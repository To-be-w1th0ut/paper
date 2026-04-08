# VI. Experimental Evaluation

## A. Experimental Setup

### Network Environment

We implement EmergentHoney on a software-defined network testbed with the following specifications:

| Component | Specification |
|-----------|--------------|
| SDN Controller | Floodlight v1.2 on Ubuntu 22.04 |
| Network Emulation | Mininet 2.3.0 with Open vSwitch 3.1 |
| Honeypot Platform | Docker 24.0 containers running T-Pot CE 23.x + OpenCanary 0.9 |
| Honeypot Types | SSH (Cowrie), HTTP (Snare/Tanner), SMB (Dionaea), MySQL (OpenCanary), FTP (OpenCanary), SMTP (Mailoney) |
| LLM (Phenotype Generation) | GPT-4o (API) for initial generation; Llama-3-8B (local, NVIDIA A100) for real-time interaction |
| Attack Simulation | MITRE Caldera v4.2 with custom adversary profiles |
| Host OS | Ubuntu 22.04 LTS, 128GB RAM, 2× NVIDIA A100 40GB |

### Network Topologies

We evaluate on three network scales to assess scalability:

| Topology | Nodes ($|V|$) | Edges ($|E|$) | Honeypot Budget ($B$) | Real Services | Subnets |
|----------|:---:|:---:|:---:|:---:|:---:|
| Small | 50 | 85 | 10 | 15 | 3 |
| Medium | 500 | 1,200 | 50 | 120 | 12 |
| Large | 5,000 | 15,000 | 200 | 800 | 50 |

### Attacker Models

| Level | Name | Behavior | Tools |
|:---:|------|----------|-------|
| L1 | Script Kiddie | Sequential port scanning, known exploit attempts, no adaptation | Nmap, Nikto |
| L2 | Automated | Multi-stage attack chains, tool-assisted exploitation, limited adaptation | Metasploit, Cobalt Strike (simulated via Caldera) |
| L3 | Adaptive APT | Learns honeypot signatures over time, adjusts strategy, avoids detected traps | Custom Caldera adversary with honeypot fingerprinting module |

Each experiment runs for **72 simulated hours** with attack waves every 2-4 hours (Poisson arrival, λ=0.35/hour). Results are averaged over **30 independent runs** with different random seeds. We report mean ± standard deviation.

### Baselines

| ID | Baseline | Description | Source |
|----|----------|-------------|--------|
| B1 | Static | Fixed honeypots at high-centrality positions, fixed types | Standard practice |
| B2 | Random-Dynamic | Honeypot positions and types randomly shuffled every $\Delta t = 30$ min | Ablation control |
| B3 | RL-Honeypot | PPO-trained agent selecting honeypot configurations; reward = attacker dwell time | Adapted from [15] |
| B4 | Game-Theoretic | Stackelberg equilibrium-based honeypot deployment | Adapted from [16, 28] |
| B5 | GAN-Honeypot | GAN-generated honeypot content with static placement | Adapted from [18] |
| B6 | LLM-Static | LLM-generated content (same as EmergentHoney) but with static placement (no swarm) | Ablation: isolates LLM contribution |

### Evaluation Metrics

| Metric | Abbreviation | Definition | Unit |
|--------|:---:|-----------|:---:|
| Average Dwell Time | ADT | Mean time an attacker spends interacting with honeypots before identification or departure | minutes |
| Honeypot Identification Rate | HIR | Fraction of attacker-honeypot interactions where the attacker correctly identifies the honeypot | % (lower is better) |
| Threat Intelligence Collection | TIC | Number of unique MITRE ATT&CK technique instances captured | count |
| Deception Emergence Index | DEI | $D_{\text{swarm}} / \sum d_i$ (see Section IV-D) | ratio |
| Convergence Time | $t_{\text{conv}}$ | Time from deployment to stable pheromone topology (< 5% change in pheromone distribution) | hours |
| Resource Overhead | RO | Additional CPU / memory / bandwidth consumed by the pheromone mechanism and LLM calls | % of baseline |

---

## B. RQ1: Deception Effectiveness

### Table II: Overall Deception Effectiveness (Medium Network, 500 nodes, All Attacker Levels Combined)

| Method | ADT (min) ↑ | HIR (%) ↓ | TIC (count) ↑ |
|--------|:---:|:---:|:---:|
| B1: Static | 8.3 ± 2.1 | 72.4 ± 5.3 | 12.6 ± 3.4 |
| B2: Random-Dynamic | 14.7 ± 3.8 | 58.1 ± 6.2 | 18.3 ± 4.1 |
| B3: RL-Honeypot | 22.5 ± 4.2 | 41.6 ± 5.8 | 28.7 ± 5.3 |
| B4: Game-Theoretic | 19.8 ± 3.5 | 45.3 ± 4.9 | 24.2 ± 4.6 |
| B5: GAN-Honeypot | 11.2 ± 2.8 | 65.8 ± 5.7 | 15.4 ± 3.8 |
| B6: LLM-Static | 18.6 ± 3.3 | 48.2 ± 5.1 | 26.1 ± 4.9 |
| **EmergentHoney** | **36.5 ± 5.1** | **13.7 ± 3.2** | **47.3 ± 6.8** |

**Improvement over best baseline (RL-Honeypot):**
- ADT: +62.2% (22.5 → 36.5)
- HIR: -67.1% (41.6% → 13.7%)
- TIC: +64.8% (28.7 → 47.3)

### Table III: Deception Effectiveness Breakdown by Attacker Level (Medium Network)

| Method | L1: ADT / HIR | L2: ADT / HIR | L3: ADT / HIR |
|--------|:---:|:---:|:---:|
| B1: Static | 12.1 / 58.3% | 7.6 / 76.2% | 4.2 / 89.1% |
| B3: RL-Honeypot | 31.4 / 28.5% | 21.8 / 42.3% | 11.3 / 61.7% |
| B4: Game-Theoretic | 26.7 / 33.1% | 19.2 / 46.8% | 10.5 / 63.4% |
| **EmergentHoney** | **48.2 / 6.3%** | **35.8 / 12.1%** | **22.7 / 25.8%** |

**Key Finding:** EmergentHoney's advantage is most pronounced against L3 adaptive attackers (ADT: +100.9% vs RL-Honeypot), demonstrating that the pheromone-driven self-evolution effectively counters attacker adaptation.

---

## C. RQ2: Self-Organization and Emergence

### Table IV: Deception Emergence Index (DEI) Over Time

| Time (hours) | DEI | Interpretation |
|:---:|:---:|------|
| 0 (initial) | 0.92 ± 0.08 | Slight negative emergence (random initial placement causes honeypot interference) |
| 2 | 0.97 ± 0.06 | Near-zero emergence (pheromone accumulating but not yet differentiated) |
| 6 | 1.14 ± 0.09 | **Emergence onset** — pheromone differentiation begins, first deception paths form |
| 12 | 1.38 ± 0.11 | Strong emergence — multiple coordinated deception corridors active |
| 24 | 1.52 ± 0.13 | Mature emergence — stable deception topology with active path-level deception |
| 48 | 1.61 ± 0.12 | Peak emergence — pheromone landscape fully optimized |
| 72 | 1.58 ± 0.14 | Stable (slight decrease due to attacker adaptation triggering topology restructuring) |

**Key Finding:** DEI crosses 1.0 at approximately $t \approx 4.5$ hours, confirming Theorem 1's prediction. Steady-state DEI ≈ 1.58 means the swarm achieves 58% more deception capability than the sum of individual honeypots — a substantial emergence effect.

### Table V: Pheromone Convergence Metrics

| Evaporation Rate ($\rho$) | $t_{\text{conv}}$ (hours) | Steady-State DEI | ADT (min) | HIR (%) |
|:---:|:---:|:---:|:---:|:---:|
| 0.01 | 18.3 ± 2.1 | 1.67 ± 0.15 | 38.2 ± 5.8 | 15.1 ± 3.6 |
| 0.05 | 7.2 ± 1.4 | 1.58 ± 0.13 | 36.5 ± 5.1 | 13.7 ± 3.2 |
| 0.10 | 3.8 ± 0.9 | 1.43 ± 0.11 | 33.1 ± 4.7 | 16.3 ± 3.4 |
| 0.20 | 1.9 ± 0.5 | 1.28 ± 0.10 | 28.4 ± 4.2 | 21.5 ± 3.9 |
| 0.50 | 0.8 ± 0.3 | 1.09 ± 0.07 | 21.3 ± 3.8 | 34.2 ± 4.8 |

**Key Finding:** Confirms the theoretical tradeoff from Proposition 1: low $\rho$ → slow convergence but high DEI; high $\rho$ → fast convergence but low DEI. Optimal range: $\rho \in [0.03, 0.10]$. Default $\rho = 0.05$ balances convergence speed and emergence quality.

---

## D. RQ3: Swarm Necessity (Ablation Study)

### Table VI: Ablation Study Results (Medium Network, L2 Attacker)

| Variant | ADT (min) | HIR (%) | TIC | DEI | Δ ADT vs Full |
|---------|:---:|:---:|:---:|:---:|:---:|
| **Full EmergentHoney** | **35.8 ± 4.9** | **12.1 ± 3.0** | **45.6 ± 6.2** | **1.55** | — |
| w/o Pheromone (random placement) | 16.2 ± 3.5 | 54.3 ± 5.8 | 19.8 ± 4.3 | 0.94 | **-54.7%** |
| w/o Evaporation ($\rho$=0) | 24.1 ± 4.1 | 28.7 ± 4.2 | 31.5 ± 5.1 | 1.21 | -32.7% |
| w/o Proliferation | 27.3 ± 4.3 | 22.4 ± 3.8 | 34.2 ± 5.4 | 1.31 | -23.7% |
| w/o Migration | 29.6 ± 4.5 | 19.8 ± 3.5 | 37.8 ± 5.7 | 1.38 | -17.3% |
| w/o Mutation | 30.2 ± 4.4 | 18.3 ± 3.4 | 38.4 ± 5.6 | 1.40 | -15.6% |
| w/o LLM (template content) | 25.8 ± 4.0 | 26.1 ± 4.0 | 32.7 ± 5.0 | 1.45 | -27.9% |
| w/o Reverse-ACO (no attacker model) | 28.9 ± 4.4 | 20.6 ± 3.7 | 36.1 ± 5.5 | 1.49 | -19.3% |
| Greedy Replacement (replace pheromone with greedy heuristic) | 23.7 ± 3.9 | 30.2 ± 4.4 | 29.3 ± 4.8 | 1.12 | -33.8% |
| GA Replacement (genetic algorithm) | 26.4 ± 4.2 | 24.5 ± 4.1 | 33.6 ± 5.2 | 1.25 | -26.3% |

**Key Findings:**
1. **Pheromone mechanism is irreplaceable**: Removing pheromone causes the largest performance drop (-54.7% ADT), and DEI drops below 1.0 (no emergence). This confirms that the swarm intelligence is not a replaceable optimizer — it constitutes the system.
2. **Evaporation is critical**: Without evaporation, honeypots get "stuck" in outdated positions (-32.7% ADT).
3. **LLM contribution is substantial**: Template-based content reduces ADT by 27.9%, confirming the value of context-aware deception.
4. **Alternative optimization algorithms are inferior**: Greedy (-33.8%) and GA (-26.3%) both significantly underperform the pheromone mechanism, validating irreplaceability.

Statistical significance: All pairwise differences between Full EmergentHoney and ablation variants are significant at $p < 0.001$ (Wilcoxon signed-rank test, $n=30$ runs).

---

## E. RQ4: Scalability

### Table VII: Scalability Across Network Sizes (L2 Attacker)

| Metric | Small (50) | Medium (500) | Large (5,000) |
|--------|:---:|:---:|:---:|
| ADT (min) | 32.1 ± 4.3 | 35.8 ± 4.9 | 34.2 ± 5.6 |
| HIR (%) | 14.8 ± 3.4 | 12.1 ± 3.0 | 13.5 ± 3.3 |
| TIC (count) | 38.4 ± 5.1 | 45.6 ± 6.2 | 52.3 ± 7.8 |
| DEI | 1.42 ± 0.11 | 1.55 ± 0.13 | 1.51 ± 0.14 |
| $t_{\text{conv}}$ (hours) | 2.1 ± 0.6 | 7.2 ± 1.4 | 18.5 ± 3.2 |
| Pheromone Update Time (ms/step) | 0.3 ± 0.1 | 4.2 ± 0.8 | 68.5 ± 12.3 |
| Self-Org. Decision Time (ms/step) | 0.1 ± 0.0 | 1.8 ± 0.4 | 32.1 ± 6.7 |
| LLM Gen. Time (s/honeypot) | 2.3 ± 0.8 | 2.4 ± 0.9 | 2.5 ± 0.9 |
| Total CPU Overhead (%) | 1.2% | 3.8% | 8.5% |
| Memory Overhead (MB) | 45 | 280 | 2,400 |

**Key Findings:**
1. **Deception effectiveness is scale-invariant**: ADT and HIR remain stable across 100× network size increase. This is because the pheromone mechanism is inherently local — each honeypot only interacts with its neighborhood.
2. **Convergence time scales sub-linearly**: $t_{\text{conv}}$ grows roughly as $O(|V|^{0.6})$, better than the theoretical $O(|V|)$ worst case, thanks to the parallel nature of pheromone accumulation.
3. **Computation overhead is manageable**: Even at 5,000 nodes, total per-step computation is ~100ms, well within real-time constraints.
4. **LLM generation is the bottleneck**: LLM call time (~2.5s) is independent of network size but limits the mutation speed of individual honeypots. Local model deployment mitigates this.

---

## F. RQ5: Adaptive Attacker Resistance (Arms Race Dynamics)

### Table VIII: Performance Against L3 Adaptive Attacker Over Time

| Time Window | EmergentHoney ADT | EmergentHoney HIR | RL-Honeypot ADT | RL-Honeypot HIR |
|:-----------:|:---:|:---:|:---:|:---:|
| 0-6h (initial) | 28.4 ± 4.1 | 18.3 ± 3.5 | 22.1 ± 3.8 | 32.4 ± 4.6 |
| 6-12h (attacker learns) | 19.7 ± 3.8 | 31.2 ± 4.8 | 14.3 ± 3.2 | 48.7 ± 5.9 |
| 12-18h (swarm adapts) | 25.3 ± 4.3 | 22.5 ± 4.1 | 12.8 ± 3.0 | 53.2 ± 6.1 |
| 18-24h (stabilized) | 24.1 ± 4.2 | 24.8 ± 4.3 | 11.5 ± 2.9 | 56.8 ± 6.3 |
| 24-48h (long-term) | 22.7 ± 4.0 | 25.8 ± 4.2 | 9.7 ± 2.7 | 62.4 ± 6.8 |
| 48-72h (extended) | 21.9 ± 3.9 | 27.1 ± 4.4 | 8.2 ± 2.5 | 68.3 ± 7.1 |

**Arms Race Pattern (see Fig. 8):**
- **Phase 1 (0-6h)**: Both systems perform well against naive attacker. EmergentHoney already superior.
- **Phase 2 (6-12h)**: Attacker learns honeypot signatures. Both systems degrade, but RL-Honeypot degrades far more (-35% ADT vs -30% for EmergentHoney).
- **Phase 3 (12-18h)**: **Critical difference** — EmergentHoney's pheromone-driven mutation triggers topology restructuring, partially recovering performance (+28% ADT recovery). RL-Honeypot continues degrading because its fixed policy cannot adapt to the attacker's counter-strategy without retraining.
- **Phase 4 (18-72h)**: EmergentHoney stabilizes at a "contested equilibrium" (ADT ≈ 22min, HIR ≈ 26%), while RL-Honeypot collapses to near-static-baseline performance (ADT ≈ 8min, HIR ≈ 68%).

**Key Finding:** EmergentHoney maintains **2.67× higher ADT** and **60% lower HIR** than RL-Honeypot in the long-term adaptive attacker scenario. The pheromone evaporation mechanism naturally "forgets" compromised configurations, while the positive feedback loop reinforces newly effective configurations — creating a continuous arms race dynamic that favors the defender.

---

## G. Statistical Validation

All reported results use the following statistical methodology:
- **30 independent runs** per configuration with different random seeds
- **Wilcoxon signed-rank test** for pairwise comparisons ($\alpha = 0.01$)
- **Kruskal-Wallis test** for multi-group comparisons
- **Effect size**: Cliff's delta ($d$) reported for key comparisons

### Table IX: Statistical Significance of Key Comparisons

| Comparison | Metric | $p$-value | Cliff's $d$ | Effect Size |
|-----------|:---:|:---:|:---:|:---:|
| EmergentHoney vs RL-Honeypot | ADT | $< 0.001$ | 0.89 | Large |
| EmergentHoney vs RL-Honeypot | HIR | $< 0.001$ | -0.92 | Large |
| EmergentHoney vs Game-Theoretic | ADT | $< 0.001$ | 0.94 | Large |
| EmergentHoney vs LLM-Static | ADT | $< 0.001$ | 0.78 | Large |
| Full vs w/o Pheromone | ADT | $< 0.001$ | 0.96 | Large |
| Full vs w/o LLM | ADT | $< 0.001$ | 0.72 | Large |
| Full vs GA Replacement | ADT | $< 0.001$ | 0.68 | Large |

All key comparisons show $p < 0.001$ and large effect sizes ($|d| > 0.5$), confirming that the observed improvements are both statistically significant and practically meaningful.
