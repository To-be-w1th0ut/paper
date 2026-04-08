# VI. Experimental Evaluation

## Research Questions

- **RQ1 (Effectiveness):** Does pheromone-driven self-organization improve attacker dwell time, honeypot identification rate, and threat-intelligence capture over comparison methods?
- **RQ2 (Emergence):** Does the swarm exhibit positive collective emergence (DEI > 1), and how does that behavior evolve over time?
- **RQ3 (Mechanism Necessity):** How much performance is lost when the pheromone mechanism or supporting modules are removed?
- **RQ4 (Scale):** Do the gains remain stable from 50 to 200 to 500 nodes?
- **RQ5 (Adaptive Attackers):** Does the system retain its advantage against attackers that learn and avoid observed traps?

## Experimental Setup

### Study Type
- **Positioning:** This manuscript reports an **SDN-informed emulation study**, not a completed production deployment or a full hardware-backed deployment evaluation.
- **Artifact:** The released repository contains a simulation/emulation prototype plus a canonical result bundle used to regenerate manuscript tables and figures.

### Environment
- **Topology model:** Enterprise-style SDN topologies with 50, 200, and 500 nodes
- **Honeypot abstraction:** Container-level service models for SSH, HTTP, SMB, MySQL, FTP, and SMTP deception roles
- **Attack process:** Multi-stage attacker simulation with reconnaissance, initial access, lateral movement, and exfiltration phases
- **Runtime horizon:** 72 simulated hours per run
- **Repetition:** 30 random-seed runs for the canonical comparison study

### Comparison Methods

| Method | Role in Evaluation |
|--------|--------------------|
| Static | Fixed deployment lower bound |
| Random-Dynamic | Validates "change" without strategy |
| RL-Honeypot | Best adaptive baseline in the canonical result bundle |
| Game-Theoretic | Structured decision-theoretic baseline |
| GAN-Honeypot | Content-diversity baseline from the result bundle |
| LLM-Static | Isolates the benefit of the phenotype layer without swarm adaptation |

### Primary Metrics
- **Average Dwell Time (ADT):** measured in **hours**
- **Honeypot Identification Rate (HIR):** lower is better
- **Threat Intelligence Collection (TIC):** unique technique instances captured
- **Deception Emergence Index (DEI):** collective-vs-isolated deception ratio

## Canonical Findings

- **RQ1:** EmergentHoney achieves **3.24 ± 0.16 h** ADT versus **1.66 ± 0.10 h** for the RL baseline, with **8.0 ± 2.1%** HIR versus **28.1 ± 4.7%**.
- **RQ2:** DEI reaches **2.24 ± 0.24** at 48 hours and stabilizes near **2.00**, indicating sustained positive emergence.
- **RQ3:** Removing the pheromone mechanism reduces ADT from **3.32 h** to **1.65 h** and pushes DEI below **1.0**.
- **RQ4:** ADT remains within **3.21-3.46 h** across 50, 200, and 500 nodes.
- **RQ5:** Against adaptive attackers, EmergentHoney maintains roughly **2x** the dwell time of the RL baseline across all time windows.

## Interpretation

The evidence in this version supports one primary claim: **the pheromone-driven self-organizing topology is the dominant source of performance**. The LLM phenotype layer and reverse-trajectory predictor help, but they function as supporting modules around the swarm mechanism rather than as separate core contributions.
