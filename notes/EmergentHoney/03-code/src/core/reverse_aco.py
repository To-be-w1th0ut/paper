"""
EmergentHoney 核心模块：反向蚁群攻击者建模
实现论文 Section IV-C 的反向信息素模型 (Algorithm 2)
"""

import numpy as np
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ReconAction:
    """攻击者侦察动作"""
    attacker_id: str
    source: int           # 来源节点
    target: int           # 目标节点
    action_type: str      # 动作类型: port_scan, service_probe, lateral_move, exploit
    timestamp: float
    success: bool = False
    techniques: List[str] = field(default_factory=list)  # MITRE ATT&CK 技术ID


@dataclass
class AttackerProfile:
    """攻击者画像 (由反向信息素推断)"""
    attacker_id: str
    trajectory: List[int]           # 访问路径
    predicted_targets: List[int]    # 预测下一步目标
    confidence: float               # 预测置信度
    attack_phase: str               # 当前攻击阶段: recon, initial_access, lateral, exfil
    techniques_used: Set[str] = field(default_factory=set)


class ReverseACO:
    """
    反向蚁群攻击者建模 — Algorithm 2

    核心思想：将攻击者侦察轨迹视为反向蚂蚁觅食路径，
    攻击者的信息素 φ_{ij}(t) 编码从节点i到节点j的攻击转移概率。

    公式:
    φ_{ij}(t+1) = (1 - ρ_a) · φ_{ij}(t) + Σ_k Δφ_{ij}^k(t)

    其中 Δφ_{ij}^k = 1/path_length(k)  (攻击者k经过边(i,j)时)

    预测公式:
    P(target=j | current=i) = φ_{ij}^α · η_{ij}^β / Σ_l [φ_{il}^α · η_{il}^β]

    其中 η_{ij} 为启发式信息 (基于网络拓扑的先验吸引力)
    """

    def __init__(
        self,
        num_nodes: int,
        adjacency: Optional[np.ndarray] = None,
        evaporation_rate: float = 0.1,
        alpha: float = 1.0,
        beta: float = 2.0,
        initial_pheromone: float = 0.1,
        prediction_horizon: int = 3,
        preemptive_budget: int = 5,
    ):
        """
        Args:
            num_nodes: 网络节点数量 |V|
            adjacency: 邻接矩阵 A ∈ {0,1}^{|V|×|V|}，None则默认全连接
            evaporation_rate: 攻击者信息素蒸发率 ρ_a
            alpha: 信息素权重指数 α
            beta: 启发式信息权重指数 β
            initial_pheromone: 初始攻击者信息素
            prediction_horizon: 预测步数 (向前预测几步)
            preemptive_budget: 预部署蜜罐预算
        """
        self.num_nodes = num_nodes
        self.alpha = alpha
        self.beta = beta
        self.rho_a = evaporation_rate
        self.prediction_horizon = prediction_horizon
        self.preemptive_budget = preemptive_budget

        # 邻接矩阵
        if adjacency is not None:
            self.adjacency = adjacency.astype(np.float64)
        else:
            self.adjacency = np.ones((num_nodes, num_nodes), dtype=np.float64)
            np.fill_diagonal(self.adjacency, 0)

        # 攻击者信息素矩阵 Φ(t) ∈ R^{|V|×|V|}
        self.phi = np.full(
            (num_nodes, num_nodes), initial_pheromone, dtype=np.float64
        )
        # 仅保留邻接边上的信息素
        self.phi *= self.adjacency

        # 启发式信息 η_{ij} — 基于节点度和资产价值
        self.eta = self._compute_heuristic()

        # 攻击者轨迹记录
        self.attacker_trajectories: Dict[str, List[int]] = defaultdict(list)
        self.attacker_actions: Dict[str, List[ReconAction]] = defaultdict(list)

        # 预测历史
        self.prediction_history: List[Dict] = []
        self.time_step = 0

    def _compute_heuristic(self) -> np.ndarray:
        """
        计算启发式信息 η_{ij}

        高度数节点和高价值资产具有更高的先验吸引力
        η_{ij} = degree(j) / max_degree  (可以扩展为更复杂的资产价值模型)
        """
        degrees = self.adjacency.sum(axis=0)
        max_degree = max(degrees.max(), 1.0)

        eta = np.zeros_like(self.adjacency)
        for j in range(self.num_nodes):
            eta[:, j] = degrees[j] / max_degree

        # 仅保留邻接边
        eta *= self.adjacency
        # 确保非零 (防止概率计算除零)
        eta = np.maximum(eta, 0.01)
        return eta

    def record_action(self, action: ReconAction):
        """
        记录攻击者侦察动作

        Args:
            action: 侦察动作记录
        """
        self.attacker_actions[action.attacker_id].append(action)

        trajectory = self.attacker_trajectories[action.attacker_id]
        if not trajectory or trajectory[-1] != action.source:
            trajectory.append(action.source)
        trajectory.append(action.target)

        logger.debug(
            f"[RECON] 攻击者={action.attacker_id} "
            f"{action.source}->{action.target} "
            f"类型={action.action_type}"
        )

    def update(self, actions: List[ReconAction]) -> np.ndarray:
        """
        执行一步攻击者信息素更新 (Algorithm 2, Lines 3-8)

        Args:
            actions: 当前时步的侦察动作列表

        Returns:
            更新后的攻击者信息素矩阵
        """
        # 记录所有动作
        for action in actions:
            self.record_action(action)

        # 步骤1: 蒸发
        self.phi *= (1 - self.rho_a)

        # 步骤2: 沉积 — 基于攻击者轨迹
        # 提取当前活跃攻击者
        active_attackers = set(a.attacker_id for a in actions)

        for attacker_id in active_attackers:
            trajectory = self.attacker_trajectories[attacker_id]
            if len(trajectory) < 2:
                continue

            # Δφ_{ij}^k = 1 / path_length(k)
            path_length = len(trajectory) - 1
            delta = 1.0 / path_length

            # 沿轨迹的每条边沉积
            for idx in range(len(trajectory) - 1):
                i = trajectory[idx]
                j = trajectory[idx + 1]
                if 0 <= i < self.num_nodes and 0 <= j < self.num_nodes:
                    self.phi[i, j] += delta

        # 保持邻接约束
        self.phi *= self.adjacency

        self.time_step += 1
        return self.phi.copy()

    def predict_targets(self, attacker_id: str) -> AttackerProfile:
        """
        预测攻击者下一步目标 (Algorithm 2, Lines 10-18)

        使用转移概率:
        P(j|i) = φ_{ij}^α · η_{ij}^β / Σ_l [φ_{il}^α · η_{il}^β]

        Args:
            attacker_id: 攻击者ID

        Returns:
            攻击者画像 (含预测目标)
        """
        trajectory = self.attacker_trajectories.get(attacker_id, [])

        if not trajectory:
            return AttackerProfile(
                attacker_id=attacker_id,
                trajectory=[],
                predicted_targets=[],
                confidence=0.0,
                attack_phase="unknown"
            )

        current_node = trajectory[-1]
        predicted = []
        confidences = []

        # 多步前瞻预测
        node = current_node
        visited = set(trajectory)

        for step in range(self.prediction_horizon):
            probs = self._transition_probabilities(node, visited)

            if probs is None or probs.sum() < 1e-10:
                break

            # 选取top-K候选
            top_k = min(3, (probs > 0).sum())
            top_indices = np.argsort(probs)[-top_k:][::-1]

            for idx in top_indices:
                if probs[idx] > 0.01 and idx not in visited:
                    predicted.append(int(idx))
                    confidences.append(float(probs[idx]))

            # 使用最可能的下一步继续预测
            next_node = int(np.argmax(probs))
            if probs[next_node] < 0.01:
                break
            visited.add(next_node)
            node = next_node

        # 去重并保持顺序
        seen = set()
        unique_predicted = []
        unique_confidences = []
        for p, c in zip(predicted, confidences):
            if p not in seen:
                seen.add(p)
                unique_predicted.append(p)
                unique_confidences.append(c)

        # 判断攻击阶段
        attack_phase = self._infer_attack_phase(attacker_id)

        # 整体置信度
        overall_confidence = np.mean(unique_confidences) if unique_confidences else 0.0

        # 收集使用的技术
        techniques = set()
        for action in self.attacker_actions.get(attacker_id, []):
            techniques.update(action.techniques)

        profile = AttackerProfile(
            attacker_id=attacker_id,
            trajectory=trajectory.copy(),
            predicted_targets=unique_predicted[:self.preemptive_budget],
            confidence=overall_confidence,
            attack_phase=attack_phase,
            techniques_used=techniques
        )

        self.prediction_history.append({
            "time_step": self.time_step,
            "attacker_id": attacker_id,
            "predicted": unique_predicted,
            "confidence": overall_confidence,
            "phase": attack_phase
        })

        return profile

    def _transition_probabilities(
        self, node: int, visited: Set[int]
    ) -> Optional[np.ndarray]:
        """
        计算从node出发的转移概率分布

        P(j|i) = φ_{ij}^α · η_{ij}^β / Σ_l [φ_{il}^α · η_{il}^β]
        """
        if node < 0 or node >= self.num_nodes:
            return None

        # 信息素 × 启发式
        phi_row = self.phi[node, :].copy()
        eta_row = self.eta[node, :].copy()

        # 屏蔽已访问节点 (攻击者倾向于探索新节点)
        for v in visited:
            if 0 <= v < self.num_nodes:
                phi_row[v] *= 0.1  # 降低但不完全屏蔽 (允许回溯)

        # 计算概率
        numerator = (phi_row ** self.alpha) * (eta_row ** self.beta)
        denominator = numerator.sum()

        if denominator < 1e-10:
            return None

        return numerator / denominator

    def _infer_attack_phase(self, attacker_id: str) -> str:
        """
        基于行为模式推断攻击阶段

        - recon: 主要是扫描和探测
        - initial_access: 尝试利用漏洞
        - lateral: 横向移动
        - exfil: 数据窃取
        """
        actions = self.attacker_actions.get(attacker_id, [])
        if not actions:
            return "unknown"

        action_types = [a.action_type for a in actions[-20:]]  # 最近20个动作

        type_counts = defaultdict(int)
        for at in action_types:
            type_counts[at] += 1

        total = len(action_types)
        scan_ratio = type_counts.get("port_scan", 0) / total
        probe_ratio = type_counts.get("service_probe", 0) / total
        lateral_ratio = type_counts.get("lateral_move", 0) / total
        exploit_ratio = type_counts.get("exploit", 0) / total

        if scan_ratio > 0.5:
            return "recon"
        elif exploit_ratio > 0.3:
            return "initial_access"
        elif lateral_ratio > 0.3:
            return "lateral"
        elif probe_ratio > 0.4:
            return "recon"
        else:
            return "lateral"

    def get_preemptive_positions(self) -> List[Tuple[int, float]]:
        """
        获取预部署位置 (Algorithm 2, Lines 20-25)

        基于所有活跃攻击者的预测，选择最需要预部署蜜罐的位置

        Returns:
            [(position, urgency_score), ...] 按紧急度降序排列
        """
        position_scores: Dict[int, float] = defaultdict(float)

        for attacker_id in self.attacker_trajectories:
            profile = self.predict_targets(attacker_id)

            for idx, target in enumerate(profile.predicted_targets):
                # 紧急度 = 置信度 × 距离衰减
                decay = 1.0 / (1 + idx)
                score = profile.confidence * decay
                position_scores[target] += score

        # 按得分排序
        ranked = sorted(
            position_scores.items(), key=lambda x: x[1], reverse=True
        )

        return ranked[:self.preemptive_budget]

    def get_attack_graph(self) -> np.ndarray:
        """
        返回攻击图 (基于攻击者信息素的加权有向图)
        边权重 = 归一化攻击者信息素

        Returns:
            归一化攻击者信息素矩阵 ∈ [0,1]^{|V|×|V|}
        """
        max_phi = self.phi.max()
        if max_phi < 1e-10:
            return self.phi.copy()
        return self.phi / max_phi

    def get_hotspot_nodes(self, top_k: int = 5) -> List[Tuple[int, float]]:
        """
        获取攻击热点节点 (入度信息素最高的节点)

        Args:
            top_k: 返回前k个热点

        Returns:
            [(node_id, incoming_pheromone), ...]
        """
        incoming = self.phi.sum(axis=0)  # 每个节点的入度信息素总和
        top_indices = np.argsort(incoming)[-top_k:][::-1]

        return [(int(idx), float(incoming[idx])) for idx in top_indices]

    def compute_prediction_accuracy(
        self, ground_truth: Dict[str, List[int]]
    ) -> Dict[str, float]:
        """
        计算预测准确率 (用于实验评估)

        Args:
            ground_truth: {attacker_id: [实际访问节点列表]}

        Returns:
            {precision, recall, f1, hit_rate}
        """
        total_predicted = 0
        total_actual = 0
        total_hits = 0

        for attacker_id, actual_targets in ground_truth.items():
            profile = self.predict_targets(attacker_id)
            predicted_set = set(profile.predicted_targets)
            actual_set = set(actual_targets)

            hits = len(predicted_set & actual_set)
            total_hits += hits
            total_predicted += len(predicted_set)
            total_actual += len(actual_set)

        precision = total_hits / max(total_predicted, 1)
        recall = total_hits / max(total_actual, 1)
        f1 = (
            2 * precision * recall / max(precision + recall, 1e-10)
        )
        hit_rate = total_hits / max(total_actual, 1)

        return {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "hit_rate": hit_rate,
        }
