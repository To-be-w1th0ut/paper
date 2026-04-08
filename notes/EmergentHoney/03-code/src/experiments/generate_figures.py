#!/usr/bin/env python3
"""Generate publication-quality figures from experiment results."""

import json
import pathlib

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

# ---------------------------------------------------------------------------
# Global style
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "font.size": 9,
    "font.family": "serif",
    "axes.labelsize": 9,
    "axes.titlesize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 7.5,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linewidth": 0.5,
})

# Professional color palette (colorblind-friendly)
COLORS = [
    "#4C72B0",  # blue
    "#55A868",  # green
    "#C44E52",  # red
    "#8172B2",  # purple
    "#CCB974",  # gold
    "#64B5CD",  # light-blue
    "#DD8452",  # orange
]

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA_PATH = ROOT / "results" / "full_experiment_results.json"
FIG_DIR = ROOT / "figures"
FIG_DIR.mkdir(exist_ok=True)


def load_data():
    with open(DATA_PATH) as f:
        return json.load(f)


def save(fig, name):
    """Save figure as PDF and PNG."""
    fig.savefig(FIG_DIR / f"{name}.pdf")
    fig.savefig(FIG_DIR / f"{name}.png")
    plt.close(fig)
    print(f"  saved {name}.pdf / .png")


# ===== Figure 4: ADT comparison bar chart =====
def fig4_adt_comparison(data):
    t3 = data["table3"]
    methods = ["B1_Static", "B2_RandomDynamic", "B3_RL",
               "B4_GameTheoretic", "B5_GAN", "B6_LLMStatic", "EmergentHoney"]
    labels = ["B1\nStatic", "B2\nRandDyn", "B3\nRL", "B4\nGameTh",
              "B5\nGAN", "B6\nLLM", "Emergent\nHoney"]

    means = [np.mean(t3[m]["adt"]) for m in methods]
    stds = [np.std(t3[m]["adt"], ddof=1) for m in methods]

    fig, ax = plt.subplots(figsize=(3.5, 2.2))
    x = np.arange(len(methods))
    bars = ax.bar(x, means, yerr=stds, width=0.6, capsize=3,
                  color=COLORS[:len(methods)], edgecolor="white", linewidth=0.5,
                  error_kw=dict(lw=0.8, capthick=0.8))

    # Highlight EmergentHoney bar
    bars[-1].set_edgecolor("#333333")
    bars[-1].set_linewidth(1.0)

    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("ADT (hours)")
    ax.set_ylim(0, max(means) * 1.25)
    fig.tight_layout()
    save(fig, "fig4_adt_comparison")


# ===== Figure 5: DEI evolution over time =====
def fig5_dei_evolution(data):
    dei = data["table5_dei"]
    hours = [0, 2, 6, 12, 24, 48, 72]
    means = [dei[str(h)]["mean"] for h in hours]
    stds = [dei[str(h)]["std"] for h in hours]
    means = np.array(means)
    stds = np.array(stds)

    fig, ax = plt.subplots(figsize=(3.5, 2.2))
    ax.plot(hours, means, "-o", color=COLORS[6], markersize=4, linewidth=1.5,
            label="DEI", zorder=3)
    ax.fill_between(hours, means - stds, means + stds,
                    color=COLORS[6], alpha=0.2)

    ax.set_xlabel("Time (hours)")
    ax.set_ylabel("Deception Effectiveness Index")
    ax.set_xticks(hours)
    ax.set_ylim(0, max(means + stds) * 1.15)
    ax.legend(loc="lower right", framealpha=0.9)
    fig.tight_layout()
    save(fig, "fig5_dei_evolution")


# ===== Figure 6: Ablation study =====
def fig6_ablation(data):
    abl = data["table7_ablation"]
    variants = ["Full", "w/o Pheromone", "w/o LLM", "w/o RevACO", "w/o AdaptRho"]
    labels = ["Full", "w/o\nPheromone", "w/o\nLLM", "w/o\nRevACO", "w/o\nAdaptRho"]

    adt_vals = [abl[v]["adt_mean"] for v in variants]
    hir_vals = [abl[v]["hir_mean"] for v in variants]

    fig, ax1 = plt.subplots(figsize=(3.5, 2.4))
    x = np.arange(len(variants))
    w = 0.35

    b1 = ax1.bar(x - w / 2, adt_vals, w, color=COLORS[0], label="ADT (hours)",
                 edgecolor="white", linewidth=0.5)
    ax1.set_ylabel("ADT (hours)", color=COLORS[0])
    ax1.tick_params(axis="y", labelcolor=COLORS[0])
    ax1.set_ylim(0, max(adt_vals) * 1.3)

    ax2 = ax1.twinx()
    b2 = ax2.bar(x + w / 2, hir_vals, w, color=COLORS[2], label="HIR (%)",
                 edgecolor="white", linewidth=0.5)
    ax2.set_ylabel("HIR (%)", color=COLORS[2])
    ax2.tick_params(axis="y", labelcolor=COLORS[2])
    ax2.set_ylim(0, max(hir_vals) * 1.3)
    ax2.spines["right"].set_visible(True)

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)

    lines = [b1, b2]
    labs = [l.get_label() for l in lines]
    ax1.legend(lines, labs, loc="upper right", framealpha=0.9)
    fig.tight_layout()
    save(fig, "fig6_ablation")


# ===== Figure 7: Scalability =====
def fig7_scalability(data):
    sc = data["table8_scale"]
    sizes = ["Small", "Medium", "Large"]
    nodes = [sc[s]["nodes"] for s in sizes]
    metrics = {
        "ADT (h)": [sc[s]["adt"] for s in sizes],
        "HIR (%)": [sc[s]["hir"] for s in sizes],
        "DEI": [sc[s]["dei"] for s in sizes],
    }

    fig, axes = plt.subplots(1, 3, figsize=(3.5, 2.0), sharey=False)
    x = np.arange(len(sizes))
    w = 0.5

    for idx, (metric_name, vals) in enumerate(metrics.items()):
        ax = axes[idx]
        ax.bar(x, vals, w, color=COLORS[idx], edgecolor="white", linewidth=0.5)
        ax.set_xticks(x)
        ax.set_xticklabels([f"{s}\n({n})" for s, n in zip(sizes, nodes)], fontsize=6.5)
        ax.set_title(metric_name, fontsize=8)
        ax.set_ylim(0, max(vals) * 1.25)

    fig.tight_layout(w_pad=0.8)
    save(fig, "fig7_scalability")


# ===== Figure 8: Arms race =====
def fig8_arms_race(data):
    arms = data["table9_arms"]
    windows = ["0-6h", "6-12h", "12-18h", "18-24h", "24-48h", "48-72h"]
    x_labels = windows

    fig, ax = plt.subplots(figsize=(3.5, 2.2))

    for method, color, marker in [("EmergentHoney", COLORS[6], "o"),
                                   ("B3_RL", COLORS[0], "s")]:
        means = np.array([arms[method][w]["mean"] for w in windows])
        stds = np.array([arms[method][w]["std"] for w in windows])
        label = "EmergentHoney" if method == "EmergentHoney" else "B3 (RL)"
        ax.plot(range(len(windows)), means, f"-{marker}", color=color,
                markersize=4, linewidth=1.5, label=label, zorder=3)
        ax.fill_between(range(len(windows)), means - stds, means + stds,
                        color=color, alpha=0.15)

    ax.set_xticks(range(len(windows)))
    ax.set_xticklabels(x_labels, rotation=30, ha="right")
    ax.set_xlabel("Time Window")
    ax.set_ylabel("ADT (hours)")
    ax.legend(loc="upper left", framealpha=0.9)
    ax.set_ylim(0, 5.5)
    fig.tight_layout()
    save(fig, "fig8_arms_race")


# ===== Main =====
def main():
    data = load_data()
    print("Generating figures...")
    fig4_adt_comparison(data)
    fig5_dei_evolution(data)
    fig6_ablation(data)
    fig7_scalability(data)
    fig8_arms_race(data)
    print("Done.")


if __name__ == "__main__":
    main()
