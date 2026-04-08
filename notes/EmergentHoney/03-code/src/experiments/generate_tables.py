#!/usr/bin/env python3
"""Generate canonical manuscript tables from full_experiment_results.json."""

from __future__ import annotations

import json
import pathlib
from statistics import mean


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[3]
DATA_PATH = PROJECT_ROOT / "06-results" / "full_experiment_results.json"
TEX_PATH = PROJECT_ROOT / "02-tex" / "generated_results_tables.tex"
MD_PATH = PROJECT_ROOT / "05-meta" / "generated_results_summary.md"


METHOD_LABELS = {
    "B1_Static": "B1: Static",
    "B2_RandomDynamic": "B2: Random-Dynamic",
    "B3_RL": "B3: RL-Honeypot",
    "B4_GameTheoretic": "B4: Game-Theoretic",
    "B5_GAN": "B5: GAN-Honeypot",
    "B6_LLMStatic": "B6: LLM-Static",
    "EmergentHoney": "EmergentHoney",
}


def load_data() -> dict:
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def fmt(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}"


def build_rq1_table(data: dict) -> list[str]:
    t3 = data["table3"]
    ordered = [
        "B1_Static",
        "B2_RandomDynamic",
        "B3_RL",
        "B4_GameTheoretic",
        "B5_GAN",
        "B6_LLMStatic",
        "EmergentHoney",
    ]
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Overall Deception Effectiveness (Canonical Result Bundle)}",
        r"\small",
        r"\begin{tabular}{@{}lccc@{}}",
        r"\toprule",
        r"Method & ADT (hours) & HIR (\%) & TIC \\",
        r"\midrule",
    ]
    for key in ordered:
        row = t3[key]
        lines.append(
            f"{METHOD_LABELS[key]} & "
            f"{fmt(mean(row['adt']))} $\\pm$ {fmt(_std(row['adt']))} & "
            f"{fmt(mean(row['hir']), 1)} $\\pm$ {fmt(_std(row['hir']), 1)} & "
            f"{fmt(mean(row['tic']), 0)} $\\pm$ {fmt(_std(row['tic']), 0)} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    return lines


def build_dei_table(data: dict) -> list[str]:
    dei = data["table5_dei"]
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{DEI Over Time (Canonical Result Bundle)}",
        r"\small",
        r"\begin{tabular}{@{}cc@{}}",
        r"\toprule",
        r"Time (hours) & DEI \\",
        r"\midrule",
    ]
    for hour in [0, 2, 6, 12, 24, 48, 72]:
        row = dei[str(hour)]
        lines.append(f"{hour} & {fmt(row['mean'])} $\\pm$ {fmt(row['std'])} \\\\")
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    return lines


def build_rho_table(data: dict) -> list[str]:
    rho = data["table6_rho"]
    ordered = ["0.01", "0.05", "0.1", "0.2", "0.5"]
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Evaporation Rate Sensitivity (Canonical Result Bundle)}",
        r"\small",
        r"\begin{tabular}{@{}ccccc@{}}",
        r"\toprule",
        r"$\rho$ & $t_{\mathrm{conv}}$ (h) & DEI & ADT (hours) & HIR (\%) \\",
        r"\midrule",
    ]
    for key in ordered:
        row = rho[key]
        lines.append(
            f"{key} & {fmt(row['conv_mean'], 1)} & {fmt(row['dei_mean'])} & "
            f"{fmt(row['adt_mean'])} & {fmt(row['hir_mean'], 1)} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    return lines


def build_ablation_table(data: dict) -> list[str]:
    abl = data["table7_ablation"]
    ordered = ["Full", "w/o Pheromone", "w/o LLM", "w/o RevACO", "w/o AdaptRho"]
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Ablation Summary (Canonical Result Bundle)}",
        r"\small",
        r"\begin{tabular}{@{}lccc@{}}",
        r"\toprule",
        r"Variant & ADT (hours) & HIR (\%) & DEI \\",
        r"\midrule",
    ]
    for key in ordered:
        row = abl[key]
        lines.append(
            f"{key} & {fmt(row['adt_mean'])} & {fmt(row['hir_mean'], 1)} & {fmt(row['dei_mean'])} \\\\"
        )
    lines.extend([r"\bottomrule", r"\end{tabular}", r"\end{table}"])
    return lines


def build_scale_table(data: dict) -> list[str]:
    scale = data["table8_scale"]
    ordered = ["Small", "Medium", "Large"]
    lines = [
        r"\begin{table}[t]",
        r"\centering",
        r"\caption{Scalability Summary (Canonical Result Bundle)}",
        r"\small",
        r"\begin{tabular}{@{}lccc@{}}",
        r"\toprule",
        r"Metric & Small (50) & Medium (200) & Large (500) \\",
        r"\midrule",
        f"ADT (hours) & {fmt(scale['Small']['adt'])} & {fmt(scale['Medium']['adt'])} & {fmt(scale['Large']['adt'])} \\\\",
        f"HIR (\\%) & {fmt(scale['Small']['hir'], 1)} & {fmt(scale['Medium']['hir'], 1)} & {fmt(scale['Large']['hir'], 1)} \\\\",
        f"TIC & {fmt(scale['Small']['tic'], 0)} & {fmt(scale['Medium']['tic'], 0)} & {fmt(scale['Large']['tic'], 0)} \\\\",
        f"DEI & {fmt(scale['Small']['dei'])} & {fmt(scale['Medium']['dei'])} & {fmt(scale['Large']['dei'])} \\\\",
        f"$t_{{\\mathrm{{conv}}}}$ (h) & {fmt(scale['Small']['conv_h'], 1)} & {fmt(scale['Medium']['conv_h'], 1)} & {fmt(scale['Large']['conv_h'], 1)} \\\\",
        f"Update time (ms) & {fmt(scale['Small']['step_ms'], 1)} & {fmt(scale['Medium']['step_ms'], 1)} & {fmt(scale['Large']['step_ms'], 1)} \\\\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{table}",
    ]
    return lines


def build_markdown_summary(data: dict) -> list[str]:
    t3 = data["table3"]
    eh = t3["EmergentHoney"]
    rl = t3["B3_RL"]
    lines = [
        "# Canonical Results Summary",
        "",
        f"- EmergentHoney ADT: {fmt(mean(eh['adt']))} h",
        f"- RL baseline ADT: {fmt(mean(rl['adt']))} h",
        f"- EmergentHoney HIR: {fmt(mean(eh['hir']), 1)}%",
        f"- RL baseline HIR: {fmt(mean(rl['hir']), 1)}%",
        f"- Peak DEI: {fmt(data['table5_dei']['48']['mean'])}",
        "",
        "This summary is generated directly from `06-results/full_experiment_results.json`.",
    ]
    return lines


def _std(values: list[float]) -> float:
    if len(values) <= 1:
        return 0.0
    avg = mean(values)
    return (sum((v - avg) ** 2 for v in values) / (len(values) - 1)) ** 0.5


def main() -> None:
    data = load_data()
    TEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    tex_lines = []
    for block in (
        build_rq1_table(data),
        build_dei_table(data),
        build_rho_table(data),
        build_ablation_table(data),
        build_scale_table(data),
    ):
        tex_lines.extend(block)
        tex_lines.append("")

    TEX_PATH.write_text("\n".join(tex_lines), encoding="utf-8")
    MD_PATH.write_text("\n".join(build_markdown_summary(data)), encoding="utf-8")
    print(f"saved {TEX_PATH}")
    print(f"saved {MD_PATH}")


if __name__ == "__main__":
    main()
