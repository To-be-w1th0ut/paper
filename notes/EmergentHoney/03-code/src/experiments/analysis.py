"""
EmergentHoney 实验模块：数据分析与可视化
实现论文 Section VI 的统计检验与图表生成
"""

import numpy as np
import json
import logging
from typing import Dict, List, Tuple, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================
# 统计检验
# ============================================================

class StatisticalTests:
    """
    统计检验工具

    论文使用:
    - Wilcoxon符号秩检验 (非参数配对检验，n=30)
    - Cliff's delta (效应量)
    - 95%置信区间
    """

    @staticmethod
    def wilcoxon_test(x: np.ndarray, y: np.ndarray) -> Dict:
        """
        Wilcoxon符号秩检验

        H0: 两组样本无显著差异
        H1: EmergentHoney显著优于基线

        Args:
            x: EmergentHoney结果
            y: 基线结果

        Returns:
            {statistic, p_value, significant}
        """
        try:
            from scipy.stats import wilcoxon
            stat, p_value = wilcoxon(x, y, alternative="greater")
            return {
                "statistic": float(stat),
                "p_value": float(p_value),
                "significant": p_value < 0.05,
            }
        except ImportError:
            # 无scipy时使用简化版本
            logger.warning("scipy未安装，使用简化统计检验")
            return StatisticalTests._simplified_wilcoxon(x, y)

    @staticmethod
    def _simplified_wilcoxon(x: np.ndarray, y: np.ndarray) -> Dict:
        """简化Wilcoxon检验 (无scipy依赖)"""
        diffs = x - y
        n_positive = np.sum(diffs > 0)
        n_total = np.sum(diffs != 0)

        if n_total == 0:
            return {"statistic": 0, "p_value": 1.0, "significant": False}

        # 使用正态近似
        ratio = n_positive / n_total
        # 简化: 如果>70%的差异为正，认为显著
        significant = ratio > 0.7 and n_total >= 10

        return {
            "statistic": float(n_positive),
            "p_value": 1.0 - ratio,  # 近似p值
            "significant": significant,
        }

    @staticmethod
    def cliffs_delta(x: np.ndarray, y: np.ndarray) -> Dict:
        """
        Cliff's delta 效应量

        |d| < 0.147: negligible
        |d| < 0.33: small
        |d| < 0.474: medium
        |d| >= 0.474: large

        Args:
            x: 实验组
            y: 对照组

        Returns:
            {delta, magnitude}
        """
        n_x, n_y = len(x), len(y)
        if n_x == 0 or n_y == 0:
            return {"delta": 0.0, "magnitude": "negligible"}

        # 计算所有配对比较
        more = 0
        less = 0
        for xi in x:
            for yi in y:
                if xi > yi:
                    more += 1
                elif xi < yi:
                    less += 1

        delta = (more - less) / (n_x * n_y)

        abs_delta = abs(delta)
        if abs_delta < 0.147:
            magnitude = "negligible"
        elif abs_delta < 0.33:
            magnitude = "small"
        elif abs_delta < 0.474:
            magnitude = "medium"
        else:
            magnitude = "large"

        return {"delta": float(delta), "magnitude": magnitude}

    @staticmethod
    def confidence_interval(data: np.ndarray, confidence: float = 0.95) -> Tuple:
        """
        计算置信区间

        Args:
            data: 样本数据
            confidence: 置信水平

        Returns:
            (mean, lower, upper)
        """
        n = len(data)
        mean = np.mean(data)
        std = np.std(data, ddof=1)

        # 使用t分布近似 (n>=30时近似正态)
        if n >= 30:
            z = 1.96  # 95%
        else:
            # 简化t值查表
            z = 2.045  # t_{0.025, 29}

        margin = z * std / np.sqrt(n)
        return (float(mean), float(mean - margin), float(mean + margin))


# ============================================================
# 结果分析器
# ============================================================

class ResultAnalyzer:
    """结果分析器"""

    def __init__(self, results_dir: str = "results"):
        self.results_dir = Path(results_dir)

    def load_results(self) -> Dict:
        """加载实验结果"""
        summary_path = self.results_dir / "experiment_summary.json"
        if summary_path.exists():
            with open(summary_path, "r") as f:
                return json.load(f)
        return {}

    def generate_comparison_table(
        self,
        eh_data: np.ndarray,
        baselines: Dict[str, np.ndarray],
        metric_name: str = "ADT",
    ) -> str:
        """
        生成对比表 (LaTeX格式)

        输出格式类似论文 Table 1:
        Method | Mean±Std | Median | p-value | Cliff's δ
        """
        lines = []
        lines.append(r"\begin{table}[t]")
        lines.append(r"\centering")
        lines.append(f"\\caption{{{metric_name} 对比结果 (n=30)}}")
        lines.append(r"\begin{tabular}{lcccc}")
        lines.append(r"\toprule")
        lines.append(
            f"Method & {metric_name} (Mean$\\pm$Std) & Median & "
            r"$p$-value & Cliff's $\delta$ \\"
        )
        lines.append(r"\midrule")

        # EmergentHoney 行
        mean_eh, lo, hi = StatisticalTests.confidence_interval(eh_data)
        std_eh = np.std(eh_data)
        median_eh = np.median(eh_data)
        lines.append(
            f"\\textbf{{EmergentHoney}} & "
            f"\\textbf{{{mean_eh:.1f}$\\pm${std_eh:.1f}}} & "
            f"\\textbf{{{median_eh:.1f}}} & -- & -- \\\\"
        )

        # 基线行
        for name, data in baselines.items():
            mean_bl = np.mean(data)
            std_bl = np.std(data)
            median_bl = np.median(data)

            wilcox = StatisticalTests.wilcoxon_test(eh_data, data)
            cliff = StatisticalTests.cliffs_delta(eh_data, data)

            p_str = f"{wilcox['p_value']:.4f}"
            if wilcox["significant"]:
                p_str = f"\\textbf{{{p_str}}}"

            delta_str = f"{cliff['delta']:.3f} ({cliff['magnitude'][0].upper()})"

            lines.append(
                f"{name} & {mean_bl:.1f}$\\pm${std_bl:.1f} & "
                f"{median_bl:.1f} & {p_str} & {delta_str} \\\\"
            )

        lines.append(r"\bottomrule")
        lines.append(r"\end{tabular}")
        lines.append(r"\end{table}")

        return "\n".join(lines)

    def generate_convergence_analysis(
        self,
        convergence_data: Dict[int, List[int]],
    ) -> str:
        """生成收敛分析表"""
        lines = []
        lines.append(r"\begin{table}[t]")
        lines.append(r"\centering")
        lines.append(r"\caption{收敛分析 (不同网络规模)}")
        lines.append(r"\begin{tabular}{lccc}")
        lines.append(r"\toprule")
        lines.append(r"|V| & 收敛步数 (Mean$\pm$Std) & 95\% CI & 收敛率 \\")
        lines.append(r"\midrule")

        for size, steps in sorted(convergence_data.items()):
            data = np.array(steps)
            mean, lo, hi = StatisticalTests.confidence_interval(data)
            std = np.std(data)
            rate = mean / size  # 归一化收敛率

            lines.append(
                f"{size} & {mean:.0f}$\\pm${std:.0f} & "
                f"[{lo:.0f}, {hi:.0f}] & {rate:.3f} \\\\"
            )

        lines.append(r"\bottomrule")
        lines.append(r"\end{tabular}")
        lines.append(r"\end{table}")

        return "\n".join(lines)


# ============================================================
# 可视化生成器
# ============================================================

class VisualizationGenerator:
    """
    可视化生成器

    生成论文所需的所有图表 (matplotlib/pgfplots格式)
    """

    @staticmethod
    def plot_adt_comparison(
        results: Dict[str, np.ndarray],
        output_path: str = "fig_adt_comparison.pdf",
    ):
        """生成ADT对比柱状图 (Fig 4)"""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            methods = list(results.keys())
            means = [np.mean(v) for v in results.values()]
            stds = [np.std(v) for v in results.values()]

            fig, ax = plt.subplots(figsize=(10, 6))
            colors = ["#2196F3", "#9E9E9E", "#9E9E9E", "#9E9E9E", "#9E9E9E"]
            bars = ax.bar(methods, means, yerr=stds, capsize=5, color=colors[:len(methods)])

            ax.set_ylabel("Average Dwell Time (seconds)", fontsize=12)
            ax.set_title("Performance Comparison: Average Dwell Time", fontsize=14)
            ax.grid(axis="y", alpha=0.3)

            # 标注数值
            for bar, mean, std in zip(bars, means, stds):
                ax.text(
                    bar.get_x() + bar.get_width() / 2, bar.get_height() + std + 2,
                    f"{mean:.1f}", ha="center", va="bottom", fontsize=10,
                )

            plt.tight_layout()
            plt.savefig(output_path, dpi=300, bbox_inches="tight")
            plt.close()

            logger.info(f"[VIS] ADT对比图已保存: {output_path}")

        except ImportError:
            logger.warning("matplotlib未安装，跳过可视化生成")

    @staticmethod
    def plot_convergence_curve(
        pheromone_histories: List[List[float]],
        output_path: str = "fig_convergence.pdf",
    ):
        """生成收敛曲线 (Fig 5)"""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(10, 6))

            # 绘制每次运行的曲线 (半透明)
            for history in pheromone_histories:
                ax.plot(history, alpha=0.15, color="#2196F3", linewidth=0.5)

            # 绘制平均曲线
            max_len = max(len(h) for h in pheromone_histories)
            padded = [h + [h[-1]] * (max_len - len(h)) for h in pheromone_histories]
            mean_curve = np.mean(padded, axis=0)
            ax.plot(mean_curve, color="#1565C0", linewidth=2, label="Mean")

            # 收敛阈值线
            ax.axhline(y=0.05, color="red", linestyle="--",
                       alpha=0.7, label="Convergence threshold (5%)")

            ax.set_xlabel("Time Step", fontsize=12)
            ax.set_ylabel("Pheromone Change Rate", fontsize=12)
            ax.set_title("Convergence Analysis", fontsize=14)
            ax.legend()
            ax.grid(alpha=0.3)
            ax.set_ylim(0, 1)

            plt.tight_layout()
            plt.savefig(output_path, dpi=300, bbox_inches="tight")
            plt.close()

            logger.info(f"[VIS] 收敛曲线已保存: {output_path}")

        except ImportError:
            logger.warning("matplotlib未安装，跳过可视化生成")

    @staticmethod
    def plot_dei_evolution(
        dei_values: List[float],
        output_path: str = "fig_dei.pdf",
    ):
        """生成DEI演化曲线"""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, ax = plt.subplots(figsize=(10, 6))

            ax.plot(dei_values, color="#4CAF50", linewidth=2)
            ax.axhline(y=1.0, color="gray", linestyle="--",
                       alpha=0.5, label="DEI = 1 (no emergence)")
            ax.fill_between(
                range(len(dei_values)), 1.0, dei_values,
                where=[d > 1 for d in dei_values],
                alpha=0.2, color="#4CAF50", label="Emergence region"
            )

            ax.set_xlabel("Time Step", fontsize=12)
            ax.set_ylabel("Deception Emergence Index (DEI)", fontsize=12)
            ax.set_title("Deception Emergence Index Evolution", fontsize=14)
            ax.legend()
            ax.grid(alpha=0.3)

            plt.tight_layout()
            plt.savefig(output_path, dpi=300, bbox_inches="tight")
            plt.close()

            logger.info(f"[VIS] DEI曲线已保存: {output_path}")

        except ImportError:
            logger.warning("matplotlib未安装，跳过可视化生成")

    @staticmethod
    def plot_scalability(
        sizes: List[int],
        step_times: List[float],
        output_path: str = "fig_scalability.pdf",
    ):
        """生成可扩展性分析图"""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            fig, ax1 = plt.subplots(figsize=(10, 6))

            ax1.plot(sizes, step_times, "b-o", linewidth=2, markersize=8)
            ax1.set_xlabel("Network Size |V|", fontsize=12)
            ax1.set_ylabel("Average Step Time (ms)", fontsize=12, color="blue")
            ax1.tick_params(axis="y", labelcolor="blue")

            # 理论 O(|V|²) 曲线
            theoretical = [s**2 / sizes[0]**2 * step_times[0] for s in sizes]
            ax1.plot(sizes, theoretical, "r--", alpha=0.5, label="O(|V|²) reference")

            ax1.set_title("Scalability Analysis", fontsize=14)
            ax1.legend()
            ax1.grid(alpha=0.3)

            plt.tight_layout()
            plt.savefig(output_path, dpi=300, bbox_inches="tight")
            plt.close()

            logger.info(f"[VIS] 可扩展性图已保存: {output_path}")

        except ImportError:
            logger.warning("matplotlib未安装，跳过可视化生成")

    @staticmethod
    def plot_ablation_radar(
        results: Dict[str, Dict[str, float]],
        output_path: str = "fig_ablation_radar.pdf",
    ):
        """生成消融实验雷达图"""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt

            categories = ["ADT", "IR", "Convergence", "Prediction", "DEI"]
            num_vars = len(categories)

            angles = np.linspace(0, 2 * np.pi, num_vars, endpoint=False).tolist()
            angles += angles[:1]

            fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))

            for variant, metrics in results.items():
                values = [metrics.get(cat, 0) for cat in categories]
                values += values[:1]
                ax.plot(angles, values, linewidth=2, label=variant)
                ax.fill(angles, values, alpha=0.1)

            ax.set_xticks(angles[:-1])
            ax.set_xticklabels(categories, fontsize=11)
            ax.set_title("Ablation Study", fontsize=14, pad=20)
            ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))

            plt.tight_layout()
            plt.savefig(output_path, dpi=300, bbox_inches="tight")
            plt.close()

            logger.info(f"[VIS] 消融雷达图已保存: {output_path}")

        except ImportError:
            logger.warning("matplotlib未安装，跳过可视化生成")


# ============================================================
# 主分析流程
# ============================================================

def run_analysis(results_dir: str = "results"):
    """运行完整分析流程"""
    logging.basicConfig(level=logging.INFO)

    analyzer = ResultAnalyzer(results_dir)
    results = analyzer.load_results()

    if not results:
        logger.warning("未找到实验结果，请先运行实验")
        return

    # 生成统计检验结果
    logger.info("生成统计检验报告...")

    output_dir = Path(results_dir) / "analysis"
    output_dir.mkdir(exist_ok=True)

    # 汇总报告
    report_lines = [
        "# EmergentHoney 实验分析报告",
        "",
        "## 1. 核心性能对比",
        "",
    ]

    for exp_name, stats in results.items():
        report_lines.append(f"### {exp_name}")
        report_lines.append(f"- ADT: {stats['adt_mean']:.1f} ± {stats['adt_std']:.1f}")
        report_lines.append(f"- IR: {stats['ir_mean']:.3f} ± {stats['ir_std']:.1f}")
        report_lines.append(f"- 收敛步数: {stats['convergence_mean']:.0f}")
        report_lines.append(f"- 步耗时: {stats['avg_step_ms']:.2f} ms")
        report_lines.append("")

    report_path = output_dir / "analysis_report.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))

    logger.info(f"分析报告已保存: {report_path}")


if __name__ == "__main__":
    run_analysis()
