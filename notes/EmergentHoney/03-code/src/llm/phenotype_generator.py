"""
EmergentHoney LLM模块：蜜罐表型生成器
实现论文 Section IV-B 的LLM驱动表型表达机制
"""

import json
import hashlib
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# ============================================================
# 蜜罐类型定义
# ============================================================

HONEYPOT_TYPES = {
    0: {"name": "ssh_server", "service": "SSH", "port": 22,
        "description": "OpenSSH 仿真蜜罐"},
    1: {"name": "web_server", "service": "HTTP/HTTPS", "port": 80,
        "description": "Web应用蜜罐 (Apache/Nginx)"},
    2: {"name": "database", "service": "MySQL/PostgreSQL", "port": 3306,
        "description": "数据库蜜罐"},
    3: {"name": "file_server", "service": "SMB/FTP", "port": 445,
        "description": "文件共享蜜罐"},
    4: {"name": "mail_server", "service": "SMTP/IMAP", "port": 25,
        "description": "邮件服务器蜜罐"},
    5: {"name": "rdp_server", "service": "RDP", "port": 3389,
        "description": "远程桌面蜜罐"},
    6: {"name": "iot_device", "service": "Telnet/MQTT", "port": 23,
        "description": "IoT设备蜜罐"},
    7: {"name": "scada_hmi", "service": "Modbus/DNP3", "port": 502,
        "description": "工控系统蜜罐"},
}


@dataclass
class PhenotypeSpec:
    """蜜罐表型规格"""
    phenotype_id: str
    hp_type: int
    position: int
    service_banner: str          # 服务横幅 (e.g., "OpenSSH_8.9p1 Ubuntu")
    fake_files: List[Dict]       # 假文件列表 [{name, content, size}]
    fake_credentials: List[Dict] # 假凭据 [{username, password, notes}]
    fake_data: Dict              # 假数据 (数据库记录、邮件内容等)
    response_templates: Dict     # 交互响应模板
    vulnerability_profile: Dict  # 模拟的漏洞特征
    network_fingerprint: Dict    # 网络指纹 (OS, TTL, TCP window等)
    diversity_hash: str = ""     # 多样性哈希 (用于去重)


@dataclass
class AttackerContext:
    """攻击者上下文 (传递给LLM的信息)"""
    techniques_observed: List[str]   # 已观察到的ATT&CK技术
    attack_phase: str                # 当前攻击阶段
    scan_patterns: List[str]         # 扫描模式
    time_in_network: float           # 在网络中的时间 (秒)
    previous_interactions: int       # 之前的交互次数


# ============================================================
# LLM后端抽象接口
# ============================================================

class LLMBackend(ABC):
    """LLM后端抽象基类"""

    @abstractmethod
    def generate(self, prompt: str, max_tokens: int = 2048,
                 temperature: float = 0.7) -> str:
        """生成文本"""
        pass


class MockLLMBackend(LLMBackend):
    """
    模拟LLM后端 — 用于实验和测试

    不依赖真实API，使用模板生成可信的蜜罐表型内容
    """

    # 操作系统指纹库
    OS_FINGERPRINTS = [
        {"os": "Ubuntu 22.04 LTS", "ttl": 64, "tcp_window": 65535,
         "vendor": "Canonical"},
        {"os": "CentOS 8", "ttl": 64, "tcp_window": 29200,
         "vendor": "Red Hat"},
        {"os": "Windows Server 2019", "ttl": 128, "tcp_window": 65535,
         "vendor": "Microsoft"},
        {"os": "Debian 11", "ttl": 64, "tcp_window": 65535,
         "vendor": "Debian"},
        {"os": "FreeBSD 13", "ttl": 64, "tcp_window": 65535,
         "vendor": "FreeBSD Foundation"},
    ]

    # SSH横幅库
    SSH_BANNERS = [
        "SSH-2.0-OpenSSH_8.9p1 Ubuntu-3ubuntu0.1",
        "SSH-2.0-OpenSSH_8.0",
        "SSH-2.0-OpenSSH_7.9p1 Debian-10+deb10u2",
        "SSH-2.0-OpenSSH_8.4p1 Debian-5+deb11u1",
    ]

    # Web服务器横幅库
    WEB_BANNERS = [
        "Apache/2.4.54 (Ubuntu)",
        "nginx/1.22.1",
        "Apache/2.4.52 (Debian)",
        "Microsoft-IIS/10.0",
    ]

    # 假文件名模板
    FAKE_FILES = {
        "ssh_server": [
            {"name": "/etc/passwd", "type": "system"},
            {"name": "/home/admin/.ssh/authorized_keys", "type": "credential"},
            {"name": "/var/log/auth.log", "type": "log"},
        ],
        "web_server": [
            {"name": "/var/www/html/wp-config.php", "type": "config"},
            {"name": "/var/www/html/.env", "type": "credential"},
            {"name": "/var/log/apache2/access.log", "type": "log"},
        ],
        "database": [
            {"name": "/etc/mysql/my.cnf", "type": "config"},
            {"name": "/var/lib/mysql/backup_2024.sql", "type": "data"},
            {"name": "/root/.mysql_history", "type": "credential"},
        ],
        "file_server": [
            {"name": "/share/finance/Q4_report_2024.xlsx", "type": "data"},
            {"name": "/share/hr/employee_list.csv", "type": "data"},
            {"name": "/share/IT/vpn_credentials.txt", "type": "credential"},
        ],
    }

    # 假凭据模板
    FAKE_CREDENTIALS_POOL = [
        {"username": "admin", "password": "P@ssw0rd2024!", "notes": "系统管理员"},
        {"username": "deploy", "password": "d3pl0y_s3rv1c3", "notes": "部署账号"},
        {"username": "backup", "password": "bkup_r3st0re", "notes": "备份服务"},
        {"username": "jenkins", "password": "j3nk1ns_c1cd", "notes": "CI/CD"},
        {"username": "root", "password": "toor123!", "notes": "根用户"},
        {"username": "dbadmin", "password": "Dat@base#2024", "notes": "数据库管理"},
        {"username": "webmaster", "password": "W3bM@ster!", "notes": "Web管理"},
        {"username": "svc_account", "password": "Sv(Acc0unt", "notes": "服务账号"},
    ]

    def generate(self, prompt: str, max_tokens: int = 2048,
                 temperature: float = 0.7) -> str:
        """模拟LLM生成 — 返回结构化JSON"""
        # 从prompt中提取类型信息 (简化实现)
        return json.dumps({"status": "mock_generated", "prompt_length": len(prompt)})


class OpenAIBackend(LLMBackend):
    """
    OpenAI API后端 (GPT-4/GPT-3.5)

    注意：实际使用时需要设置API密钥
    """

    def __init__(self, model: str = "gpt-4", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key

    def generate(self, prompt: str, max_tokens: int = 2048,
                 temperature: float = 0.7) -> str:
        """调用OpenAI API"""
        try:
            import openai
            client = openai.OpenAI(api_key=self.api_key)
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system",
                     "content": "你是一个网络安全蜜罐配置生成专家。"
                                "生成真实可信的蜜罐服务配置。"
                                "所有输出必须是合法JSON格式。"},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except ImportError:
            logger.warning("openai 包未安装，回退到模拟后端")
            return MockLLMBackend().generate(prompt, max_tokens, temperature)
        except Exception as e:
            logger.error(f"OpenAI API 调用失败: {e}")
            return MockLLMBackend().generate(prompt, max_tokens, temperature)


# ============================================================
# 表型生成器
# ============================================================

class PhenotypeGenerator:
    """
    蜜罐表型生成器 — Section IV-B

    信息素引擎决定"在哪里部署什么类型的蜜罐"(基因型 genotype)
    本模块决定"蜜罐长什么样"(表型 phenotype)

    关键特性:
    1. 上下文感知: 根据攻击者行为定制响应
    2. 多样性控制: 确保同类型蜜罐间存在差异 (防指纹)
    3. 一致性维护: 单个蜜罐内部各项信息自洽
    """

    def __init__(
        self,
        llm_backend: Optional[LLMBackend] = None,
        diversity_threshold: float = 0.3,
        cache_size: int = 100,
    ):
        """
        Args:
            llm_backend: LLM后端实例，None则使用模拟后端
            diversity_threshold: 多样性阈值 (0-1)，低于此值触发重新生成
            cache_size: 表型缓存大小
        """
        self.llm = llm_backend or MockLLMBackend()
        self.diversity_threshold = diversity_threshold
        self.cache_size = cache_size

        # 已生成的表型缓存
        self.phenotype_cache: Dict[str, PhenotypeSpec] = {}

        # 多样性池 — 按类型分组的所有表型哈希
        self.diversity_pool: Dict[int, List[str]] = {}

        # 生成计数
        self.generation_count = 0

    def generate_phenotype(
        self,
        hp_type: int,
        position: int,
        attacker_context: Optional[AttackerContext] = None,
    ) -> PhenotypeSpec:
        """
        生成蜜罐表型

        Args:
            hp_type: 蜜罐类型索引
            position: 网络位置
            attacker_context: 攻击者上下文 (可选，用于自适应)

        Returns:
            完整的蜜罐表型规格
        """
        type_info = HONEYPOT_TYPES.get(hp_type, HONEYPOT_TYPES[0])

        # 构建LLM提示词
        prompt = self._build_prompt(type_info, position, attacker_context)

        # 生成基础表型
        if isinstance(self.llm, MockLLMBackend):
            phenotype = self._generate_mock_phenotype(
                hp_type, position, type_info, attacker_context
            )
        else:
            phenotype = self._generate_llm_phenotype(
                hp_type, position, type_info, prompt
            )

        # 多样性检查与强化
        phenotype = self._ensure_diversity(phenotype, hp_type)

        # 缓存
        self.phenotype_cache[phenotype.phenotype_id] = phenotype
        self._maintain_cache()

        self.generation_count += 1

        logger.info(
            f"[PHENOTYPE] 生成表型 ID={phenotype.phenotype_id} "
            f"类型={type_info['name']} 位置={position}"
        )

        return phenotype

    def _build_prompt(
        self,
        type_info: Dict,
        position: int,
        context: Optional[AttackerContext],
    ) -> str:
        """构建LLM提示词"""
        prompt_parts = [
            f"为以下蜜罐生成真实可信的配置表型:",
            f"- 蜜罐类型: {type_info['name']} ({type_info['description']})",
            f"- 服务: {type_info['service']} 端口: {type_info['port']}",
            f"- 网络位置: 节点 #{position}",
            "",
            "请生成以下内容 (JSON格式):",
            "1. service_banner: 真实的服务横幅字符串",
            "2. fake_files: 至少3个诱饵文件 (含文件名和内容摘要)",
            "3. fake_credentials: 至少2组假凭据",
            "4. vulnerability_profile: 模拟的漏洞特征 (CVE编号和描述)",
            "5. network_fingerprint: 操作系统指纹 (OS, TTL, TCP窗口大小)",
        ]

        if context:
            prompt_parts.extend([
                "",
                "攻击者上下文:",
                f"- 已观察技术: {', '.join(context.techniques_observed[:5])}",
                f"- 攻击阶段: {context.attack_phase}",
                f"- 网络驻留时间: {context.time_in_network:.0f}秒",
                "",
                "请根据攻击者行为调整蜜罐表型，使其更具吸引力。",
                "例如：如果攻击者在进行横向移动，增加更多凭据和内部服务信息。",
            ])

        return "\n".join(prompt_parts)

    def _generate_mock_phenotype(
        self,
        hp_type: int,
        position: int,
        type_info: Dict,
        context: Optional[AttackerContext],
    ) -> PhenotypeSpec:
        """使用模板生成表型 (不依赖真实LLM)"""
        import random

        type_name = type_info["name"]

        # 选择OS指纹
        os_fp = random.choice(MockLLMBackend.OS_FINGERPRINTS)

        # 服务横幅
        if type_name == "ssh_server":
            banner = random.choice(MockLLMBackend.SSH_BANNERS)
        elif type_name == "web_server":
            banner = random.choice(MockLLMBackend.WEB_BANNERS)
        elif type_name == "database":
            banner = f"MySQL {random.choice(['5.7.42', '8.0.33', '8.0.35'])}"
        elif type_name == "file_server":
            banner = f"Samba {random.choice(['4.15.13', '4.17.12', '4.18.6'])}"
        elif type_name == "rdp_server":
            banner = "Microsoft Terminal Services"
        else:
            banner = f"{type_info['service']} Server"

        # 假文件
        file_templates = MockLLMBackend.FAKE_FILES.get(type_name, [
            {"name": f"/opt/{type_name}/config.yml", "type": "config"},
            {"name": f"/var/log/{type_name}.log", "type": "log"},
        ])

        fake_files = []
        for ft in file_templates:
            fake_files.append({
                "name": ft["name"],
                "content": f"[模拟内容] {ft['type']}数据 - 节点{position}",
                "size": random.randint(256, 65536),
                "modified": f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            })

        # 假凭据 (随机选取，避免重复)
        cred_count = random.randint(2, 4)
        fake_creds = random.sample(
            MockLLMBackend.FAKE_CREDENTIALS_POOL,
            min(cred_count, len(MockLLMBackend.FAKE_CREDENTIALS_POOL))
        )

        # 根据攻击者上下文调整
        if context and context.attack_phase == "lateral":
            # 横向移动阶段：增加更多内部凭据
            fake_creds.append({
                "username": f"svc_{type_name}",
                "password": f"Int3rn@l_{random.randint(1000,9999)}",
                "notes": "内部服务账号"
            })
            fake_files.append({
                "name": f"/home/admin/.ssh/id_rsa",
                "content": "[模拟SSH私钥]",
                "size": 1679,
            })

        # 漏洞特征
        vulnerability_profile = self._generate_vulnerability_profile(
            type_name, context
        )

        # 网络指纹
        network_fingerprint = {
            "os": os_fp["os"],
            "ttl": os_fp["ttl"],
            "tcp_window": os_fp["tcp_window"],
            "vendor": os_fp["vendor"],
            "uptime_days": random.randint(7, 365),
            "mac_vendor": random.choice([
                "VMware", "Dell", "HP", "Lenovo", "SuperMicro"
            ]),
        }

        # 生成表型ID
        phenotype_id = self._generate_phenotype_id(hp_type, position)

        # 多样性哈希
        diversity_hash = self._compute_diversity_hash(
            banner, fake_files, fake_creds
        )

        return PhenotypeSpec(
            phenotype_id=phenotype_id,
            hp_type=hp_type,
            position=position,
            service_banner=banner,
            fake_files=fake_files,
            fake_credentials=fake_creds,
            fake_data={"records": random.randint(100, 10000)},
            response_templates=self._generate_response_templates(type_name),
            vulnerability_profile=vulnerability_profile,
            network_fingerprint=network_fingerprint,
            diversity_hash=diversity_hash,
        )

    def _generate_llm_phenotype(
        self,
        hp_type: int,
        position: int,
        type_info: Dict,
        prompt: str,
    ) -> PhenotypeSpec:
        """使用真实LLM生成表型"""
        response = self.llm.generate(prompt, max_tokens=2048, temperature=0.8)

        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            logger.warning("LLM输出无法解析为JSON，回退到模拟生成")
            return self._generate_mock_phenotype(
                hp_type, position, type_info, None
            )

        phenotype_id = self._generate_phenotype_id(hp_type, position)

        return PhenotypeSpec(
            phenotype_id=phenotype_id,
            hp_type=hp_type,
            position=position,
            service_banner=data.get("service_banner", "Unknown Service"),
            fake_files=data.get("fake_files", []),
            fake_credentials=data.get("fake_credentials", []),
            fake_data=data.get("fake_data", {}),
            response_templates=data.get("response_templates", {}),
            vulnerability_profile=data.get("vulnerability_profile", {}),
            network_fingerprint=data.get("network_fingerprint", {}),
            diversity_hash=self._compute_diversity_hash(
                data.get("service_banner", ""),
                data.get("fake_files", []),
                data.get("fake_credentials", []),
            ),
        )

    def _generate_vulnerability_profile(
        self,
        type_name: str,
        context: Optional[AttackerContext],
    ) -> Dict:
        """生成模拟漏洞特征"""
        import random

        vuln_db = {
            "ssh_server": [
                {"cve": "CVE-2023-38408", "severity": "high",
                 "desc": "OpenSSH PKCS#11 远程代码执行"},
                {"cve": "CVE-2021-41617", "severity": "medium",
                 "desc": "OpenSSH 权限提升"},
            ],
            "web_server": [
                {"cve": "CVE-2023-25690", "severity": "critical",
                 "desc": "Apache HTTP Server 请求走私"},
                {"cve": "CVE-2022-22720", "severity": "high",
                 "desc": "Apache HTTP Server 请求走私"},
            ],
            "database": [
                {"cve": "CVE-2023-22078", "severity": "high",
                 "desc": "MySQL Server 拒绝服务"},
                {"cve": "CVE-2022-21589", "severity": "medium",
                 "desc": "MySQL Server 信息泄露"},
            ],
            "file_server": [
                {"cve": "CVE-2023-3347", "severity": "medium",
                 "desc": "Samba SMB签名绕过"},
            ],
        }

        vulns = vuln_db.get(type_name, [
            {"cve": "CVE-2023-XXXXX", "severity": "medium",
             "desc": "通用服务漏洞"}
        ])

        # 选择1-2个漏洞
        selected = random.sample(vulns, min(random.randint(1, 2), len(vulns)))

        return {
            "vulnerabilities": selected,
            "patch_level": random.choice(["outdated", "partially_patched"]),
            "last_update": f"2024-{random.randint(1,6):02d}-{random.randint(1,28):02d}",
        }

    def _generate_response_templates(self, type_name: str) -> Dict:
        """生成交互响应模板"""
        templates = {
            "ssh_server": {
                "login_success": "Last login: {date} from {ip}",
                "login_failure": "Permission denied, please try again.",
                "motd": "Welcome to Ubuntu 22.04 LTS (GNU/Linux 5.15.0-83-generic x86_64)",
                "command_not_found": "{cmd}: command not found",
            },
            "web_server": {
                "200": "<html><head><title>Welcome</title></head><body>Index</body></html>",
                "401": "401 Unauthorized - Authentication Required",
                "403": "403 Forbidden - Access Denied",
                "404": "404 Not Found - The requested resource was not found",
                "500": "500 Internal Server Error",
            },
            "database": {
                "auth_success": "Welcome to MySQL monitor. Commands end with ; or \\g.",
                "auth_failure": "ERROR 1045 (28000): Access denied for user '{user}'@'{host}'",
                "query_result": "Query OK, {rows} rows affected ({time} sec)",
            },
        }

        return templates.get(type_name, {
            "default": "Service response placeholder"
        })

    def _ensure_diversity(
        self, phenotype: PhenotypeSpec, hp_type: int
    ) -> PhenotypeSpec:
        """
        确保表型多样性 — 防止攻击者通过指纹识别蜜罐

        如果新表型与已有表型过于相似，触发变异
        """
        if hp_type not in self.diversity_pool:
            self.diversity_pool[hp_type] = []

        existing_hashes = self.diversity_pool[hp_type]

        # 检查是否与已有表型过于相似
        for existing_hash in existing_hashes:
            similarity = self._hash_similarity(
                phenotype.diversity_hash, existing_hash
            )
            if similarity > (1 - self.diversity_threshold):
                # 过于相似，触发微变异
                phenotype = self._mutate_phenotype(phenotype)
                logger.debug(
                    f"[DIVERSITY] 表型 {phenotype.phenotype_id} "
                    f"触发多样性变异 (相似度={similarity:.2f})"
                )
                break

        # 记录哈希
        existing_hashes.append(phenotype.diversity_hash)

        return phenotype

    def _mutate_phenotype(self, phenotype: PhenotypeSpec) -> PhenotypeSpec:
        """对表型进行微变异以增加多样性"""
        import random

        # 随机修改横幅版本号
        banner = phenotype.service_banner
        if "." in banner:
            parts = banner.rsplit(".", 1)
            try:
                minor = int(parts[-1].split()[0]) if parts[-1].split() else 0
                parts[-1] = str(minor + random.randint(1, 3))
                phenotype.service_banner = ".".join(parts)
            except (ValueError, IndexError):
                pass

        # 随机替换一个凭据
        if phenotype.fake_credentials:
            idx = random.randint(0, len(phenotype.fake_credentials) - 1)
            new_cred = random.choice(MockLLMBackend.FAKE_CREDENTIALS_POOL)
            phenotype.fake_credentials[idx] = new_cred.copy()

        # 重新计算哈希
        phenotype.diversity_hash = self._compute_diversity_hash(
            phenotype.service_banner,
            phenotype.fake_files,
            phenotype.fake_credentials,
        )

        return phenotype

    def _generate_phenotype_id(self, hp_type: int, position: int) -> str:
        """生成唯一表型ID"""
        self.generation_count += 1
        raw = f"{hp_type}_{position}_{self.generation_count}"
        return f"ph_{hashlib.md5(raw.encode()).hexdigest()[:12]}"

    def _compute_diversity_hash(
        self,
        banner: str,
        files: List[Dict],
        credentials: List[Dict],
    ) -> str:
        """计算表型多样性哈希"""
        content = json.dumps({
            "banner": banner,
            "files": [f.get("name", "") for f in files],
            "creds": [c.get("username", "") for c in credentials],
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def _hash_similarity(hash1: str, hash2: str) -> float:
        """计算两个哈希的相似度 (基于汉明距离)"""
        if len(hash1) != len(hash2):
            return 0.0
        matches = sum(c1 == c2 for c1, c2 in zip(hash1, hash2))
        return matches / len(hash1)

    def _maintain_cache(self):
        """维护缓存大小"""
        if len(self.phenotype_cache) > self.cache_size:
            # 移除最早的条目
            keys = list(self.phenotype_cache.keys())
            for key in keys[:len(keys) - self.cache_size]:
                del self.phenotype_cache[key]

    def get_stats(self) -> Dict:
        """获取生成器统计信息"""
        type_counts = {}
        for spec in self.phenotype_cache.values():
            t = spec.hp_type
            type_counts[t] = type_counts.get(t, 0) + 1

        return {
            "total_generated": self.generation_count,
            "cache_size": len(self.phenotype_cache),
            "type_distribution": type_counts,
            "diversity_pool_sizes": {
                k: len(v) for k, v in self.diversity_pool.items()
            },
        }
