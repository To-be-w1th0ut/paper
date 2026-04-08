# VIII. Conclusion

EmergentHoney introduces a decentralized cyber deception framework in which pheromone dynamics govern where honeypots appear, when they move, and how the swarm reconfigures under pressure. The central contribution of the paper is therefore not "ACO used in security" but a **pheromone-driven self-organizing deception topology** in which swarm intelligence serves as the operational fabric of the defense mechanism.

Within the released SDN-informed emulation study, EmergentHoney achieves **3.24 ± 0.16 hours** average attacker dwell time, nearly doubling the best adaptive RL baseline, while reducing honeypot identification rate by **71%**. The ablation study further shows that removing the pheromone mechanism cuts dwell time by **50.3%** and drops the Deception Emergence Index below **1.0**, indicating that the swarm advantage disappears once decentralized self-organization is removed.

The LLM phenotype layer and reverse-trajectory predictor remain useful supporting modules, but the empirical and theoretical center of gravity is the pheromone mechanism itself. Future work should extend this emulation artifact into a fully instrumented real SDN deployment and re-run the same evaluation pipeline under stronger operational constraints.
