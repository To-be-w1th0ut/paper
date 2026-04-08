# VI. Experimental Evaluation

## Research Questions

- **RQ1 (Deception Effectiveness):** How much does EmergentHoney improve attacker dwell time, honeypot identification rate, and threat intelligence collection compared to baseline methods?
- **RQ2 (Self-Organization):** Does the honeypot swarm truly exhibit emergent collective deception capability (DEI > 1)? How long does emergence take?
- **RQ3 (Swarm Necessity):** How much does performance degrade when the pheromone mechanism is replaced by random/greedy/RL alternatives? (Irreplaceability validation)
- **RQ4 (Scalability):** How do EmergentHoney's performance and overhead scale from 50 → 500 → 5000 network nodes?
- **RQ5 (Adaptive Resistance):** Does EmergentHoney maintain deception effectiveness against adaptive attackers who can learn honeypot patterns?

## Experimental Setup

### Network Environment
- **Network Simulation**: Mininet + Open vSwitch for SDN network construction; Floodlight/ONOS as SDN controller
- **Honeypot Framework**: Dockerized T-Pot + OpenCanary instances supporting SSH/HTTP/SMB/MySQL/FTP honeypot types
- **Attack Simulation**: MITRE Caldera framework generating multi-stage APT attacks (Reconnaissance → Initial Access → Lateral Movement → Exfiltration), with 3 capability levels:
  - L1: Script-based scanning (Nmap)
  - L2: Automated exploitation (Metasploit)
  - L3: Adaptive attacker capable of learning honeypot signatures
- **LLM**: GPT-4o for honeypot content generation; locally deployed Llama-3-8B for real-time responses

### Baselines

| Baseline | Description | Selection Rationale |
|----------|-------------|-------------------|
| Static | Fixed-position, fixed-type honeypots | Traditional approach lower bound |
| Random-Dynamic | Random periodic honeypot configuration changes | Validates "change itself" vs "intelligent change" |
| RL-Honeypot | PPO-driven adaptive honeypot [ref: HoneyRL] | SOTA dynamic honeypot |
| Game-Theoretic | Stackelberg game honeypot deployment [Zhu & Başar] | Theory-driven approach |
| GAN-Honeypot | GAN-generated honeypot content [IJERT 2026] | Latest related work |
| Ablation-NoSwarm | EmergentHoney with pheromone replaced by greedy | Swarm irreplaceability validation |

### Evaluation Metrics
- **Primary**: Average Dwell Time (ADT), Honeypot Identification Rate (HIR), Threat Intelligence Collection count (TIC)
- **Secondary**: DEI emergence index, honeypot configuration change frequency, system resource overhead (CPU/memory/bandwidth), convergence time (time from deployment to stable deception topology)

### Ablation Study Design (RQ3 Core)

| Variant | Modification | Validation Target |
|---------|-------------|------------------|
| Full EmergentHoney | Complete system | Baseline |
| w/o Pheromone | Uniform random replaces pheromone guidance | Value of pheromone mechanism |
| w/o Evaporation | Set ρ=0, pheromone only increases | Value of forgetting mechanism |
| w/o Proliferation | Disable honeypot proliferation, allow only migration+mutation | Value of dynamic deployment |
| w/o LLM | Template-based content replaces LLM generation | LLM phenotype generation gain |
| w/o Reverse-ACO | Remove attacker modeling, use only defense-side pheromone | Value of predictive deployment |
