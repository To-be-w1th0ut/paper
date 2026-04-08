# VII. Discussion

## A. Limitations

1. **SDN Dependency.** EmergentHoney requires SDN/cloud-native infrastructure for programmatic honeypot deployment and migration. Traditional static networks cannot support the dynamic topology changes that the pheromone mechanism prescribes. While SDN adoption is growing rapidly in enterprise and cloud environments, this limits applicability in legacy network environments.

2. **LLM Latency and Cost.** Generating honeypot phenotypes via LLM introduces latency (typically 1-5 seconds for GPT-4o) and API costs. For high-interaction honeypots requiring real-time responses, this can be mitigated by using locally deployed smaller models (e.g., Llama-3-8B) or pre-generating response libraries during low-activity periods.

3. **Pheromone Cold Start.** At initial deployment (before any attacker interaction), the pheromone landscape is uniform, and the system operates in a near-random configuration until sufficient interaction data accumulates. This cold-start period (estimated at 2-5 hours based on typical attack rates) represents a vulnerability window. Mitigation: initialize pheromone based on network topology analysis (high-centrality positions receive higher initial pheromone).

4. **Attacker Awareness.** If an attacker becomes aware that the target uses pheromone-based deception, they might develop counter-strategies (e.g., deliberately generating fake interactions to manipulate pheromone). Proposition 3 shows this is costly but not impossible. Future work should explore adversarial-robust pheromone models.

## B. Ethical Considerations

EmergentHoney is a purely defensive technology. The honeypot instances do not interact with external systems or attack other hosts. All deception content is generated within the defended network's perimeter. The threat intelligence collected follows standard honeypot data collection practices under established legal frameworks [44].

## C. Future Directions

1. **Cross-Network Federated Pheromone Sharing.** Multiple organizations could share anonymized pheromone statistics (not raw interaction data), enabling cross-organizational collective deception learning — analogous to the biological concept of "inter-colony information transfer" observed in some ant species.

2. **Integration with EcoImmune.** Combining EmergentHoney's proactive deception with the immune-based self-healing framework (EcoImmune) could create a comprehensive "deception + detection + healing" defense ecosystem. The pheromone mechanism handles external attacker engagement while the immune mechanism handles internal threat mitigation.

3. **Formal Game-Theoretic Analysis.** While the current work focuses on the swarm intelligence paradigm, future work could analyze the defender-attacker interaction through a formal game-theoretic lens, studying whether the pheromone-driven strategy constitutes an approximate equilibrium of the deception game.
