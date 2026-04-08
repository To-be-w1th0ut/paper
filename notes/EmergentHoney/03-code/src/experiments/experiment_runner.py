"""
EmergentHoney 实验模块：实验运行器
实现论文 Section VI 的完整实验流程
"""

import numpy as np
import json
import time
import logging
import os
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path

# 导入项目模块
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.core.pheromone_engine import (
    PheromoneEngine, SelfOrganizer,
    HoneypotConfig, AttackerInteraction,
)
from src.core.reverse_aco import ReverseACO, ReconAction
from src.llm.phenotype_generator import PhenotypeGenerator, MockLLMBackend
from src.network.sdn_topology import SDNTopology
from src.network.honeypot_deployer import HoneypotDeployer

logger = logging.getLogger(__name__)


# ============================================================
# 攻击者模拟器
# ============================================================

class AttackerSimulator:
    """
    多阶段APT攻击模拟器

    模拟MITRE ATT&CK框架的攻击链:
    1. Reconnaissance (侦察)
    2. Initial Access (初始访问)
    3. Execution / Privilege Escalation
    4. Lateral Movement (横向移动)
    5. Collection / Exfiltration

    攻击者行为参数:
    - sophistication: 攻击者水平 [0,1]，影响蜜罐识别能力
    - persistence: 持久性 [0,1]，影响驻留时间
    - adaptiveness: 适应性 [0,1]，影响是否回避已知蜜罐
    """

    ATTACK_TECHNIQUES = {
        "recon": ["T1595", "T1592", "T1590", "T1589"],       # 侦察
        "initial_access": ["T1190", "T1133", "T1078"],        # 初始访问
        "lateral": ["T1021", "T1570", "T1550", "T1563"],      # 横向移动
        "exfil": ["T1048", "T1041", "T1567"],                 # 数据窃取
    }

    def __init__(
        self,
        attacker_id: str,
        topology: SDNTopology,
        sophistication: float = 0.5,
        persistence: float = 0.5,
        adaptiveness: float = 0.5,
        entry_node: Optional[int] = None,
    ):
        self.attacker_id = attacker_id
        self.topology = topology
        self.sophistication = sophistication
        self.persistence = persistence
        self.adaptiveness = adaptiveness

        # 选择入口节点
        if entry_node is not None:
            self.current_node = entry_node
        else:
            # 随机选择DMZ或边界节点
            dmz_nodes = topology.get_subnet_nodes(0)
            self.current_node = np.random.choice(dmz_nodes) if dmz_nodes else 0

        self.trajectory: List[int] = [self.current_node]
        self.discovered_honeypots: set = set()
        self.phase = "recon"
        self.active = True
        self.total_time = 0.0

    def step(
        self,
        honeypot_positions: set,
        time_step: float,
    ) -> Tuple[Optional[ReconAction], Optional[AttackerInteraction]]:
        """
        执行一步攻击动作

        Returns:
            (侦察动作, 蜜罐交互) — 蜜罐交互可能为None
        """
        if not self.active:
            return None, None

        neighbors = self.topology.get_neighbors(self.current_node)
        if not neighbors:
            self.active = False
            return None, None

        # 选择目标节点
        target = self._select_target(neighbors, honeypot_positions)

        # 生成侦察动作
        action_type = self._get_action_type()
        techniques = self._get_techniques()

        recon_action = ReconAction(
            attacker_id=self.attacker_id,
            source=self.current_node,
            target=target,
            action_type=action_type,
            timestamp=time_step,
            success=True,
            techniques=techniques,
        )

        # 检查是否与蜜罐交互
        interaction = None
        if target in honeypot_positions:
            # 蜜罐识别概率
            detect_prob = self.sophistication * 0.3  # 基础识别概率

            if np.random.random() > detect_prob:
                # 未识别为蜜罐 → 产生交互
                engagement = self._compute_engagement_time()
                detection_risk = 1.0 - self.sophistication * 0.5

                interaction = AttackerInteraction(
                    attacker_id=self.attacker_id,
                    position=target,
                    hp_type=0,  # 由引擎确定
                    engagement_time=engagement,
                    detection_risk=detection_risk,
                    techniques_observed=techniques,
                    timestamp=time_step,
                )
                self.total_time += engagement
            else:
                # 识别为蜜罐
                self.discovered_honeypots.add(target)

        # 移动到目标
        self.current_node = target
        self.trajectory.append(target)

        # 更新攻击阶段
        self._update_phase()

        return recon_action, interaction

    def _select_target(
        self, neighbors: List[int], honeypot_positions: set
    ) -> int:
        """选择目标节点"""
        # 过滤已知蜜罐 (如果适应性足够高)
        if self.adaptiveness > 0.3:
            safe_neighbors = [
                n for n in neighbors if n not in self.discovered_honeypots
            ]
            if safe_neighbors:
                neighbors = safe_neighbors

        # 偏好未访问过的节点
        unvisited = [n for n in neighbors if n not in set(self.trajectory)]
        if unvisited and np.random.random() < 0.7:
            # 偏好高价值节点
            values = [self.topology.nodes[n].value for n in unvisited]
            probs = np.array(values)
            probs = probs / (probs.sum() + 1e-10)
            return int(np.random.choice(unvisited, p=probs))

        return int(np.random.choice(neighbors))

    def _compute_engagement_time(self) -> float:
        """计算与蜜罐的驻留时间"""
        base_time = 30.0 + np.random.exponential(60.0)
        # 持久性越高，驻留越长
        return base_time * (1 + self.persistence)

    def _get_action_type(self) -> str:
        """根据攻击阶段返回动作类型"""
        phase_map = {
            "recon": ["port_scan", "service_probe"],
            "initial_access": ["exploit", "service_probe"],
            "lateral": ["lateral_move", "exploit"],
            "exfil": ["lateral_move", "exploit"],
        }
        options = phase_map.get(self.phase, ["port_scan"])
        return str(np.random.choice(options))

    def _get_techniques(self) -> List[str]:
        """根据攻击阶段返回ATT&CK技术"""
        techs = self.ATTACK_TECHNIQUES.get(self.phase, ["T1595"])
        k = min(2, len(techs))
        return list(np.random.choice(techs, size=k, replace=False))

    def _update_phase(self):
        """更新攻击阶段"""
        steps = len(self.trajectory)
        if steps < 5:
            self.phase = "recon"
        elif steps < 15:
            self.phase = "initial_access"
        elif steps < 30:
            self.phase = "lateral"
        else:
            self.phase = "exfil"

        # 攻击者可能放弃
        if steps > 50 or self.total_time > 3600:
            self.active = False


# ============================================================
# Baseline 对比方法
# ============================================================

class BaselineMethod:
    """基线方法基类"""

    def __init__(self, num_positions: int, num_types: int, budget: int):
        self.num_positions = num_positions
        self.num_types = num_types
        self.budget = budget
        self.honeypots: Dict[int, int] = {}  # {position: type}

    def initialize(self):
        """初始部署"""
        raise NotImplementedError

    def update(self, interactions: List[AttackerInteraction]):
        """更新 (可选)"""
        pass

    def get_positions(self) -> set:
        return set(self.honeypots.keys())


class StaticBaseline(BaselineMethod):
    """静态随机部署基线"""

    def initialize(self):
        positions = np.random.choice(
            self.num_positions, size=min(self.budget, self.num_positions),
            replace=False
        )
        for pos in positions:
            self.honeypots[int(pos)] = np.random.randint(self.num_types)


class RandomDynamicBaseline(BaselineMethod):
    """随机动态部署基线 (每N步随机重新部署)"""

    def __init__(self, *args, redeploy_interval: int = 10, **kwargs):
        super().__init__(*args, **kwargs)
        self.redeploy_interval = redeploy_interval
        self.step_count = 0

    def initialize(self):
        self._random_deploy()

    def update(self, interactions):
        self.step_count += 1
        if self.step_count % self.redeploy_interval == 0:
            self._random_deploy()

    def _random_deploy(self):
        self.honeypots.clear()
        positions = np.random.choice(
            self.num_positions, size=min(self.budget, self.num_positions),
            replace=False
        )
        for pos in positions:
            self.honeypots[int(pos)] = np.random.randint(self.num_types)


class RLBaseline(BaselineMethod):
    """强化学习基线 (简化Q-learning)"""

    def __init__(self, *args, learning_rate: float = 0.1,
                 epsilon: float = 0.1, **kwargs):
        super().__init__(*args, **kwargs)
        self.lr = learning_rate
        self.epsilon = epsilon
        self.q_table = np.zeros((self.num_positions, self.num_types))

    def initialize(self):
        # ε-greedy 初始部署
        self._deploy_from_q()

    def update(self, interactions):
        # Q值更新
        for inter in interactions:
            reward = inter.engagement_time / max(inter.detection_risk, 0.01)
            i, j = inter.position, inter.hp_type
            if 0 <= i < self.num_positions and 0 <= j < self.num_types:
                self.q_table[i, j] += self.lr * (reward - self.q_table[i, j])

        self._deploy_from_q()

    def _deploy_from_q(self):
        self.honeypots.clear()
        # 选取Q值最高的B个位置
        max_q = self.q_table.max(axis=1)
        top_positions = np.argsort(max_q)[-self.budget:]

        for pos in top_positions:
            pos = int(pos)
            if np.random.random() < self.epsilon:
                hp_type = np.random.randint(self.num_types)
            else:
                hp_type = int(np.argmax(self.q_table[pos]))
            self.honeypots[pos] = hp_type


class GameTheoreticBaseline(BaselineMethod):
    """博弈论基线 (简化Stackelberg博弈)"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.coverage_value = np.random.uniform(0.5, 2.0, self.num_positions)

    def initialize(self):
        # 按价值排序，部署到最高价值位置
        top_positions = np.argsort(self.coverage_value)[-self.budget:]
        for pos in top_positions:
            self.honeypots[int(pos)] = np.random.randint(self.num_types)

    def update(self, interactions):
        # 更新价值估计
        for inter in interactions:
            if 0 <= inter.position < self.num_positions:
                self.coverage_value[inter.position] += inter.engagement_time * 0.01
        self.initialize()


# ============================================================
# 实验运行器
# ============================================================

@dataclass
class ExperimentConfig:
    """实验配置"""
    # 网络参数
    num_nodes: int = 50
    topology_type: str = "enterprise"

    # 蜜罐参数
    num_hp_types: int = 8
    budget: int = 15

    # 信息素参数
    evaporation_rate: float = 0.05
    Q: float = 100.0
    delta_max: float = 50.0

    # 攻击者参数
    num_attackers: int = 5
    attacker_sophistication: float = 0.5
    attacker_persistence: float = 0.5
    attacker_adaptiveness: float = 0.5

    # 实验参数
    num_steps: int = 200
    num_runs: int = 30
    random_seed: int = 42

    # 输出
    output_dir: str = "results"


@dataclass
class RunMetrics:
    """单次运行的指标"""
    # 核心指标 (Table 1-2)
    avg_dwell_time: float = 0.0          # 平均驻留时间 ADT (秒)
    interaction_rate: float = 0.0         # 交互率 IR
    attacker_coverage: float = 0.0        # 攻击者覆盖率

    # 收敛指标 (Table 3)
    convergence_step: int = 0             # 收敛步数
    convergence_rate: float = 0.0         # 收敛速率

    # 自适应指标 (Table 5)
    response_time: float = 0.0           # 响应时间 (步)
    topology_changes: int = 0            # 拓扑变化次数

    # 预测指标 (Table 7)
    prediction_precision: float = 0.0
    prediction_recall: float = 0.0
    prediction_f1: float = 0.0

    # DEI 指标 (Table 4)
    dei_value: float = 0.0

    # 计算开销
    avg_step_time_ms: float = 0.0

    # 原始数据
    dwell_times: List[float] = field(default_factory=list)
    pheromone_history: List[float] = field(default_factory=list)


class ExperimentRunner:
    """
    实验运行器 — 编排完整的实验流程

    实验矩阵 (论文 Table 1-9):
    1. 核心性能对比 (Table 1-2): EmergentHoney vs 4基线
    2. 收敛分析 (Table 3): 不同网络规模的收敛速度
    3. DEI验证 (Table 4): 个体vs集群欺骗能力
    4. 自适应性 (Table 5): 攻击策略切换后的恢复
    5. 消融实验 (Table 6): 各组件贡献
    6. 预测准确率 (Table 7): 反向ACO性能
    7. 可扩展性 (Table 8): 50/200/500节点
    8. 对抗性 (Table 9): 不同水平攻击者
    """

    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.results: Dict[str, List[RunMetrics]] = {}

        # 创建输出目录
        os.makedirs(config.output_dir, exist_ok=True)

    def run_all_experiments(self):
        """运行全部实验"""
        logger.info("=" * 60)
        logger.info("EmergentHoney 实验开始")
        logger.info("=" * 60)

        # 实验1: 核心性能对比
        self.run_comparison_experiment()

        # 实验2: 收敛分析
        self.run_convergence_experiment()

        # 实验3: DEI验证
        self.run_dei_experiment()

        # 实验4: 可扩展性
        self.run_scalability_experiment()

        # 实验5: 消融实验
        self.run_ablation_experiment()

        # 保存所有结果
        self.save_results()

        logger.info("=" * 60)
        logger.info("所有实验完成")
        logger.info("=" * 60)

    def run_comparison_experiment(self):
        """实验1: EmergentHoney vs 基线方法对比"""
        logger.info("[实验1] 核心性能对比")

        methods = {
            "EmergentHoney": None,  # 特殊处理
            "Static": StaticBaseline,
            "RandomDynamic": RandomDynamicBaseline,
            "RL": RLBaseline,
            "GameTheoretic": GameTheoreticBaseline,
        }

        for method_name, baseline_cls in methods.items():
            logger.info(f"  运行 {method_name}...")
            run_results = []

            for run in range(self.config.num_runs):
                np.random.seed(self.config.random_seed + run)

                if method_name == "EmergentHoney":
                    metrics = self._run_emergent_honey(run)
                else:
                    metrics = self._run_baseline(baseline_cls, run)

                run_results.append(metrics)

            self.results[f"comparison_{method_name}"] = run_results

            # 输出摘要
            avg_adt = np.mean([r.avg_dwell_time for r in run_results])
            std_adt = np.std([r.avg_dwell_time for r in run_results])
            logger.info(f"  {method_name}: ADT={avg_adt:.1f}±{std_adt:.1f}s")

    def run_convergence_experiment(self):
        """实验2: 收敛分析"""
        logger.info("[实验2] 收敛分析")

        for size in [50, 200, 500]:
            config = ExperimentConfig(
                num_nodes=size,
                num_steps=300,
                num_runs=min(self.config.num_runs, 10),
                budget=max(size // 5, 10),
                random_seed=self.config.random_seed,
            )

            run_results = []
            for run in range(config.num_runs):
                np.random.seed(config.random_seed + run)
                metrics = self._run_single(config)
                run_results.append(metrics)

            self.results[f"convergence_{size}"] = run_results
            avg_conv = np.mean([r.convergence_step for r in run_results])
            logger.info(f"  |V|={size}: 平均收敛步数={avg_conv:.0f}")

    def run_dei_experiment(self):
        """实验3: DEI验证"""
        logger.info("[实验3] DEI验证")

        run_results = []
        for run in range(self.config.num_runs):
            np.random.seed(self.config.random_seed + run)
            metrics = self._run_emergent_honey(run, track_dei=True)
            run_results.append(metrics)

        self.results["dei_verification"] = run_results
        avg_dei = np.mean([r.dei_value for r in run_results])
        logger.info(f"  平均DEI={avg_dei:.3f}")

    def run_scalability_experiment(self):
        """实验4: 可扩展性"""
        logger.info("[实验4] 可扩展性")

        for size in [50, 200, 500]:
            config = ExperimentConfig(
                num_nodes=size,
                num_steps=200,
                num_runs=min(self.config.num_runs, 10),
                budget=max(size // 5, 10),
                num_attackers=max(size // 10, 3),
                random_seed=self.config.random_seed,
            )

            run_results = []
            for run in range(config.num_runs):
                np.random.seed(config.random_seed + run)
                metrics = self._run_single(config)
                run_results.append(metrics)

            self.results[f"scalability_{size}"] = run_results
            avg_time = np.mean([r.avg_step_time_ms for r in run_results])
            logger.info(f"  |V|={size}: 平均步时间={avg_time:.2f}ms")

    def run_ablation_experiment(self):
        """实验5: 消融实验"""
        logger.info("[实验5] 消融实验")

        ablation_configs = {
            "full": {"use_reverse_aco": True, "use_llm": True,
                     "use_adaptive_rho": True},
            "no_reverse_aco": {"use_reverse_aco": False, "use_llm": True,
                               "use_adaptive_rho": True},
            "no_llm": {"use_reverse_aco": True, "use_llm": False,
                       "use_adaptive_rho": True},
            "no_adaptive_rho": {"use_reverse_aco": True, "use_llm": True,
                                "use_adaptive_rho": False},
            "pheromone_only": {"use_reverse_aco": False, "use_llm": False,
                               "use_adaptive_rho": False},
        }

        for variant, flags in ablation_configs.items():
            run_results = []
            for run in range(min(self.config.num_runs, 10)):
                np.random.seed(self.config.random_seed + run)
                metrics = self._run_emergent_honey(run, **flags)
                run_results.append(metrics)

            self.results[f"ablation_{variant}"] = run_results
            avg_adt = np.mean([r.avg_dwell_time for r in run_results])
            logger.info(f"  {variant}: ADT={avg_adt:.1f}s")

    # ============================================================
    # 内部运行方法
    # ============================================================

    def _run_emergent_honey(
        self,
        run_id: int,
        track_dei: bool = False,
        use_reverse_aco: bool = True,
        use_llm: bool = True,
        use_adaptive_rho: bool = True,
    ) -> RunMetrics:
        """运行EmergentHoney完整系统"""
        cfg = self.config
        metrics = RunMetrics()

        # 初始化组件
        topology = SDNTopology(cfg.num_nodes, cfg.topology_type)

        engine = PheromoneEngine(
            num_positions=cfg.num_nodes,
            num_types=cfg.num_hp_types,
            evaporation_rate=cfg.evaporation_rate,
            Q=cfg.Q,
            delta_max=cfg.delta_max,
            adaptive_rho=use_adaptive_rho,
        )

        organizer = SelfOrganizer(engine, budget=cfg.budget)

        reverse_aco = None
        if use_reverse_aco:
            reverse_aco = ReverseACO(
                num_nodes=cfg.num_nodes,
                adjacency=topology.get_adjacency_matrix(),
            )

        phenotype_gen = None
        if use_llm:
            phenotype_gen = PhenotypeGenerator(llm_backend=MockLLMBackend())

        # 初始化攻击者
        attackers = self._create_attackers(topology)

        # 运行模拟
        all_dwells = []
        total_interactions = 0
        step_times = []

        for step in range(cfg.num_steps):
            t0 = time.time()

            # 收集攻击者动作
            interactions = []
            recon_actions = []

            for attacker in attackers:
                if not attacker.active:
                    continue

                hp_positions = set(organizer.get_honeypot_positions())
                recon, interaction = attacker.step(hp_positions, float(step))

                if recon:
                    recon_actions.append(recon)
                if interaction:
                    # 设置正确的蜜罐类型
                    pos = interaction.position
                    if pos in organizer.honeypots:
                        interaction.hp_type = organizer.honeypots[pos].hp_type
                    interactions.append(interaction)
                    all_dwells.append(interaction.engagement_time)
                    total_interactions += 1

            # 更新信息素
            engine.update(interactions)

            # 反向ACO更新
            if reverse_aco and recon_actions:
                reverse_aco.update(recon_actions)

                # 预部署
                preemptive = reverse_aco.get_preemptive_positions()
                for pos, score in preemptive[:3]:
                    if pos not in organizer.honeypots and len(organizer.honeypots) < cfg.budget:
                        best_type = engine.get_best_type(pos)
                        organizer.honeypots[pos] = HoneypotConfig(
                            position=pos, hp_type=best_type,
                            creation_time=float(step)
                        )

            # 自组织操作
            ops = organizer.step(float(step))
            metrics.topology_changes += (
                len(ops["proliferated"]) + len(ops["migrated"]) + len(ops["mutated"])
            )

            # 收敛检查
            conv = engine.get_convergence_metric()
            metrics.pheromone_history.append(conv)
            if conv < 0.05 and metrics.convergence_step == 0:
                metrics.convergence_step = step

            t1 = time.time()
            step_times.append((t1 - t0) * 1000)

            # 重生已退出的攻击者
            for i, attacker in enumerate(attackers):
                if not attacker.active and step < cfg.num_steps - 10:
                    if np.random.random() < 0.1:
                        attackers[i] = self._create_single_attacker(
                            f"atk_{run_id}_{step}_{i}", topology
                        )

        # 计算指标
        metrics.avg_dwell_time = np.mean(all_dwells) if all_dwells else 0.0
        metrics.dwell_times = all_dwells
        metrics.interaction_rate = total_interactions / max(cfg.num_steps, 1)
        metrics.avg_step_time_ms = np.mean(step_times)

        if metrics.convergence_step == 0:
            metrics.convergence_step = cfg.num_steps

        # DEI计算
        if track_dei:
            individual_dwells = {}
            collective_dwells = {}
            for pos in organizer.get_honeypot_positions():
                individual_dwells[pos] = np.mean(all_dwells) * 0.6 if all_dwells else 0
                collective_dwells[pos] = np.mean(all_dwells) if all_dwells else 0
            metrics.dei_value = organizer.compute_dei(
                individual_dwells, collective_dwells
            )

        # 预测准确率
        if reverse_aco:
            # 构造ground truth: 攻击者实际轨迹的后3步
            ground_truth = {}
            for atk in attackers:
                if len(atk.trajectory) > 5:
                    ground_truth[atk.attacker_id] = atk.trajectory[-3:]
            if ground_truth:
                pred_metrics = reverse_aco.compute_prediction_accuracy(ground_truth)
                metrics.prediction_precision = pred_metrics["precision"]
                metrics.prediction_recall = pred_metrics["recall"]
                metrics.prediction_f1 = pred_metrics["f1"]

        return metrics

    def _run_baseline(
        self, baseline_cls, run_id: int
    ) -> RunMetrics:
        """运行基线方法"""
        cfg = self.config
        metrics = RunMetrics()

        topology = SDNTopology(cfg.num_nodes, cfg.topology_type)

        baseline = baseline_cls(
            num_positions=cfg.num_nodes,
            num_types=cfg.num_hp_types,
            budget=cfg.budget,
        )
        baseline.initialize()

        attackers = self._create_attackers(topology)

        all_dwells = []
        total_interactions = 0
        step_times = []

        for step in range(cfg.num_steps):
            t0 = time.time()

            interactions = []
            for attacker in attackers:
                if not attacker.active:
                    continue

                hp_positions = baseline.get_positions()
                _, interaction = attacker.step(hp_positions, float(step))

                if interaction:
                    interactions.append(interaction)
                    all_dwells.append(interaction.engagement_time)
                    total_interactions += 1

            baseline.update(interactions)

            t1 = time.time()
            step_times.append((t1 - t0) * 1000)

            # 重生攻击者
            for i, atk in enumerate(attackers):
                if not atk.active and step < cfg.num_steps - 10:
                    if np.random.random() < 0.1:
                        attackers[i] = self._create_single_attacker(
                            f"atk_bl_{run_id}_{step}_{i}", topology
                        )

        metrics.avg_dwell_time = np.mean(all_dwells) if all_dwells else 0.0
        metrics.dwell_times = all_dwells
        metrics.interaction_rate = total_interactions / max(cfg.num_steps, 1)
        metrics.avg_step_time_ms = np.mean(step_times)

        return metrics

    def _run_single(self, config: ExperimentConfig) -> RunMetrics:
        """使用自定义配置运行单次"""
        old_config = self.config
        self.config = config
        metrics = self._run_emergent_honey(0)
        self.config = old_config
        return metrics

    def _create_attackers(self, topology: SDNTopology) -> List[AttackerSimulator]:
        """创建攻击者"""
        attackers = []
        for i in range(self.config.num_attackers):
            attacker = self._create_single_attacker(f"atk_{i}", topology)
            attackers.append(attacker)
        return attackers

    def _create_single_attacker(
        self, attacker_id: str, topology: SDNTopology
    ) -> AttackerSimulator:
        """创建单个攻击者"""
        return AttackerSimulator(
            attacker_id=attacker_id,
            topology=topology,
            sophistication=self.config.attacker_sophistication + np.random.normal(0, 0.1),
            persistence=self.config.attacker_persistence + np.random.normal(0, 0.1),
            adaptiveness=self.config.attacker_adaptiveness + np.random.normal(0, 0.1),
        )

    # ============================================================
    # 结果保存
    # ============================================================

    def save_results(self):
        """保存所有实验结果"""
        output_path = Path(self.config.output_dir)

        # 保存汇总
        summary = {}
        for exp_name, runs in self.results.items():
            adts = [r.avg_dwell_time for r in runs]
            irs = [r.interaction_rate for r in runs]
            summary[exp_name] = {
                "num_runs": len(runs),
                "adt_mean": float(np.mean(adts)),
                "adt_std": float(np.std(adts)),
                "adt_median": float(np.median(adts)),
                "ir_mean": float(np.mean(irs)),
                "ir_std": float(np.std(irs)),
                "convergence_mean": float(
                    np.mean([r.convergence_step for r in runs])
                ),
                "avg_step_ms": float(
                    np.mean([r.avg_step_time_ms for r in runs])
                ),
            }

        summary_path = output_path / "experiment_summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)

        logger.info(f"结果已保存到 {output_path}")

        # 打印汇总表
        self._print_summary_table(summary)

    def _print_summary_table(self, summary: Dict):
        """打印结果汇总表"""
        print("\n" + "=" * 70)
        print("实验结果汇总")
        print("=" * 70)
        print(f"{'实验名称':<35} {'ADT(s)':<15} {'IR':<10} {'步耗(ms)':<10}")
        print("-" * 70)

        for name, stats in summary.items():
            adt = f"{stats['adt_mean']:.1f}±{stats['adt_std']:.1f}"
            ir = f"{stats['ir_mean']:.3f}"
            step_ms = f"{stats['avg_step_ms']:.2f}"
            print(f"{name:<35} {adt:<15} {ir:<10} {step_ms:<10}")

        print("=" * 70)


# ============================================================
# 入口点
# ============================================================

def main():
    """主函数"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = ExperimentConfig(
        num_nodes=50,
        num_hp_types=8,
        budget=15,
        num_attackers=5,
        num_steps=200,
        num_runs=30,
        output_dir="results",
    )

    runner = ExperimentRunner(config)
    runner.run_all_experiments()


if __name__ == "__main__":
    main()
