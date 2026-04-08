"""
EmergentHoney 网络模块：蜜罐部署管理器
管理蜜罐实例的生命周期 (创建、配置、迁移、销毁)
"""

import logging
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class HoneypotStatus(Enum):
    """蜜罐实例状态"""
    PENDING = "pending"
    DEPLOYING = "deploying"
    RUNNING = "running"
    MIGRATING = "migrating"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class HoneypotInstance:
    """蜜罐实例"""
    instance_id: str
    position: int          # 网络位置 (节点ID)
    hp_type: int           # 蜜罐类型索引
    phenotype_id: str      # 表型ID
    status: HoneypotStatus = HoneypotStatus.PENDING
    container_id: str = ""
    ip_address: str = ""
    creation_time: float = 0.0
    last_interaction: float = 0.0
    total_interactions: int = 0
    total_engagement_time: float = 0.0

    # 运行时指标
    cpu_usage: float = 0.0
    memory_mb: float = 0.0
    network_bytes_in: int = 0
    network_bytes_out: int = 0


class HoneypotDeployer:
    """
    蜜罐部署管理器

    在实验环境中模拟Docker容器化蜜罐部署。
    生产环境中可对接真实的Docker/Kubernetes API。

    支持的蜜罐后端:
    - T-Pot (https://github.com/telekom-security/tpotce)
    - OpenCanary (https://github.com/thinkst/opencanary)
    - Cowrie (SSH/Telnet)
    - Dionaea (多协议)
    """

    # 蜜罐类型到容器镜像的映射
    TYPE_IMAGE_MAP = {
        0: {"image": "cowrie/cowrie:latest", "name": "cowrie",
            "ports": {"2222/tcp": 22}},
        1: {"image": "snare/tanner:latest", "name": "snare",
            "ports": {"8080/tcp": 80, "8443/tcp": 443}},
        2: {"image": "dionaea:latest", "name": "dionaea-mysql",
            "ports": {"3306/tcp": 3306}},
        3: {"image": "dionaea:latest", "name": "dionaea-smb",
            "ports": {"445/tcp": 445, "139/tcp": 139}},
        4: {"image": "mailoney:latest", "name": "mailoney",
            "ports": {"2525/tcp": 25}},
        5: {"image": "rdpy:latest", "name": "rdpy",
            "ports": {"3389/tcp": 3389}},
        6: {"image": "opencanary:latest", "name": "opencanary-iot",
            "ports": {"23/tcp": 23, "1883/tcp": 1883}},
        7: {"image": "conpot:latest", "name": "conpot",
            "ports": {"502/tcp": 502, "102/tcp": 102}},
    }

    def __init__(
        self,
        max_instances: int = 50,
        deploy_latency: float = 2.0,
        migration_latency: float = 5.0,
        simulation_mode: bool = True,
    ):
        """
        Args:
            max_instances: 最大蜜罐实例数
            deploy_latency: 部署延迟 (秒，用于模拟)
            migration_latency: 迁移延迟 (秒，用于模拟)
            simulation_mode: True=模拟模式，False=真实Docker部署
        """
        self.max_instances = max_instances
        self.deploy_latency = deploy_latency
        self.migration_latency = migration_latency
        self.simulation_mode = simulation_mode

        # 活跃实例
        self.instances: Dict[str, HoneypotInstance] = {}

        # 位置到实例的映射
        self.position_map: Dict[int, str] = {}

        # 部署历史
        self.deploy_history: List[Dict] = []

        # 统计
        self.total_deployments = 0
        self.total_migrations = 0
        self.total_mutations = 0

        self._instance_counter = 0

    def deploy(
        self,
        position: int,
        hp_type: int,
        phenotype_id: str = "",
    ) -> Optional[HoneypotInstance]:
        """
        部署蜜罐实例

        Args:
            position: 网络位置
            hp_type: 蜜罐类型
            phenotype_id: 表型ID

        Returns:
            部署的实例，或None (预算已满/位置已占用)
        """
        # 检查预算
        active_count = sum(
            1 for inst in self.instances.values()
            if inst.status in (HoneypotStatus.RUNNING, HoneypotStatus.DEPLOYING)
        )
        if active_count >= self.max_instances:
            logger.warning(f"[DEPLOY] 已达最大实例数 {self.max_instances}")
            return None

        # 检查位置冲突
        if position in self.position_map:
            existing_id = self.position_map[position]
            if existing_id in self.instances:
                logger.warning(f"[DEPLOY] 位置 {position} 已被 {existing_id} 占用")
                return None

        # 创建实例
        instance_id = self._generate_instance_id()
        now = time.time()

        instance = HoneypotInstance(
            instance_id=instance_id,
            position=position,
            hp_type=hp_type,
            phenotype_id=phenotype_id,
            status=HoneypotStatus.DEPLOYING,
            creation_time=now,
            ip_address=f"10.99.{position // 256}.{position % 256}",
        )

        if self.simulation_mode:
            # 模拟部署延迟
            instance.status = HoneypotStatus.RUNNING
            instance.container_id = f"sim_{instance_id}"
        else:
            # 真实Docker部署
            container_id = self._docker_deploy(instance, hp_type)
            if container_id:
                instance.container_id = container_id
                instance.status = HoneypotStatus.RUNNING
            else:
                instance.status = HoneypotStatus.ERROR
                return None

        # 注册
        self.instances[instance_id] = instance
        self.position_map[position] = instance_id
        self.total_deployments += 1

        self.deploy_history.append({
            "action": "deploy",
            "instance_id": instance_id,
            "position": position,
            "hp_type": hp_type,
            "timestamp": now,
        })

        logger.info(
            f"[DEPLOY] 蜜罐 {instance_id} 部署到位置 {position} "
            f"类型={hp_type} 表型={phenotype_id}"
        )

        return instance

    def migrate(
        self,
        instance_id: str,
        new_position: int,
        new_type: Optional[int] = None,
        new_phenotype_id: str = "",
    ) -> bool:
        """
        迁移蜜罐实例到新位置

        Args:
            instance_id: 实例ID
            new_position: 新位置
            new_type: 新类型 (可选，不变则沿用)
            new_phenotype_id: 新表型ID

        Returns:
            是否成功
        """
        if instance_id not in self.instances:
            logger.error(f"[MIGRATE] 实例 {instance_id} 不存在")
            return False

        instance = self.instances[instance_id]
        old_position = instance.position

        # 检查新位置
        if new_position in self.position_map:
            existing = self.position_map[new_position]
            if existing != instance_id:
                logger.warning(f"[MIGRATE] 新位置 {new_position} 已被占用")
                return False

        # 更新状态
        instance.status = HoneypotStatus.MIGRATING

        # 移除旧映射
        if old_position in self.position_map:
            del self.position_map[old_position]

        # 更新实例
        instance.position = new_position
        if new_type is not None:
            instance.hp_type = new_type
        if new_phenotype_id:
            instance.phenotype_id = new_phenotype_id

        # 注册新映射
        self.position_map[new_position] = instance_id
        instance.status = HoneypotStatus.RUNNING
        instance.ip_address = f"10.99.{new_position // 256}.{new_position % 256}"

        self.total_migrations += 1

        self.deploy_history.append({
            "action": "migrate",
            "instance_id": instance_id,
            "from_position": old_position,
            "to_position": new_position,
            "new_type": new_type,
            "timestamp": time.time(),
        })

        logger.info(
            f"[MIGRATE] {instance_id}: {old_position} -> {new_position} "
            f"类型={instance.hp_type}"
        )

        return True

    def mutate(
        self,
        instance_id: str,
        new_type: int,
        new_phenotype_id: str = "",
    ) -> bool:
        """
        变异蜜罐类型 (保持位置不变)

        Args:
            instance_id: 实例ID
            new_type: 新蜜罐类型
            new_phenotype_id: 新表型ID
        """
        if instance_id not in self.instances:
            return False

        instance = self.instances[instance_id]
        old_type = instance.hp_type
        instance.hp_type = new_type

        if new_phenotype_id:
            instance.phenotype_id = new_phenotype_id

        self.total_mutations += 1

        self.deploy_history.append({
            "action": "mutate",
            "instance_id": instance_id,
            "position": instance.position,
            "old_type": old_type,
            "new_type": new_type,
            "timestamp": time.time(),
        })

        logger.info(
            f"[MUTATE] {instance_id} 位置={instance.position}: "
            f"类型 {old_type} -> {new_type}"
        )

        return True

    def destroy(self, instance_id: str) -> bool:
        """销毁蜜罐实例"""
        if instance_id not in self.instances:
            return False

        instance = self.instances[instance_id]

        # 清理映射
        if instance.position in self.position_map:
            if self.position_map[instance.position] == instance_id:
                del self.position_map[instance.position]

        if not self.simulation_mode:
            self._docker_stop(instance.container_id)

        instance.status = HoneypotStatus.STOPPED

        self.deploy_history.append({
            "action": "destroy",
            "instance_id": instance_id,
            "position": instance.position,
            "timestamp": time.time(),
        })

        del self.instances[instance_id]

        logger.info(f"[DESTROY] 蜜罐 {instance_id} 已销毁")
        return True

    def record_interaction(
        self,
        position: int,
        engagement_time: float,
    ):
        """记录蜜罐交互"""
        if position in self.position_map:
            instance_id = self.position_map[position]
            if instance_id in self.instances:
                inst = self.instances[instance_id]
                inst.total_interactions += 1
                inst.total_engagement_time += engagement_time
                inst.last_interaction = time.time()

    def _generate_instance_id(self) -> str:
        """生成唯一实例ID"""
        self._instance_counter += 1
        return f"hp_{self._instance_counter:06d}"

    def _docker_deploy(self, instance: HoneypotInstance, hp_type: int) -> Optional[str]:
        """真实Docker部署 (需要docker SDK)"""
        try:
            import docker
            client = docker.from_env()

            image_info = self.TYPE_IMAGE_MAP.get(hp_type, self.TYPE_IMAGE_MAP[0])
            container = client.containers.run(
                image_info["image"],
                detach=True,
                name=f"eh_{instance.instance_id}",
                ports=image_info["ports"],
                labels={"emergent_honey": "true",
                        "position": str(instance.position)},
            )
            return container.id
        except ImportError:
            logger.warning("docker SDK未安装，回退到模拟模式")
            return f"sim_{instance.instance_id}"
        except Exception as e:
            logger.error(f"Docker部署失败: {e}")
            return None

    def _docker_stop(self, container_id: str):
        """停止Docker容器"""
        if container_id.startswith("sim_"):
            return
        try:
            import docker
            client = docker.from_env()
            container = client.containers.get(container_id)
            container.stop(timeout=5)
            container.remove()
        except Exception as e:
            logger.error(f"Docker停止失败: {e}")

    # ============================================================
    # 查询接口
    # ============================================================

    def get_active_instances(self) -> List[HoneypotInstance]:
        """获取所有活跃实例"""
        return [
            inst for inst in self.instances.values()
            if inst.status == HoneypotStatus.RUNNING
        ]

    def get_instance_at(self, position: int) -> Optional[HoneypotInstance]:
        """获取指定位置的实例"""
        inst_id = self.position_map.get(position)
        if inst_id:
            return self.instances.get(inst_id)
        return None

    def get_deployment_stats(self) -> Dict:
        """获取部署统计"""
        active = sum(
            1 for i in self.instances.values()
            if i.status == HoneypotStatus.RUNNING
        )
        total_engagement = sum(
            i.total_engagement_time for i in self.instances.values()
        )
        total_interactions = sum(
            i.total_interactions for i in self.instances.values()
        )

        return {
            "active_instances": active,
            "total_deployments": self.total_deployments,
            "total_migrations": self.total_migrations,
            "total_mutations": self.total_mutations,
            "total_engagement_time": total_engagement,
            "total_interactions": total_interactions,
            "budget_utilization": active / max(self.max_instances, 1),
        }
