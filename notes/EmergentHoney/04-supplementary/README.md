# EmergentHoney — Supplementary Materials

## Code Repository Structure

```
src/
├── core/
│   ├── pheromone_engine.py    # 信息素引擎 + 自组织管理器 (Algorithm 1)
│   └── reverse_aco.py         # 反向蚁群攻击者建模 (Algorithm 2)
├── llm/
│   └── phenotype_generator.py # LLM驱动蜜罐表型生成 (Section IV-B)
├── network/
│   ├── sdn_topology.py        # SDN网络拓扑管理
│   └── honeypot_deployer.py   # 蜜罐实例生命周期管理
├── experiments/
│   ├── experiment_runner.py   # 实验运行器 (Section VI 全部实验)
│   └── analysis.py            # 统计检验 + 可视化
└── utils/
```

## Dependencies

```
numpy>=1.24.0
scipy>=1.10.0        # 用于 Wilcoxon 检验
matplotlib>=3.7.0    # 用于图表生成 (可选)
```

Optional (for full deployment):
```
docker>=6.0.0        # 真实蜜罐容器部署
openai>=1.0.0        # GPT-4 表型生成
mininet>=2.3.0       # SDN网络仿真
```

## Reproducing Experiments

### Canonical Manuscript Artifacts

The authoritative manuscript figures and summary tables are regenerated from:

- `06-results/full_experiment_results.json`
- `03-code/src/experiments/generate_figures.py`
- `03-code/src/experiments/generate_tables.py`

This is the recommended path for reproducing the exact numbers shown in the
paper.

Recommended environment setup:

```bash
cd 03-code
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Quick Start (机制模拟)

```bash
cd 03-code
source .venv/bin/activate
python -m src.experiments.experiment_runner
```

This runs the prototype pheromone-driven simulation with default parameters:
- |V| = 50 nodes, |H| = 8 types, B = 15 budget
- 5 attackers, 200 time steps, 30 independent runs
- Results saved to `results/experiment_summary.json`

### Full Manuscript Artifact Regeneration

```bash
source 03-code/.venv/bin/activate
python 03-code/src/experiments/generate_tables.py
python 03-code/src/experiments/generate_figures.py
```

### Prototype Runner Configuration

```python
from src.experiments.experiment_runner import ExperimentRunner, ExperimentConfig

config = ExperimentConfig(
    num_nodes=50,       # Table 1-2: Small network
    num_hp_types=8,
    budget=15,
    num_attackers=5,
    attacker_sophistication=0.5,
    num_steps=200,
    num_runs=30,
    random_seed=42,
    output_dir="results_paper",
)

runner = ExperimentRunner(config)
runner.run_all_experiments()
```

### Scalability Experiments

The experiment runner automatically tests |V| ∈ {50, 200, 500}.

### Analysis & Visualization

```bash
python -m src.experiments.analysis
```

Generates:
- Statistical test results (Wilcoxon, Cliff's δ)
- LaTeX tables ready for paper inclusion
- Matplotlib figures (if matplotlib available)

## Key Parameters (Table of Paper Notation)

| Symbol | Parameter | Default | Description |
|--------|-----------|---------|-------------|
| ρ | evaporation_rate | 0.05 | Pheromone evaporation rate |
| Q | Q | 100.0 | Pheromone deposit constant |
| Δ_max | delta_max | 50.0 | Maximum single deposit |
| α | alpha | 1.0 | Pheromone weight exponent |
| β | beta | 2.0 | Heuristic weight exponent |
| θ_p | theta_prolif | 0.7 | Proliferation threshold ratio |
| θ_m | theta_migrate | 0.2 | Migration threshold ratio |
| θ_μ | theta_mutate | 0.5 | Mutation threshold ratio |
| B | budget | 15 | Honeypot deployment budget |
| ρ_a | rho_a (reverse) | 0.1 | Attacker pheromone evaporation |

## Data Description

Experiment outputs in `results/`:
- `experiment_summary.json`: Aggregated statistics for all experiments
- `results/analysis/`: Statistical test reports and figures

The canonical manuscript bundle records:
- Average Dwell Time (ADT) in hours
- Honeypot Identification Rate (HIR)
- Threat Intelligence Collection (TIC)
- DEI values
- Scalability summaries
- Arms-race trajectories

## Ethical Statement

All experiments were conducted on isolated simulated networks.
No real attacker data or production systems were involved.
The deception techniques are purely defensive in nature.

## License

This code is provided for academic research purposes.
Please cite the paper if you use this code in your work.
