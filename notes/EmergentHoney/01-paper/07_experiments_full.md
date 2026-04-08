# VI. Experimental Evaluation

## A. Study Design and Positioning

This version of the paper reports an **SDN-informed emulation study**. The repository contains:

- a prototype simulator for pheromone-driven honeypot self-organization,
- a canonical result bundle (`06-results/full_experiment_results.json`),
- scripts that regenerate the manuscript figures from that bundle.

We do **not** present this version as a completed production deployment or a finished hardware-backed SDN deployment campaign.

## B. Canonical Setup

| Component | Configuration Used in the Canonical Study |
|-----------|-------------------------------------------|
| Topology sizes | 50 / 200 / 500 nodes |
| Honeypot budget | 10 / 30 / 80 |
| Horizon | 72 simulated hours |
| Runs | 30 seeds for the main comparison |
| Attacker types | L1, L2, L3 |
| Comparison set | Static, Random-Dynamic, RL, Game-Theoretic, GAN, LLM-Static, EmergentHoney |

## C. RQ1: Overall Effectiveness

| Method | ADT (hours) ↑ | HIR (%) ↓ | TIC ↑ |
|--------|:---:|:---:|:---:|
| Static | 1.57 ± 0.11 | 42.9 ± 5.2 | 91 ± 11 |
| Random-Dynamic | 1.55 ± 0.10 | 35.1 ± 4.5 | 107 ± 11 |
| RL-Honeypot | 1.66 ± 0.10 | 28.1 ± 4.7 | 118 ± 15 |
| Game-Theoretic | 1.59 ± 0.10 | 30.3 ± 4.7 | 113 ± 10 |
| GAN-Honeypot | 1.76 ± 0.11 | 31.7 ± 4.6 | 110 ± 13 |
| LLM-Static | 2.43 ± 0.12 | 22.9 ± 3.3 | 128 ± 10 |
| **EmergentHoney** | **3.24 ± 0.16** | **8.0 ± 2.1** | **158 ± 20** |

Compared with the strongest adaptive baseline (RL-Honeypot), EmergentHoney improves ADT by roughly **96%**, reduces HIR by **71%**, and increases TIC by **34%**. Compared with LLM-Static, it still gains **34%** ADT, indicating that the topology mechanism contributes beyond content realism alone.

## D. RQ2: Emergence Over Time

| Time (hours) | DEI |
|:---:|:---:|
| 0 | 1.00 ± 0.00 |
| 2 | 2.01 ± 0.76 |
| 6 | 1.93 ± 0.59 |
| 12 | 1.90 ± 0.40 |
| 24 | 2.10 ± 0.24 |
| 48 | 2.24 ± 0.24 |
| 72 | 2.00 ± 0.16 |

The swarm reaches positive emergence rapidly and maintains a DEI near **2.0**, meaning the coordinated swarm roughly doubles the deception capability implied by isolated honeypot measurements.

## E. RQ3: Ablation

| Variant | ADT (hours) | HIR (%) | DEI | ΔADT vs Full |
|---------|:---:|:---:|:---:|:---:|
| **Full EmergentHoney** | **3.32** | **8.9** | **2.00** | — |
| w/o Pheromone | 1.65 | 42.9 | 0.90 | -50.3% |
| w/o LLM | 2.09 | 22.9 | 1.97 | -37.2% |
| w/o Reverse-ACO | 3.36 | 14.0 | 1.92 | +1.1% |
| w/o Adaptive-ρ | 3.30 | 10.1 | 1.96 | -0.7% |

The key ablation result is unambiguous: **the pheromone mechanism is the only removal that pushes DEI below 1.0 and cuts ADT in half**. That is the empirical basis for treating pheromone-driven self-organization as the paper's main contribution.

## F. RQ4: Scalability

| Metric | Small (50) | Medium (200) | Large (500) |
|--------|:---:|:---:|:---:|
| ADT (hours) | 3.21 | 3.46 | 3.37 |
| HIR (%) | 8.6 | 8.7 | 9.0 |
| TIC | 64 | 144 | 410 |
| DEI | 1.99 | 1.76 | 1.95 |
| Convergence (hours) | 15.1 | 9.4 | 6.3 |
| Update time (ms) | 1.4 | 4.1 | 13.1 |

Performance remains stable across scales in the canonical result bundle, with computation cost still comfortably within real-time decision windows.

## G. RQ5: Adaptive Attackers

Against L3 adaptive attackers, EmergentHoney maintains ADT between **3.70 h** and **4.00 h** across all windows, while the RL baseline remains near **1.8-1.95 h**. In this version of the study, Reverse-ACO appears to contribute more to identification resistance than to raw dwell time.

## H. Current Takeaway

The canonical evidence supports a focused claim:

**EmergentHoney should be read primarily as a pheromone-driven decentralized deception-topology mechanism, with the phenotype layer and reverse-trajectory predictor acting as supporting components.**
