"""
EmergentHoney 网络模块：SDN网络拓扑管理
实现论文 Section VI-A 的实验环境 (SDN-based testbed)
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class NodeRole(Enum):
    """网络节点角色"""
    NORMAL = "normal"          # 普通主机
    SERVER = "server"          # 服务器
    HONEYPOT = "honeypot"      # 蜜罐
    SWITCH = "switch"          # SDN交换机
    CONTROLLER = "controller"  # SDN控制器
    ATTACKER = "attacker"      # 攻击者入口


@dataclass
class NetworkNode:
    """网络节点"""
    node_id: int
    ip: str
    mac: str
    role: NodeRole
    subnet: int                # 子网ID
    services: List[int] = field(default_factory=list)  # 开放端口列表
    is_honeypot: bool = False
    value: float = 1.0         # 资产价值 (用于启发式信息)


@dataclass
class NetworkLink:
    """网络链路"""
    src: int
    dst: int
    bandwidth: float = 1000.0  # Mbps
    latency: float = 1.0       # ms
    is_monitored: bool = False


class SDNTopology:
    """
    SDN网络拓扑管理器

    支持多种拓扑结构:
    - enterprise: 企业网络 (核心-汇聚-接入三层)
    - datacenter: 数据中心 (Fat-Tree / Leaf-Spine)
    - campus: 校园网
    - custom: 自定义邻接矩阵

    论文实验使用:
    - Small: |V|=50, |E|≈150
    - Medium: |V|=200, |E|≈800
    - Large: |V|=500, |E|≈2500
    """

    def __init__(self, num_nodes: int = 50, topology_type: str = "enterprise"):
        """
        Args:
            num_nodes: 节点数量
            topology_type: 拓扑类型
        """
        self.num_nodes = num_nodes
        self.topology_type = topology_type

        # 节点和链路
        self.nodes: Dict[int, NetworkNode] = {}
        self.links: List[NetworkLink] = []

        # 邻接矩阵
        self.adjacency = np.zeros((num_nodes, num_nodes), dtype=np.float64)

        # 子网信息
        self.subnets: Dict[int, List[int]] = {}

        # 构建拓扑
        self._build_topology()

    def _build_topology(self):
        """根据拓扑类型构建网络"""
        if self.topology_type == "enterprise":
            self._build_enterprise()
        elif self.topology_type == "datacenter":
            self._build_datacenter()
        elif self.topology_type == "campus":
            self._build_campus()
        else:
            self._build_random()

    def _build_enterprise(self):
        """
        构建企业网络拓扑

        结构:
        - DMZ子网 (10%节点): Web服务器、邮件服务器
        - 办公子网 (50%节点): 工作站
        - 服务器子网 (20%节点): 数据库、文件服务器
        - 管理子网 (10%节点): 管理服务器
        - 核心路由 (10%节点): 交换机和路由器

        每个子网内部全连接，子网间通过核心路由连接
        """
        n = self.num_nodes

        # 划分子网
        dmz_size = max(int(n * 0.10), 2)
        office_size = max(int(n * 0.50), 5)
        server_size = max(int(n * 0.20), 3)
        mgmt_size = max(int(n * 0.10), 2)
        core_size = n - dmz_size - office_size - server_size - mgmt_size

        offset = 0
        subnet_ranges = {
            0: (offset, offset + dmz_size),           # DMZ
            1: (offset := offset + dmz_size, offset + office_size),  # 办公
            2: (offset := offset + office_size, offset + server_size),  # 服务器
            3: (offset := offset + server_size, offset + mgmt_size),   # 管理
            4: (offset := offset + mgmt_size, offset + core_size),     # 核心
        }

        subnet_names = {0: "DMZ", 1: "Office", 2: "Server", 3: "Management", 4: "Core"}

        # 创建节点
        for subnet_id, (start, end) in subnet_ranges.items():
            self.subnets[subnet_id] = list(range(start, end))

            for i in range(start, end):
                # 分配角色
                if subnet_id == 0:
                    role = NodeRole.SERVER
                    services = [80, 443, 25]
                elif subnet_id == 1:
                    role = NodeRole.NORMAL
                    services = [22]
                elif subnet_id == 2:
                    role = NodeRole.SERVER
                    services = [3306, 5432, 445, 22]
                elif subnet_id == 3:
                    role = NodeRole.SERVER
                    services = [22, 3389, 8080]
                else:
                    role = NodeRole.SWITCH
                    services = []

                node = NetworkNode(
                    node_id=i,
                    ip=f"10.{subnet_id}.{i // 256}.{i % 256}",
                    mac=f"02:{subnet_id:02x}:{i:04x}".replace("x", "0")[:17],
                    role=role,
                    subnet=subnet_id,
                    services=services,
                    value=self._compute_node_value(role, subnet_id),
                )
                self.nodes[i] = node

        # 子网内部连接 (随机稀疏连接，不全连接以提高真实性)
        for subnet_id, node_ids in self.subnets.items():
            self._connect_subnet(node_ids, density=0.3)

        # 子网间连接 (通过核心路由)
        core_nodes = self.subnets.get(4, [])
        if core_nodes:
            for subnet_id in range(4):
                subnet_nodes = self.subnets.get(subnet_id, [])
                if subnet_nodes and core_nodes:
                    # 每个子网连接2-3个核心节点
                    import random
                    num_connections = min(3, len(core_nodes))
                    gateways = random.sample(core_nodes, num_connections)
                    border_nodes = random.sample(
                        subnet_nodes, min(2, len(subnet_nodes))
                    )
                    for gw in gateways:
                        for border in border_nodes:
                            self._add_link(border, gw)

        logger.info(
            f"[TOPOLOGY] 企业网络: {n}节点, "
            f"{len(self.links)}链路, "
            f"{len(self.subnets)}子网"
        )

    def _build_datacenter(self):
        """构建数据中心拓扑 (简化Fat-Tree)"""
        n = self.num_nodes
        # Leaf-Spine简化: 每4个节点一个leaf，若干spine
        leaf_count = max(n // 5, 2)
        spine_count = max(leaf_count // 2, 2)

        # 创建节点
        for i in range(n):
            if i < spine_count:
                role = NodeRole.SWITCH
                subnet = 0
            elif i < spine_count + leaf_count:
                role = NodeRole.SWITCH
                subnet = 1
            else:
                role = NodeRole.SERVER
                subnet = 2 + (i % leaf_count)

            self.nodes[i] = NetworkNode(
                node_id=i,
                ip=f"172.16.{i // 256}.{i % 256}",
                mac=f"02:dc:{i:04x}"[:17],
                role=role,
                subnet=subnet,
                services=[22, 80, 443] if role == NodeRole.SERVER else [],
                value=self._compute_node_value(role, subnet),
            )

        # Spine-Leaf全互连
        for s in range(spine_count):
            for l in range(spine_count, spine_count + leaf_count):
                self._add_link(s, l)

        # Leaf连接下挂服务器
        servers = list(range(spine_count + leaf_count, n))
        for idx, server in enumerate(servers):
            leaf = spine_count + (idx % leaf_count)
            self._add_link(leaf, server)

        logger.info(f"[TOPOLOGY] 数据中心: {n}节点, {len(self.links)}链路")

    def _build_campus(self):
        """构建校园网拓扑"""
        # 简化为多个建筑物子网 + 核心互连
        n = self.num_nodes
        num_buildings = max(n // 10, 3)

        for i in range(n):
            building = i % num_buildings
            self.nodes[i] = NetworkNode(
                node_id=i,
                ip=f"192.168.{building}.{i % 256}",
                mac=f"02:ca:{i:04x}"[:17],
                role=NodeRole.NORMAL if i >= num_buildings else NodeRole.SWITCH,
                subnet=building,
                services=[22, 80] if i >= num_buildings else [],
                value=1.0,
            )
            if building not in self.subnets:
                self.subnets[building] = []
            self.subnets[building].append(i)

        # 建筑物内连接
        for subnet_id, node_ids in self.subnets.items():
            self._connect_subnet(node_ids, density=0.25)

        # 建筑物间连接 (环形 + 核心)
        building_gateways = [
            self.subnets[b][0] for b in range(num_buildings) if self.subnets.get(b)
        ]
        for idx in range(len(building_gateways)):
            next_idx = (idx + 1) % len(building_gateways)
            self._add_link(building_gateways[idx], building_gateways[next_idx])

        logger.info(f"[TOPOLOGY] 校园网: {n}节点, {len(self.links)}链路")

    def _build_random(self):
        """构建随机拓扑 (Erdős–Rényi模型)"""
        import random
        n = self.num_nodes
        p = min(6.0 / n, 0.3)  # 平均度≈6

        for i in range(n):
            self.nodes[i] = NetworkNode(
                node_id=i,
                ip=f"10.0.{i // 256}.{i % 256}",
                mac=f"02:rn:{i:04x}"[:17],
                role=NodeRole.NORMAL,
                subnet=0,
                services=[22],
                value=1.0,
            )

        for i in range(n):
            for j in range(i + 1, n):
                if random.random() < p:
                    self._add_link(i, j)

        # 确保连通性
        self._ensure_connectivity()

        logger.info(f"[TOPOLOGY] 随机网络: {n}节点, {len(self.links)}链路")

    def _connect_subnet(self, node_ids: List[int], density: float = 0.3):
        """子网内部随机连接"""
        import random
        for i in range(len(node_ids)):
            for j in range(i + 1, len(node_ids)):
                if random.random() < density:
                    self._add_link(node_ids[i], node_ids[j])

    def _add_link(self, src: int, dst: int, bandwidth: float = 1000.0):
        """添加双向链路"""
        if src == dst or src >= self.num_nodes or dst >= self.num_nodes:
            return
        if self.adjacency[src, dst] > 0:
            return  # 已存在

        self.adjacency[src, dst] = 1.0
        self.adjacency[dst, src] = 1.0

        self.links.append(NetworkLink(src=src, dst=dst, bandwidth=bandwidth))

    def _ensure_connectivity(self):
        """确保图连通 (BFS检查 + 补边)"""
        visited = set()
        queue = [0]
        visited.add(0)

        while queue:
            node = queue.pop(0)
            neighbors = np.where(self.adjacency[node] > 0)[0]
            for nb in neighbors:
                if nb not in visited:
                    visited.add(nb)
                    queue.append(nb)

        # 连接未访问到的节点
        unvisited = set(range(self.num_nodes)) - visited
        if unvisited:
            import random
            for node in unvisited:
                target = random.choice(list(visited))
                self._add_link(node, target)
                visited.add(node)

    def _compute_node_value(self, role: NodeRole, subnet: int) -> float:
        """计算节点资产价值"""
        value_map = {
            NodeRole.NORMAL: 1.0,
            NodeRole.SERVER: 3.0,
            NodeRole.SWITCH: 2.0,
            NodeRole.CONTROLLER: 5.0,
            NodeRole.ATTACKER: 0.0,
        }
        base = value_map.get(role, 1.0)
        # 服务器子网和管理子网价值更高
        if subnet in (2, 3):
            base *= 1.5
        return base

    # ============================================================
    # 查询接口
    # ============================================================

    def get_adjacency_matrix(self) -> np.ndarray:
        """返回邻接矩阵"""
        return self.adjacency.copy()

    def get_neighbors(self, node_id: int) -> List[int]:
        """获取邻居节点"""
        return list(np.where(self.adjacency[node_id] > 0)[0])

    def get_shortest_path_length(self, src: int, dst: int) -> int:
        """BFS计算最短路径长度"""
        if src == dst:
            return 0

        visited = {src}
        queue = [(src, 0)]

        while queue:
            node, dist = queue.pop(0)
            for nb in self.get_neighbors(node):
                if nb == dst:
                    return dist + 1
                if nb not in visited:
                    visited.add(nb)
                    queue.append((nb, dist + 1))

        return -1  # 不可达

    def get_subnet_nodes(self, subnet_id: int) -> List[int]:
        """获取子网内所有节点"""
        return self.subnets.get(subnet_id, [])

    def get_high_value_nodes(self, top_k: int = 10) -> List[Tuple[int, float]]:
        """获取高价值节点"""
        value_list = [(nid, node.value) for nid, node in self.nodes.items()]
        value_list.sort(key=lambda x: x[1], reverse=True)
        return value_list[:top_k]

    def deploy_honeypot(self, node_id: int) -> bool:
        """标记节点为蜜罐"""
        if node_id in self.nodes:
            self.nodes[node_id].is_honeypot = True
            self.nodes[node_id].role = NodeRole.HONEYPOT
            return True
        return False

    def remove_honeypot(self, node_id: int) -> bool:
        """移除节点的蜜罐标记"""
        if node_id in self.nodes and self.nodes[node_id].is_honeypot:
            self.nodes[node_id].is_honeypot = False
            self.nodes[node_id].role = NodeRole.NORMAL
            return True
        return False

    def get_honeypot_positions(self) -> List[int]:
        """获取所有蜜罐位置"""
        return [nid for nid, node in self.nodes.items() if node.is_honeypot]

    def get_topology_stats(self) -> Dict:
        """获取拓扑统计信息"""
        degrees = self.adjacency.sum(axis=1)
        return {
            "num_nodes": self.num_nodes,
            "num_links": len(self.links),
            "num_subnets": len(self.subnets),
            "avg_degree": float(degrees.mean()),
            "max_degree": int(degrees.max()),
            "min_degree": int(degrees.min()),
            "density": float(self.adjacency.sum() / (self.num_nodes * (self.num_nodes - 1))),
            "topology_type": self.topology_type,
        }
