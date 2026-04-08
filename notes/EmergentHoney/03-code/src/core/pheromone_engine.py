"""
EmergentHoney 核心模块：信息素引擎
实现论文 Section IV-A 的信息素更新规则与自组织算法 (Algorithm 1)
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class HoneypotConfig:
    """蜜罐配置"""
    position: int           # 网络位置 (节点ID)
    hp_type: int            # 蜜罐类型索引
    phenotype_id: str = ""  # LLM生成的表型ID
    creation_time: float = 0.0


@dataclass
class AttackerInteraction:
    """攻击者交互记录"""
    attacker_id: str
    position: int
    hp_type: int
    engagement_time: float    # 驻留时间 (秒)
    detection_risk: float     # 被识别风险 [0,1]
    techniques_observed: List[str] = field(default_factory=list)  # MITRE ATT&CK技术
    timestamp: float = 0.0


class PheromoneEngine:
    """
    信息素引擎 — EmergentHoney 的核心组件

    实现公式:
    τ_{ij}(t+1) = (1 - ρ) · τ_{ij}(t) + Σ_k Δτ_{ij}^k(t)

    其中 Δτ_{ij}^k = Q · engagement(k,i,t) / detection_risk(k,i,t)
    """

    def __init__(
        self,
        num_positions: int,
        num_types: int,
        evaporation_rate: float = 0.05,
        Q: float = 100.0,
        delta_max: float = 50.0,
        initial_pheromone: float = 1.0,
        adaptive_rho: bool = True,
        rho_sensitivity: float = 0.1,
    ):
        """
        Args:
            num_positions: 网络节点数量 |V|
            num_types: 蜜罐类型数量 |H|
            evaporation_rate: 蒸发率 ρ ∈ (0,1)
            Q: 信息素沉积常数
            delta_max: 最大单次沉积量 Δ_max
            initial_pheromone: 初始信息素值
            adaptive_rho: 是否启用自适应蒸发率
            rho_sensitivity: 自适应蒸发率灵敏度 σ
        """
        self.num_positions = num_positions
        self.num_types = num_types
        self.rho = evaporation_rate
        self.rho_base = evaporation_rate
        self.Q = Q
        self.delta_max = delta_max
        self.adaptive_rho = adaptive_rho
        self.rho_sensitivity = rho_sensitivity

        # 信息素矩阵 T(t) ∈ R^{|V| × |H|}
        self.tau = np.full((num_positions, num_types), initial_pheromone, dtype=np.float64)

        # 历史记录 (用于自适应蒸发率)
        self.interaction_history: List[AttackerInteraction] = []
        self.pheromone_history: List[np.ndarray] = []
        self.time_step = 0

    def update(self, interactions: List[AttackerInteraction]) -> np.ndarray:
        """
        执行一步信息素更新 (公式 2-3)

        Args:
            interactions: 当前时步的攻击者交互列表

        Returns:
            更新后的信息素矩阵
        """
        # 保存历史
        self.pheromone_history.append(self.tau.copy())
        self.interaction_history.extend(interactions)

        # 步骤1: 蒸发 (公式 2 第一项)
        self.tau *= (1 - self.rho)

        # 步骤2: 沉积 (公式 2 第二项 + 公式 3)
        for interaction in interactions:
            i = interaction.position
            j = interaction.hp_type

            if 0 <= i < self.num_positions and 0 <= j < self.num_types:
                # Δτ_{ij}^k = Q · engagement / detection_risk
                detection_risk = max(interaction.detection_risk, 0.01)  # 防止除零
                delta = self.Q * interaction.engagement_time / detection_risk

                # 截断到 [0, delta_max] (Assumption 1)
                delta = np.clip(delta, 0, self.delta_max)

                self.tau[i, j] += delta

        # 步骤3: 自适应蒸发率更新
        if self.adaptive_rho and len(self.pheromone_history) >= 2:
            self._adapt_evaporation_rate()

        self.time_step += 1
        return self.tau.copy()

    def _adapt_evaporation_rate(self):
        """
        自适应蒸发率: ρ(t) = ρ_0 · (1 + σ · attack_variability(t))
        """
        if len(self.interaction_history) < 10:
            return

        # 计算最近的攻击变异性 (位置分布的熵变化)
        recent = self.interaction_history[-50:]
        positions = [x.position for x in recent]

        if len(set(positions)) <= 1:
            variability = 0.0
        else:
            hist, _ = np.histogram(positions, bins=min(20, self.num_positions),
                                   range=(0, self.num_positions))
            hist = hist / hist.sum()
            hist = hist[hist > 0]
            entropy = -np.sum(hist * np.log(hist + 1e-10))
            max_entropy = np.log(min(20, self.num_positions))
            variability = entropy / max_entropy  # 归一化到 [0, 1]

        self.rho = self.rho_base * (1 + self.rho_sensitivity * variability)
        self.rho = np.clip(self.rho, 0.01, 0.5)

    def get_best_type(self, position: int) -> int:
        """获取位置i的最优蜜罐类型: j*(i) = argmax_j τ_{ij}"""
        return int(np.argmax(self.tau[position, :]))

    def get_max_pheromone(self, position: int) -> float:
        """获取位置i的最大信息素值: τ_max(i) = max_j τ_{ij}"""
        return float(np.max(self.tau[position, :]))

    def get_pheromone_distribution(self) -> np.ndarray:
        """返回每个位置的最大信息素值向量"""
        return np.max(self.tau, axis=1)

    def get_convergence_metric(self) -> float:
        """
        计算收敛指标: 相邻时步信息素分布变化率
        当变化率 < 5% 时认为已收敛
        """
        if len(self.pheromone_history) < 2:
            return 1.0

        prev = self.pheromone_history[-1]
        curr = self.tau

        prev_norm = np.linalg.norm(prev)
        if prev_norm < 1e-10:
            return 1.0

        change = np.linalg.norm(curr - prev) / prev_norm
        return float(change)

    @property
    def theoretical_upper_bound(self) -> float:
        """Lemma 1: τ 上界 = |A|_max · Δ_max / ρ"""
        # 假设最大同时攻击者数为交互历史中观察到的最大值
        if not self.interaction_history:
            return self.delta_max / self.rho

        # 按时间窗口统计
        max_concurrent = 10  # 默认估计
        return max_concurrent * self.delta_max / self.rho


class SelfOrganizer:
    """
    自组织管理器 — 实现 Algorithm 1

    三种操作:
    1. Proliferation (增殖): 在高信息素区域部署新蜜罐
    2. Migration (迁移): 将低信息素蜜罐移动到高信息素空位
    3. Mutation (变异): 改变中等信息素蜜罐的类型
    """

    def __init__(
        self,
        pheromone_engine: PheromoneEngine,
        budget: int,
        theta_prolif: float = 0.7,
        theta_migrate: float = 0.2,
        theta_mutate: float = 0.5,
    ):
        """
        Args:
            pheromone_engine: 信息素引擎实例
            budget: 蜜罐总预算 B
            theta_prolif: 增殖阈值 (相对于τ_max的比例)
            theta_migrate: 迁移阈值 (相对于τ_max的比例)
            theta_mutate: 变异阈值 (相对于τ_max的比例)
        """
        self.engine = pheromone_engine
        self.budget = budget
        self.theta_prolif_ratio = theta_prolif
        self.theta_migrate_ratio = theta_migrate
        self.theta_mutate_ratio = theta_mutate

        # 当前蜜罐集合
        self.honeypots: Dict[int, HoneypotConfig] = {}

        # 操作日志
        self.operation_log: List[Dict] = []

    def step(self, current_time: float) -> Dict[str, List]:
        """
        执行一步自组织 (Algorithm 1)

        Returns:
            操作记录 {"proliferated": [...], "migrated": [...], "mutated": [...]}
        """
        pheromone_dist = self.engine.get_pheromone_distribution()
        global_max = np.max(pheromone_dist) if np.max(pheromone_dist) > 0 else 1.0

        # 动态阈值 (基于全局信息素)
        theta_prolif = self.theta_prolif_ratio * global_max
        theta_migrate = self.theta_migrate_ratio * global_max
        theta_mutate = self.theta_mutate_ratio * global_max

        result = {"proliferated": [], "migrated": [], "mutated": []}

        occupied = set(self.honeypots.keys())

        # ===== 1. PROLIFERATION (Lines 6-12) =====
        vacant_high = []
        for i in range(self.engine.num_positions):
            if i not in occupied and pheromone_dist[i] > theta_prolif:
                vacant_high.append((i, pheromone_dist[i]))

        # 按信息素降序排列
        vacant_high.sort(key=lambda x: x[1], reverse=True)

        for pos, _ in vacant_high:
            if len(self.honeypots) >= self.budget:
                break

            best_type = self.engine.get_best_type(pos)
            new_hp = HoneypotConfig(
                position=pos,
                hp_type=best_type,
                creation_time=current_time
            )
            self.honeypots[pos] = new_hp
            result["proliferated"].append(new_hp)
            occupied.add(pos)

            logger.info(f"[PROLIFERATE] t={current_time:.1f} 部署蜜罐 位置={pos} 类型={best_type}")

        # ===== 2. MIGRATION (Lines 14-20) =====
        low_pheromone_hps = []
        for pos, hp in self.honeypots.items():
            if pheromone_dist[pos] < theta_migrate:
                low_pheromone_hps.append((pos, hp, pheromone_dist[pos]))

        low_pheromone_hps.sort(key=lambda x: x[2])  # 最低信息素优先迁移

        for old_pos, hp, old_pher in low_pheromone_hps:
            # 找最优空位
            best_vacant = -1
            best_pher = old_pher

            for i in range(self.engine.num_positions):
                if i not in occupied and pheromone_dist[i] > best_pher:
                    best_vacant = i
                    best_pher = pheromone_dist[i]

            if best_vacant >= 0:
                # 执行迁移
                new_type = self.engine.get_best_type(best_vacant)
                del self.honeypots[old_pos]
                occupied.discard(old_pos)

                new_hp = HoneypotConfig(
                    position=best_vacant,
                    hp_type=new_type,
                    creation_time=current_time
                )
                self.honeypots[best_vacant] = new_hp
                occupied.add(best_vacant)

                result["migrated"].append({
                    "from": old_pos, "to": best_vacant,
                    "old_type": hp.hp_type, "new_type": new_type
                })

                logger.info(f"[MIGRATE] t={current_time:.1f} {old_pos}->{best_vacant} 类型={new_type}")

        # ===== 3. MUTATION (Lines 22-28) =====
        for pos, hp in list(self.honeypots.items()):
            pher_val = pheromone_dist[pos]
            if theta_migrate <= pher_val <= theta_mutate:
                # 轮盘赌选择新类型
                type_pheromones = self.engine.tau[pos, :]
                probs = type_pheromones / (type_pheromones.sum() + 1e-10)

                new_type = np.random.choice(self.engine.num_types, p=probs)

                if new_type != hp.hp_type:
                    old_type = hp.hp_type
                    hp.hp_type = new_type

                    result["mutated"].append({
                        "position": pos, "old_type": old_type, "new_type": new_type
                    })

                    logger.info(f"[MUTATE] t={current_time:.1f} 位置={pos} {old_type}->{new_type}")

        self.operation_log.append({
            "time": current_time,
            "operations": result,
            "num_honeypots": len(self.honeypots)
        })

        return result

    def compute_dei(self, individual_dwells: Dict[int, float],
                    collective_dwells: Dict[int, float]) -> float:
        """
        计算 Deception Emergence Index (公式 7)

        Args:
            individual_dwells: {hp_id: 独立驻留时间} (每个蜜罐单独部署时)
            collective_dwells: {hp_id: 集群驻留时间} (所有蜜罐协同运行时)

        Returns:
            DEI值
        """
        sum_individual = sum(individual_dwells.values())
        sum_collective = sum(collective_dwells.values())

        if sum_individual <= 0:
            return 1.0

        dei = sum_collective / sum_individual
        return dei

    def get_honeypot_positions(self) -> List[int]:
        """返回当前所有蜜罐位置"""
        return list(self.honeypots.keys())

    def get_honeypot_types(self) -> Dict[int, int]:
        """返回 {位置: 类型} 映射"""
        return {pos: hp.hp_type for pos, hp in self.honeypots.items()}
