from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from adapters import load_adapter
from adapters.base import Challenge, ChallengeAdapter
from adapters.official_adapter import OfficialAdapterError
from core.agent_manager import AgentManager
from core.config_watcher import ConfigWatcher, load_all_config
from core.database import Database
from core.monitor import Monitor
from core.state import AgentRecord, GlobalState, ZoneState

logger = logging.getLogger("ctf-router.dispatcher")


@dataclass(frozen=True)
class UnlockRule:
    after_zone: str
    target_zone: str
    min_solved: int | None = None
    min_score: int | None = None

    def is_enabled(self) -> bool:
        return self.min_solved is not None or self.min_score is not None

    def matched(self, zone_state: ZoneState | None) -> bool:
        if zone_state is None or not self.is_enabled():
            return False
        solved_ok = self.min_solved is not None and zone_state.solved_count >= self.min_solved
        score_ok = self.min_score is not None and zone_state.got_score >= self.min_score
        return solved_ok or score_ok

    def describe_match(self, zone_state: ZoneState | None) -> str:
        if zone_state is None:
            return "source zone has no telemetry yet"
        clauses: list[str] = []
        if self.min_solved is not None:
            clauses.append(
                f"solved {zone_state.solved_count}/{self.min_solved}"
            )
        if self.min_score is not None:
            clauses.append(
                f"score {zone_state.got_score}/{self.min_score}"
            )
        return " | ".join(clauses) if clauses else "no threshold configured"

    def to_dict(self, zone_state: ZoneState | None, active_zones: set[str]) -> dict[str, Any]:
        return {
            "after_zone": self.after_zone,
            "target_zone": self.target_zone,
            "min_solved": self.min_solved,
            "min_score": self.min_score,
            "matched": self.matched(zone_state),
            "active": self.target_zone in active_zones,
            "status": self.describe_match(zone_state),
        }


class Dispatcher:

    def __init__(
        self,
        config_dir: str | Path = "config",
        *,
        adapter: ChallengeAdapter | None = None,
        db: Database | None = None,
        monitor: Monitor | None = None,
    ) -> None:
        self._config_dir = Path(config_dir)
        self._raw_config = load_all_config(config_dir)

        default = self._raw_config.get("default", {})
        agents_cfg = self._raw_config.get("agents", {})
        runtime = self._raw_config.get("runtime", {})

        api_cfg = dict(default.get("api", {}))
        adapter_name = api_cfg.pop("adapter", "mock_adapter")
        adapter_args = api_cfg.pop("adapter_args", {})
        adapter_args.update(api_cfg)

        self.adapter: ChallengeAdapter = adapter or load_adapter(adapter_name, **adapter_args)
        self.state = GlobalState()
        self.db = db or Database(default.get("general", {}).get("db_path", "data/ctf-router.db"))
        self.monitor = monitor or Monitor(
            cpu_threshold=default.get("monitor", {}).get("cpu_threshold", 80.0),
            mem_min_mb=default.get("monitor", {}).get("mem_min_mb", 1024),
        )

        dispatch_cfg = default.get("dispatch", {})
        policy_cfg = default.get("policy", {})

        max_concurrency = int(dispatch_cfg.get("max_concurrency", 8) or 8)
        adapter_limit = getattr(self.adapter, "max_active_instances", None)
        if isinstance(adapter_limit, int) and adapter_limit > 0:
            max_concurrency = min(max_concurrency, adapter_limit)

        self.agent_mgr = AgentManager(
            monitor=self.monitor,
            state=self.state,
            db=self.db,
            max_global_concurrency=max_concurrency,
        )

        self.config_watcher = ConfigWatcher(
            config_dir=config_dir,
            on_reload=self._on_config_reload,
        )

        self._zone_templates: dict[str, dict[str, Any]] = {}
        for zone in agents_cfg.get("zone", []):
            self._zone_templates[zone["name"]] = zone

        self._zone_order = _sort_zone_names(self._zone_templates.keys())
        self._configured_active_zones = set(runtime.get("zones", {}).get("active", []))
        self._dynamic_active_zones: set[str] = set()
        self._active_zones: set[str] = set(self._configured_active_zones)
        self._activation_interval = max(1, int(dispatch_cfg.get("activation_interval_sec", 5) or 5))
        self._health_interval = max(1, int(dispatch_cfg.get("health_interval_sec", 30) or 30))
        self._working_set_size = max(1, int(policy_cfg.get("per_zone_working_set_size", 3) or 3))
        self._priority_mode = str(policy_cfg.get("priority_mode", "points_desc") or "points_desc")
        self._auto_unlock_next = bool(policy_cfg.get("auto_unlock_next", False))
        self._default_unlock_solved = _optional_int(policy_cfg.get("default_unlock_solved_count"))
        self._default_unlock_score = _optional_int(policy_cfg.get("default_unlock_score"))
        self._log_tail_lines = max(20, int(policy_cfg.get("agent_log_tail_lines", 120) or 120))
        self._unlock_rules = _load_unlock_rules(
            runtime.get("unlock", []),
            zone_order=self._zone_order,
            auto_unlock_next=self._auto_unlock_next,
            default_min_solved=self._default_unlock_solved,
            default_min_score=self._default_unlock_score,
        )
        self._health_launch_hits: dict[str, int] = {}
        self._stop = asyncio.Event()
        self._ws_broadcast: Any = None

    def set_ws_broadcast(self, fn: Any) -> None:
        self._ws_broadcast = fn
        self.agent_mgr.set_event_broadcast(fn)

    async def start(self) -> None:
        await self.db.open()
        await self._restore_state()
        logger.info("Dispatcher started | active zones: %s", self._active_zones)
        self.state.add_log(
            "INFO",
            "Dispatcher started",
            topic="lifecycle",
            active_zones=sorted(self._active_zones),
        )

    async def _restore_state(self) -> None:
        await self._restore_dynamic_active_zones()

        running = await self.db.get_running_agents()
        for row in running:
            pid = row["pid"]
            instance_id = row.get("instance_id", f"restored_{pid}")
            alive = await asyncio.to_thread(self.monitor.is_pid_alive, pid)
            if alive:
                record = AgentRecord(
                    pid=pid,
                    zone=row["zone"],
                    challenge_id=row["challenge_id"],
                    target_url=row["target_url"],
                    cmd=row["cmd"],
                    instance_id=instance_id,
                    status="running",
                    started_at=row["started_at"],
                )
                self.state.agents[instance_id] = record
                logger.info(
                    "Restored running agent: PID %d [%s] (%s/%s)",
                    pid,
                    instance_id,
                    row["zone"],
                    row["challenge_id"],
                )
            else:
                await self.db.update_agent_status(instance_id, "crashed")

        for challenge in await self.db.get_all_challenges():
            self.state.challenges[challenge["challenge_id"]] = challenge

        self._recompute_active_zones()
        for zone_name in self._zone_order:
            zone_state = self.state.zones.setdefault(zone_name, ZoneState(name=zone_name))
            zone_state.active = zone_name in self._active_zones
            zone_state.unlocked = zone_name in self._active_zones and zone_name not in self._configured_active_zones
            if zone_state.active:
                zone_state.unlock_reason = zone_state.unlock_reason or "configured"
            self._refresh_zone_metrics(zone_name)
            if zone_name in self._active_zones:
                self._mark_zone_stale(zone_name)

    async def _restore_dynamic_active_zones(self) -> None:
        payload = await self.db.kv_get("dynamic_active_zones")
        if not payload:
            self._dynamic_active_zones = set()
            return
        try:
            values = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Failed to decode dynamic_active_zones kv payload")
            self._dynamic_active_zones = set()
            return
        self._dynamic_active_zones = {
            str(item)
            for item in values
            if str(item) in self._zone_templates
        }

    def _build_agent_runtime_env(
        self,
        challenge_id: str,
        base_env: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        launch_env: dict[str, str] = {}

        if isinstance(base_env, dict):
            for key, value in base_env.items():
                if isinstance(key, str) and isinstance(value, str):
                    launch_env[key] = value

        api_cfg = self._raw_config.get("default", {}).get("api", {})
        base_url = api_cfg.get("base_url") if isinstance(api_cfg, dict) else None
        token = api_cfg.get("token") if isinstance(api_cfg, dict) else None

        launch_env["TIANTI_CHALLENGE_CODE"] = challenge_id
        if isinstance(base_url, str) and base_url.strip():
            launch_env["TIANTI_ARENA_API_BASE"] = base_url.strip()
        if isinstance(token, str) and token.strip():
            launch_env["TIANTI_AGENT_TOKEN"] = token.strip()

        return launch_env

    async def _persist_dynamic_active_zones(self) -> None:
        await self.db.kv_set(
            "dynamic_active_zones",
            json.dumps(sorted(self._dynamic_active_zones), ensure_ascii=False),
        )

    def _recompute_active_zones(self) -> None:
        self._active_zones = set(self._configured_active_zones) | set(self._dynamic_active_zones)

    async def run(self) -> None:
        await self.start()
        tasks = [
            asyncio.create_task(self._activation_loop(), name="activation"),
            asyncio.create_task(self._health_loop(), name="health"),
            asyncio.create_task(self.config_watcher.watch(), name="config"),
        ]
        try:
            await self._stop.wait()
        except asyncio.CancelledError:
            pass
        finally:
            self.config_watcher.stop()
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.agent_mgr.graceful_shutdown()
            await self._cleanup_finished_agents()
            await self.db.close()
            logger.info("Dispatcher shut down")

    async def _activation_loop(self) -> None:
        while not self._stop.is_set():
            changed = False
            for zone_name in list(self._active_zones):
                zone_state = self.state.zones.get(zone_name)
                if zone_state is None:
                    zone_state = self.state.zones.setdefault(zone_name, ZoneState(name=zone_name, active=True))
                if not zone_state.challenges_loaded:
                    await self._activate_zone(zone_name)
                    changed = True
            if changed:
                await self._broadcast()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._activation_interval)
                break
            except asyncio.TimeoutError:
                pass

    async def _activate_zone(self, zone_name: str) -> None:
        synced = await self._sync_zone(zone_name, reason="activation")
        if not synced:
            return
        await self._evaluate_unlocks()
        await self._rebalance_launches(zones=[zone_name])
        await self._broadcast()

    async def _health_loop(self) -> None:
        while not self._stop.is_set():
            await self.agent_mgr.check_health()
            await self._cleanup_finished_agents()
            for zone_name in list(self._active_zones):
                await self._sync_zone(zone_name, reason="heartbeat")
            await self._evaluate_unlocks()
            await self._rebalance_launches(require_health_confirm=True)
            await self._broadcast()
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self._health_interval)
                break
            except asyncio.TimeoutError:
                pass

    async def _sync_zone(self, zone_name: str, *, reason: str) -> bool:
        template = self._zone_templates.get(zone_name)
        if not template:
            logger.error("No template for zone %s", zone_name)
            self.state.add_log(
                "ERROR",
                f"No template configured for {zone_name}",
                topic="policy",
                zone=zone_name,
            )
            return False

        zone_state = self.state.zones.setdefault(zone_name, ZoneState(name=zone_name))
        zone_state.active = zone_name in self._active_zones
        previous = (
            zone_state.solved_count,
            zone_state.got_score,
            tuple(zone_state.working_set_ids),
        )

        try:
            challenges = await self.adapter.fetch_challenges(zone_name)
        except Exception as exc:
            zone_state.heartbeat_ok = False
            zone_state.last_error = str(exc)
            if reason == "heartbeat":
                zone_state.last_heartbeat_at = time.time()
            logger.error("Failed to fetch challenges for %s: %s", zone_name, exc)
            self.state.add_log(
                "ERROR",
                f"Failed to fetch challenges for {zone_name}: {exc}",
                topic="heartbeat",
                zone=zone_name,
            )
            return False

        now = time.time()
        zone_state.challenge_ids = []
        zone_state.last_sync_at = now
        zone_state.last_heartbeat_at = now
        zone_state.heartbeat_ok = True
        zone_state.last_error = ""

        for challenge in challenges:
            zone_state.challenge_ids.append(challenge.challenge_id)
            await self._upsert_challenge(challenge)

        working_set_ids = await self._apply_working_set(zone_name, challenges)
        zone_state.challenges_loaded = True
        self._refresh_zone_metrics(zone_name)

        current = (
            zone_state.solved_count,
            zone_state.got_score,
            tuple(working_set_ids),
        )
        if reason == "activation" or previous != current:
            self.state.add_log(
                "INFO",
                (
                    f"{zone_name} synced | solved {zone_state.solved_count}/{zone_state.total_count} "
                    f"| score {zone_state.got_score}/{zone_state.total_score} "
                    f"| working {len(zone_state.working_set_ids)}"
                ),
                topic="heartbeat",
                zone=zone_name,
            )
        logger.info(
            "Zone %s synced (%s): %d challenges, solved=%d, working=%d",
            zone_name,
            reason,
            len(challenges),
            zone_state.solved_count,
            len(zone_state.working_set_ids),
        )
        return True

    async def _apply_working_set(self, zone_name: str, challenges: list[Challenge]) -> list[str]:
        zone_state = self.state.zones.setdefault(zone_name, ZoneState(name=zone_name))
        current = [
            self.state.challenges[challenge.challenge_id]
            for challenge in challenges
            if challenge.challenge_id in self.state.challenges
        ]
        selected_ids = self._select_working_set(zone_name, current)
        selected_lookup = {challenge_id: index + 1 for index, challenge_id in enumerate(selected_ids)}

        zone_state.working_set_ids = list(selected_ids)
        for challenge in current:
            metadata = challenge.setdefault("metadata", {})
            in_working_set = challenge["challenge_id"] in selected_lookup
            window_rank = selected_lookup.get(challenge["challenge_id"])
            changed = False
            if metadata.get("in_working_set") != in_working_set:
                metadata["in_working_set"] = in_working_set
                changed = True
            if metadata.get("window_rank") != window_rank:
                metadata["window_rank"] = window_rank
                changed = True
            if changed:
                await self.db.save_challenge(challenge)
        return selected_ids

    def _select_working_set(self, zone_name: str, challenges: list[dict]) -> list[str]:
        running_ids = {
            record.challenge_id
            for record in self.state.agents.values()
            if record.zone == zone_name and record.status == "running"
        }
        unsolved = [
            challenge
            for challenge in challenges
            if not self._is_challenge_solved(challenge["challenge_id"])
        ]
        running = [
            challenge
            for challenge in unsolved
            if challenge["challenge_id"] in running_ids
        ]
        queued = [
            challenge
            for challenge in unsolved
            if challenge["challenge_id"] not in running_ids
        ]

        ordered_running = sorted(running, key=self._challenge_priority_key)
        ordered_queued = sorted(queued, key=self._challenge_priority_key)

        if len(ordered_running) >= self._working_set_size:
            return [challenge["challenge_id"] for challenge in ordered_running]

        selected = ordered_running + ordered_queued[: self._working_set_size - len(ordered_running)]
        return [challenge["challenge_id"] for challenge in selected]

    def _challenge_priority_key(self, challenge: dict) -> tuple:
        challenge_id = str(challenge.get("challenge_id", ""))
        points = int(challenge.get("points", 0) or 0)
        title = str(challenge.get("title", "") or "")
        metadata = challenge.get("metadata", {})
        hint_bias = 0 if challenge.get("hints") or metadata.get("hint_viewed") else 1
        if self._priority_mode == "id_asc":
            return (challenge_id,)
        if self._priority_mode == "title_asc":
            return (title, challenge_id)
        if self._priority_mode == "points_desc":
            return (-points, hint_bias, challenge_id)

        # --- easy_first (default): 高分低难度优先，忽略赛区 ---
        # difficulty 权重: easy=0, medium=1, hard=2 (越小越优先)
        difficulty = str(metadata.get("difficulty", "medium")).lower()
        difficulty_rank = {"easy": 0, "medium": 1, "hard": 2}.get(difficulty, 1)

        # 部分完成的题目优先 (已拿到部分 flag，继续做 ROI 最高)
        flag_count = int(metadata.get("flag_count", 0) or 0)
        flag_got_count = int(metadata.get("flag_got_count", 0) or 0)
        has_partial = -1 if 0 < flag_got_count < flag_count else 0

        # 做过没做出来的题目放到最后 (有历史失败记录)
        was_attempted = 1 if any(
            r.challenge_id == challenge_id and r.status in ("stopped", "crashed", "killed")
            for r in self.state.agents.values()
        ) else 0

        # 排序键: 部分完成优先 → 未尝试优先 → 低难度优先 → 高分优先 → 有Hint优先 → ID
        return (has_partial, was_attempted, difficulty_rank, -points, hint_bias, challenge_id)

    async def _rebalance_launches(
        self,
        *,
        zones: list[str] | None = None,
        require_health_confirm: bool = False,
    ) -> None:
        candidates = self._iter_launch_candidates(zones=zones)
        candidate_ids = {challenge["challenge_id"] for _, challenge, _ in candidates}

        if require_health_confirm:
            self._health_launch_hits = {
                challenge_id: hits
                for challenge_id, hits in self._health_launch_hits.items()
                if challenge_id in candidate_ids
            }
        else:
            for challenge_id in candidate_ids:
                self._health_launch_hits.pop(challenge_id, None)

        for zone_name, challenge, template in candidates:
            challenge_id = challenge["challenge_id"]
            if require_health_confirm:
                hits = self._health_launch_hits.get(challenge_id, 0) + 1
                self._health_launch_hits[challenge_id] = hits
                if hits < 2:
                    logger.info(
                        "Health loop launch probe %s observed (%d/2), delaying launch",
                        challenge_id,
                        hits,
                    )
                    continue

            max_zone_concurrency = int(template.get("max_concurrency", self._working_set_size) or self._working_set_size)
            can_launch, reason = await self.agent_mgr.can_launch_now(
                zone=zone_name,
                max_zone_concurrency=max_zone_concurrency,
            )
            if not can_launch:
                if reason.startswith("zone concurrency limit"):
                    continue
                break
            launched = await self._start_and_launch_challenge(
                zone_name,
                challenge,
                template,
                reason="scheduler",
            )
            if launched:
                self._health_launch_hits.pop(challenge_id, None)
                self._refresh_zone_metrics(zone_name)

    def _iter_launch_candidates(self, *, zones: list[str] | None = None) -> list[tuple[str, dict, dict[str, Any]]]:
        candidates: list[tuple[tuple, str, dict, dict[str, Any]]] = []
        active_order = {zone_name: index for index, zone_name in enumerate(self._zone_order)}
        candidate_zones = zones or sorted(self._active_zones, key=lambda item: active_order.get(item, 999))

        # easy_first 模式下忽略赛区优先级，纯按题目性价比排序
        ignore_zone_priority = self._priority_mode not in ("points_desc", "id_asc", "title_asc")

        for zone_name in candidate_zones:
            zone_state = self.state.zones.get(zone_name)
            template = self._zone_templates.get(zone_name)
            if zone_state is None or template is None:
                continue
            for window_rank, challenge_id in enumerate(zone_state.working_set_ids, start=1):
                challenge = self.state.challenges.get(challenge_id)
                if challenge is None:
                    continue
                if self._is_challenge_solved(challenge_id):
                    continue
                if any(
                    record.challenge_id == challenge_id and record.status == "running"
                    for record in self.state.agents.values()
                ):
                    continue

                if ignore_zone_priority:
                    # 排序键仅由题目优先级决定，赛区和窗口排名不参与
                    sort_key = self._challenge_priority_key(challenge)
                else:
                    sort_key = (
                        active_order.get(zone_name, 999),
                        window_rank,
                        *self._challenge_priority_key(challenge),
                    )

                candidates.append((sort_key, zone_name, challenge, template))

        candidates.sort(key=lambda item: item[0])
        return [(zone_name, challenge, template) for _, zone_name, challenge, template in candidates]

    async def _start_and_launch_challenge(
        self,
        zone_name: str,
        challenge: dict,
        template: dict[str, Any],
        *,
        reason: str,
    ) -> bool:
        challenge_id = challenge["challenge_id"]
        if self._is_challenge_solved(challenge_id):
            return False
        if any(
            record.challenge_id == challenge_id and record.status == "running"
            for record in self.state.agents.values()
        ):
            return False

        self.state.add_log(
            "INFO",
            f"Launching {challenge_id} for {zone_name}",
            topic="launch",
            zone=zone_name,
            challenge_id=challenge_id,
            trigger=reason,
        )

        try:
            started = await self.adapter.start_challenge(challenge_id)
        except Exception as exc:
            logger.error("Failed to start challenge %s: %s", challenge_id, exc)
            self.state.add_log(
                "ERROR",
                f"Failed to start challenge {challenge_id}: {exc}",
                topic="launch",
                zone=zone_name,
                challenge_id=challenge_id,
            )
            return False

        if started.already_completed:
            await self._mark_challenge_completed(challenge_id, started.message)
            self._mark_zone_stale(zone_name)
            return False

        target_url = started.primary_target_url or challenge.get("target_url", "")
        if not target_url:
            self.state.add_log(
                "ERROR",
                f"Challenge {challenge_id} started without entrypoint",
                topic="launch",
                zone=zone_name,
                challenge_id=challenge_id,
            )
            try:
                await self.adapter.stop_challenge(challenge_id)
            except Exception:
                logger.exception("Failed to stop challenge %s after missing entrypoint", challenge_id)
            return False

        launch_hints = await self._prefetch_launch_hints(challenge_id)
        launch_instruction = _compose_instruction(challenge.get("instruction", ""), launch_hints)
        max_zone_concurrency = int(template.get("max_concurrency", self._working_set_size) or self._working_set_size)
        launch_env = self._build_agent_runtime_env(challenge_id, template.get("env"))

        instance_id = await self.agent_mgr.launch(
            zone=zone_name,
            challenge_id=challenge_id,
            target_url=target_url,
            instruction=launch_instruction,
            agent_template=template.get(
                "agent_template",
                "python3 -c \"import time; time.sleep(3600)\"",
            ),
            env=launch_env,
            max_zone_concurrency=max_zone_concurrency,
            queue_if_blocked=False,
        )
        if not instance_id:
            try:
                await self.adapter.stop_challenge(challenge_id)
            except Exception:
                logger.exception("Failed to stop deferred challenge %s", challenge_id)
            return False

        record = self.state.agents.get(instance_id)
        if record is not None:
            record.platform_instance_active = True
            record.platform_cleanup_done = False

        await self._update_challenge_runtime(
            challenge_id,
            target_url=target_url,
            status="running",
            metadata_updates={
                "instance_status": "running",
                "entrypoints": list(started.entrypoints),
                "start_message": started.message,
                "already_completed": False,
                "launch_hints": list(launch_hints),
                "launch_instruction": launch_instruction,
            },
        )
        self.state.add_log(
            "INFO",
            f"Agent launched for {challenge_id}",
            topic="launch",
            zone=zone_name,
            challenge_id=challenge_id,
            instance_id=instance_id,
            target_url=target_url,
        )
        return True

    async def _cleanup_finished_agents(self) -> None:
        for instance_id, record in list(self.state.agents.items()):
            if record.status == "running":
                continue
            if not record.platform_instance_active or record.platform_cleanup_done:
                continue
            if any(
                other.challenge_id == record.challenge_id
                and other.status == "running"
                and other.instance_id != instance_id
                for other in self.state.agents.values()
            ):
                continue

            try:
                await self.adapter.stop_challenge(record.challenge_id)
            except OfficialAdapterError as exc:
                if exc.status_code != 400:
                    self.state.add_log(
                        "ERROR",
                        f"Failed to stop challenge {record.challenge_id}: {exc}",
                        topic="cleanup",
                        zone=record.zone,
                        challenge_id=record.challenge_id,
                        instance_id=instance_id,
                    )
                    continue
            except Exception as exc:
                self.state.add_log(
                    "ERROR",
                    f"Failed to stop challenge {record.challenge_id}: {exc}",
                    topic="cleanup",
                    zone=record.zone,
                    challenge_id=record.challenge_id,
                    instance_id=instance_id,
                )
                continue

            record.platform_instance_active = False
            record.platform_cleanup_done = True
            await self._mark_challenge_stopped(record)

    async def _mark_challenge_stopped(self, record: AgentRecord) -> None:
        challenge = self.state.challenges.get(record.challenge_id)
        if challenge is None:
            return

        metadata = challenge.setdefault("metadata", {})
        metadata["instance_status"] = "stopped"
        if challenge.get("status") == "running":
            challenge["status"] = "failed" if record.status == "crashed" else "pending"
        if challenge.get("status") == "solved":
            metadata["completed_by_instance"] = record.instance_id
        await self.db.save_challenge(challenge)
        self._mark_zone_stale(record.zone)
        self._refresh_zone_metrics(record.zone)
        self.state.add_log(
            "INFO" if record.status == "stopped" else "WARN",
            f"Challenge {record.challenge_id} instance stopped",
            topic="cleanup",
            zone=record.zone,
            challenge_id=record.challenge_id,
            instance_id=record.instance_id,
            status=record.status,
        )

    async def _mark_challenge_completed(self, challenge_id: str, message: str = "") -> None:
        challenge = self.state.challenges.get(challenge_id)
        if challenge is None:
            return
        challenge["status"] = "solved"
        challenge.setdefault("metadata", {})
        challenge["metadata"]["already_completed"] = True
        challenge["metadata"]["completion_message"] = message
        challenge["metadata"]["instance_status"] = "stopped"
        await self.db.save_challenge(challenge)
        self._refresh_zone_metrics(challenge["zone"])
        self.state.add_log(
            "INFO",
            f"Challenge {challenge_id} already completed on platform",
            topic="platform",
            zone=challenge["zone"],
            challenge_id=challenge_id,
        )

    async def _upsert_challenge(self, challenge: Challenge) -> None:
        current = self.state.challenges.get(challenge.challenge_id, {})
        merged = challenge.to_dict()
        merged.setdefault("metadata", {})
        merged["metadata"] = {
            **current.get("metadata", {}),
            **merged.get("metadata", {}),
        }
        if current.get("status") == "solved":
            merged["status"] = "solved"
        self.state.challenges[challenge.challenge_id] = merged
        await self.db.save_challenge(merged)

    async def _update_challenge_runtime(
        self,
        challenge_id: str,
        *,
        target_url: str | None = None,
        status: str | None = None,
        metadata_updates: dict[str, Any] | None = None,
    ) -> None:
        challenge = self.state.challenges.get(challenge_id)
        if challenge is None:
            return
        if target_url is not None:
            challenge["target_url"] = target_url
        if status is not None:
            challenge["status"] = status
        if metadata_updates:
            challenge.setdefault("metadata", {})
            challenge["metadata"].update(metadata_updates)
        await self.db.save_challenge(challenge)

    async def _evaluate_unlocks(self) -> None:
        unlocked_any = False
        for rule in self._unlock_rules:
            if rule.target_zone in self._active_zones:
                continue
            source_state = self.state.zones.get(rule.after_zone)
            if not rule.matched(source_state):
                continue
            self._dynamic_active_zones.add(rule.target_zone)
            self._recompute_active_zones()
            await self._persist_dynamic_active_zones()
            zone_state = self.state.zones.setdefault(rule.target_zone, ZoneState(name=rule.target_zone))
            zone_state.active = True
            zone_state.unlocked = True
            zone_state.unlock_reason = (
                f"Unlocked by {rule.after_zone} ({rule.describe_match(source_state)})"
            )
            self._mark_zone_stale(rule.target_zone)
            self.state.add_log(
                "INFO",
                f"{rule.target_zone} unlocked by {rule.after_zone}",
                topic="policy",
                zone=rule.target_zone,
                source_zone=rule.after_zone,
                detail=rule.describe_match(source_state),
            )
            unlocked_any = True
        if unlocked_any:
            logger.info("Auto unlock evaluated: active zones = %s", self._active_zones)

    async def activate_zone(self, zone_name: str, *, reason: str = "manual") -> None:
        if zone_name not in self._zone_templates:
            raise KeyError(zone_name)
        if zone_name not in self._configured_active_zones:
            self._dynamic_active_zones.add(zone_name)
            await self._persist_dynamic_active_zones()
        self._recompute_active_zones()
        zone_state = self.state.zones.setdefault(zone_name, ZoneState(name=zone_name))
        zone_state.active = True
        zone_state.unlocked = zone_name not in self._configured_active_zones
        zone_state.unlock_reason = reason
        self._mark_zone_stale(zone_name)
        self.state.add_log(
            "INFO",
            f"Zone {zone_name} activated",
            topic="policy",
            zone=zone_name,
            trigger=reason,
        )

    async def _on_config_reload(self, file_stem: str, data: dict[str, Any]) -> None:
        logger.info("Config reloaded: %s", file_stem)
        self.state.add_log("INFO", f"Config reloaded: {file_stem}", topic="config")

        if file_stem == "runtime":
            self._configured_active_zones = set(data.get("zones", {}).get("active", []))
            self._unlock_rules = _load_unlock_rules(
                data.get("unlock", []),
                zone_order=self._zone_order,
                auto_unlock_next=self._auto_unlock_next,
                default_min_solved=self._default_unlock_solved,
                default_min_score=self._default_unlock_score,
            )
            self._recompute_active_zones()
            for zone_name in self._zone_templates:
                zone_state = self.state.zones.setdefault(zone_name, ZoneState(name=zone_name))
                zone_state.active = zone_name in self._active_zones
                zone_state.unlocked = zone_name in self._active_zones and zone_name not in self._configured_active_zones
            for zone_name in self._active_zones:
                self._mark_zone_stale(zone_name)

        elif file_stem == "agents":
            self._zone_templates = {}
            for zone in data.get("zone", []):
                self._zone_templates[zone["name"]] = zone
                zone_state = self.state.zones.setdefault(zone["name"], ZoneState(name=zone["name"]))
                zone_state.active = zone["name"] in self._active_zones
            self._zone_order = _sort_zone_names(self._zone_templates.keys())
            logger.info("Agent templates reloaded")
            for zone_name in self._active_zones:
                self._mark_zone_stale(zone_name)

        elif file_stem == "default":
            dispatch = data.get("dispatch", {})
            policy = data.get("policy", {})

            max_concurrency = dispatch.get("max_concurrency")
            if max_concurrency is not None and int(max_concurrency) > 0:
                max_global = int(max_concurrency)
                adapter_limit = getattr(self.adapter, "max_active_instances", None)
                if isinstance(adapter_limit, int) and adapter_limit > 0:
                    max_global = min(max_global, adapter_limit)
                self.agent_mgr._max_global = max_global

            self._activation_interval = max(1, int(dispatch.get("activation_interval_sec", self._activation_interval) or self._activation_interval))
            self._health_interval = max(1, int(dispatch.get("health_interval_sec", self._health_interval) or self._health_interval))
            self._working_set_size = max(1, int(policy.get("per_zone_working_set_size", self._working_set_size) or self._working_set_size))
            self._priority_mode = str(policy.get("priority_mode", self._priority_mode) or self._priority_mode)
            self._auto_unlock_next = bool(policy.get("auto_unlock_next", self._auto_unlock_next))
            self._default_unlock_solved = _optional_int(policy.get("default_unlock_solved_count", self._default_unlock_solved))
            self._default_unlock_score = _optional_int(policy.get("default_unlock_score", self._default_unlock_score))
            self._log_tail_lines = max(20, int(policy.get("agent_log_tail_lines", self._log_tail_lines) or self._log_tail_lines))
            self._unlock_rules = _load_unlock_rules(
                self._raw_config.get("runtime", {}).get("unlock", []),
                zone_order=self._zone_order,
                auto_unlock_next=self._auto_unlock_next,
                default_min_solved=self._default_unlock_solved,
                default_min_score=self._default_unlock_score,
            )

        self._raw_config[file_stem] = data
        await self._broadcast()

    async def _broadcast(self) -> None:
        if self._ws_broadcast:
            try:
                await self._ws_broadcast(self.get_snapshot())
            except Exception:
                pass

    def get_snapshot(self) -> dict[str, Any]:
        return {
            "system": self.monitor.get_system_stats(),
            "running_agents": self.agent_mgr.running_count,
            "queued": self.agent_mgr.pending_count,
            "control": self.get_control_snapshot(),
            **self.state.to_dict(),
        }

    def get_control_snapshot(self) -> dict[str, Any]:
        return {
            "activation_interval_sec": self._activation_interval,
            "heartbeat_interval_sec": self._health_interval,
            "working_set_size": self._working_set_size,
            "priority_mode": self._priority_mode,
            "configured_active_zones": sorted(self._configured_active_zones),
            "dynamic_active_zones": sorted(self._dynamic_active_zones),
            "active_zones": sorted(self._active_zones),
            "unlock_rules": [
                rule.to_dict(self.state.zones.get(rule.after_zone), self._active_zones)
                for rule in self._unlock_rules
            ],
        }

    def get_agent_events(self, instance_id: str) -> list[dict]:
        return self.agent_mgr.get_agent_events(instance_id)

    def get_agent_log_bundle(self, instance_id: str, *, lines: int | None = None) -> dict[str, Any]:
        line_limit = max(20, int(lines or self._log_tail_lines))
        log_dir = Path("data/logs")
        stdout_path = log_dir / f"agent_{instance_id}.stdout.log"
        stderr_path = log_dir / f"agent_{instance_id}.stderr.log"
        return {
            "instance_id": instance_id,
            "stdout": _tail_text_file(stdout_path, line_limit),
            "stderr": _tail_text_file(stderr_path, line_limit),
            "events": self.get_agent_events(instance_id)[-line_limit:],
        }

    async def kill_agent(self, instance_id: str) -> bool:
        ok = await self.agent_mgr.kill_agent(instance_id)
        if ok:
            await self._cleanup_finished_agents()
        return ok

    def request_stop(self) -> None:
        self._stop.set()

    async def _prefetch_launch_hints(self, challenge_id: str) -> list[str]:
        challenge = self.state.challenges.get(challenge_id)
        known_hints = list(challenge.get("hints", [])) if challenge else []

        try:
            fetched_hints = await self.adapter.fetch_hints(challenge_id)
        except Exception as exc:
            self.state.add_log(
                "WARN",
                f"Failed to prefetch hints for {challenge_id}: {exc}",
                topic="hint",
                challenge_id=challenge_id,
            )
            return known_hints

        merged_hints = list(known_hints)
        for hint in fetched_hints:
            if hint not in merged_hints:
                merged_hints.append(hint)

        if challenge is not None:
            challenge["hints"] = merged_hints
            challenge.setdefault("metadata", {})
            challenge["metadata"]["hint_viewed"] = bool(merged_hints)
            await self.db.save_challenge(challenge)

        if merged_hints:
            self.state.add_log(
                "INFO",
                f"Hint prefetched for {challenge_id}",
                topic="hint",
                challenge_id=challenge_id,
                hint_count=len(merged_hints),
            )
        return merged_hints

    def _mark_zone_stale(self, zone_name: str) -> None:
        zone_state = self.state.zones.setdefault(zone_name, ZoneState(name=zone_name, active=True))
        zone_state.active = zone_name in self._active_zones
        zone_state.challenges_loaded = False

    def _refresh_zone_metrics(self, zone_name: str) -> None:
        zone_state = self.state.zones.setdefault(zone_name, ZoneState(name=zone_name))
        zone_challenges = [
            challenge
            for challenge in self.state.challenges.values()
            if challenge.get("zone") == zone_name
        ]
        zone_state.total_count = len(zone_challenges)
        zone_state.solved_count = sum(
            1 for challenge in zone_challenges if self._is_challenge_solved(challenge["challenge_id"])
        )
        zone_state.total_score = sum(int(challenge.get("points", 0) or 0) for challenge in zone_challenges)
        zone_state.got_score = sum(_challenge_got_score(challenge) for challenge in zone_challenges)
        zone_state.running_count = sum(
            1
            for record in self.state.agents.values()
            if record.zone == zone_name and record.status == "running"
        )
        zone_state.pending_count = sum(
            1
            for challenge_id in zone_state.working_set_ids
            if not self._is_challenge_solved(challenge_id)
            and not any(
                record.challenge_id == challenge_id and record.status == "running"
                for record in self.state.agents.values()
            )
        )
        zone_state.hint_count = sum(
            1
            for challenge in zone_challenges
            if challenge.get("hints") or challenge.get("metadata", {}).get("hint_viewed")
        )

    def _is_challenge_solved(self, challenge_id: str) -> bool:
        challenge = self.state.challenges.get(challenge_id, {})
        if challenge.get("status") == "solved":
            return True
        metadata = challenge.get("metadata", {})
        flag_count = int(metadata.get("flag_count", 0) or 0)
        flag_got_count = int(metadata.get("flag_got_count", 0) or 0)
        return flag_count > 0 and flag_got_count >= flag_count


def _compose_instruction(base_instruction: str, hints: list[str]) -> str:
    instruction = str(base_instruction or "").strip()
    cleaned_hints = [str(item).strip() for item in hints if str(item).strip()]
    if not cleaned_hints:
        return instruction

    hint_lines = "\n".join(f"- {hint}" for hint in cleaned_hints)
    hint_block = (
        "官方 Hint（已主动读取，请优先利用这些线索规划攻击路径）：\n"
        f"{hint_lines}\n\n"
        "目标仍然是获取正确 flag；不要只停留在漏洞发现。"
    )
    if not instruction:
        return hint_block
    return f"{instruction}\n\n{hint_block}"


def _challenge_got_score(challenge: dict) -> int:
    metadata = challenge.get("metadata", {})
    if "total_got_score" in metadata:
        return int(metadata.get("total_got_score", 0) or 0)
    return int(challenge.get("points", 0) or 0) if metadata.get("flag_got_count", 0) else 0


def _optional_int(value: Any) -> int | None:
    if value in (None, "", False):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _sort_zone_names(zone_names: Any) -> list[str]:
    return sorted(zone_names, key=_zone_sort_key)


def _zone_sort_key(zone_name: str) -> tuple[int, str]:
    suffix = str(zone_name).split("_")[-1]
    try:
        return (int(suffix), str(zone_name))
    except ValueError:
        return (999, str(zone_name))


def _load_unlock_rules(
    raw_rules: Any,
    *,
    zone_order: list[str],
    auto_unlock_next: bool,
    default_min_solved: int | None,
    default_min_score: int | None,
) -> list[UnlockRule]:
    rules: list[UnlockRule] = []
    for item in raw_rules if isinstance(raw_rules, list) else []:
        if not isinstance(item, dict):
            continue
        after_zone = str(item.get("after_zone", "")).strip()
        target_zone = str(item.get("target_zone", "")).strip()
        if not after_zone or not target_zone:
            continue
        rules.append(
            UnlockRule(
                after_zone=after_zone,
                target_zone=target_zone,
                min_solved=_optional_int(item.get("min_solved")),
                min_score=_optional_int(item.get("min_score")),
            )
        )

    if rules or not auto_unlock_next:
        return rules

    derived: list[UnlockRule] = []
    for index in range(len(zone_order) - 1):
        derived.append(
            UnlockRule(
                after_zone=zone_order[index],
                target_zone=zone_order[index + 1],
                min_solved=default_min_solved,
                min_score=default_min_score,
            )
        )
    return derived


def _tail_text_file(path: Path, lines: int) -> list[str]:
    if not path.exists():
        return []
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    return content[-lines:]
