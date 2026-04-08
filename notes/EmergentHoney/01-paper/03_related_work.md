# II. Related Work

We review four bodies of literature that intersect with EmergentHoney: (A) honeypot and cyber deception technologies, (B) moving target defense, (C) swarm intelligence in cybersecurity, and (D) LLM-powered security applications. For each, we identify the gap that EmergentHoney addresses.

## A. Honeypot and Cyber Deception Technologies

Honeypot research has evolved through three generations. **First-generation (static) honeypots** — including Honeyd [11], Kippo, and Cowrie — emulate fixed services at fixed network locations. While effective against opportunistic attackers, they are trivially fingerprinted by sophisticated adversaries through timing analysis, response consistency checks, and behavioral probing [5]. Large-scale deployments such as T-Pot [12] and the Community Honey Network aggregate multiple static honeypots but do not address the fundamental configuration rigidity.

**Second-generation (dynamic) honeypots** introduce adaptation mechanisms. Provos [13] proposed virtual honeypots that mirror real services in the network, and subsequent works explored configuration rotation strategies. Wagener et al. [14] presented SGNET, a self-adaptive honeypot that learns interaction scripts from attacker sessions. Dowling et al. [15] applied reinforcement learning to honeypot interaction, training a DQN agent to select responses that maximize attacker engagement time. Pauna et al. [16] used game theory to model the honeypot-attacker interaction as a Bayesian game and derived optimal deception strategies. More recently, Sun et al. [17] proposed HoneyGPT, using large language models to generate dynamic honeypot responses for SSH sessions.

**Third-generation (intelligent/autonomous) honeypots** represent the emerging frontier. Recent work has explored generative content and learning-based adaptive defense, but these systems still do not study topology-level self-organization of honeypot swarms as the primary adaptation mechanism.

**Gap:** Existing approaches — including RL-based and game-theoretic methods — still operate largely within a **centralized control paradigm**: a controller, optimizer, or policy decides how honeypots change. The literature still lacks a clear treatment of *decentralized, emergent self-organization* of honeypot topologies driven by local pheromone interactions.

## B. Moving Target Defense (MTD)

Moving target defense [20] shifts the defender's strategy from static protection to continuous attack surface mutation. Key MTD techniques include IP address randomization (e.g., OpenFlow Random Host Mutation [21]), port hopping [22], OS diversity [23], and software stack rotation [24]. Zhuang et al. [25] formulated MTD as a Markov Decision Process and used RL to learn optimal mutation timing. Sengupta et al. [26] modeled MTD as a Bayesian Stackelberg game, deriving equilibrium mutation strategies.

A fundamental challenge in MTD is the **availability-security tradeoff**: aggressive mutation disrupts legitimate services, while conservative mutation leaves exploitable time windows [27]. Existing solutions address this through centralized optimization (e.g., convex optimization of mutation intervals [28]) or game-theoretic analysis (e.g., computing Stackelberg equilibria [26]).

**Gap:** MTD research focuses on *what to change* (IP, port, OS) and *when to change* (timing optimization), but treats each node's mutation as an independent decision. The **collective, coordinated mutation of network topology** — where the mutation rhythm of each node is influenced by its neighbors' states and attacker behavior — has not been explored. EmergentHoney fills this gap: the pheromone mechanism creates emergent coordination among honeypot instances, producing topology-level deception patterns that no individual node could achieve alone.

## C. Swarm Intelligence in Cybersecurity

Swarm intelligence algorithms have been applied to various cybersecurity problems, primarily as optimization tools. Chaalal and Baba-Ali [29] used ACO for feature selection in intrusion detection systems. Alazzam et al. [30] applied PSO to optimize SVM parameters for network anomaly detection. Elminaam et al. [31] employed ABC for cryptographic key generation. Khari and Kumar [32] used firefly algorithm for software test case prioritization in security testing. A comprehensive survey by Sayed et al. [33] covers swarm intelligence applications in cybersecurity, categorizing them into intrusion detection, malware analysis, cryptography, and access control.

In the specific domain of deception, the intersection with swarm intelligence is remarkably sparse. Zhang et al. [34] used PSO to optimize honeypot placement in a static network — treating placement as a one-time combinatorial optimization problem, not a continuous self-organizing process. To the best of our knowledge, no prior work has used swarm intelligence mechanisms as the **operational logic** (rather than an optimization tool) of a deception system.

**Gap:** Existing works use swarm intelligence to optimize *parameters* of security systems (feature weights, model hyperparameters, placement locations). EmergentHoney differs in that the pheromone mechanism acts as the system's **online coordination protocol**, not merely as a design-time optimizer.

## D. LLM-Powered Security Applications

Large language models have rapidly penetrated cybersecurity applications. In offensive security, PentestGPT [35] demonstrated LLM-guided penetration testing, and Fang et al. [36] showed that LLM agents can autonomously exploit one-day vulnerabilities. In defensive security, LLMs have been applied to threat intelligence extraction [37], security log analysis [38], vulnerability detection [39], and incident response automation [40].

For cyber deception specifically, McKee et al. [41] explored using ChatGPT to generate phishing emails as a red-team exercise, inadvertently demonstrating LLMs' capability to produce convincing fake content. HoneyGPT [17] applied LLMs to SSH honeypot response generation, achieving higher attacker engagement compared to scripted responses. However, these works use LLMs as standalone response generators without any systematic framework for *when, where, and what type* of deception content should be generated.

**Gap:** LLM-powered deception lacks a **strategic orchestration layer** that decides deployment and adaptation. EmergentHoney provides this missing layer through the pheromone mechanism: swarm intelligence determines the *strategic* decisions (where to deploy, when to mutate, which type to use), while LLMs handle the *tactical* decisions (what specific content to present). This separation of strategic and tactical intelligence is novel.

## E. Summary and Positioning

Table I summarizes the positioning of EmergentHoney relative to prior work across four dimensions.

| Dimension | Static Honeypots | Dynamic/RL Honeypots | Game-Theoretic MTD | Swarm-Optimized Security | **EmergentHoney** |
|-----------|:---:|:---:|:---:|:---:|:---:|
| Decentralized | ✗ | ✗ | ✗ | ✗ | **✓** |
| Self-organizing | ✗ | Partial (RL adapts responses) | ✗ (requires equilibrium computation) | ✗ (one-time optimization) | **✓** |
| Topology-level adaptation | ✗ | ✗ (only content-level) | ✓ (but centralized) | ✓ (but one-time) | **✓** |
| Emergent collective behavior | ✗ | ✗ | ✗ | ✗ | **✓** |
| LLM-powered content | ✗ | Partial [17] | ✗ | ✗ | **✓** |
| Predictive deployment | ✗ | ✗ | Partial (game anticipation) | ✗ | **✓** |
| Controller-free adaptation | ✗ | ✗ | ✗ | ✗ | **✓** |

As shown, EmergentHoney is positioned around decentralized self-organization and topology-level adaptation, with LLM-generated content and predictive deployment acting as supporting capabilities around the core pheromone mechanism.

---

### Bibliography Note

The canonical bibliography for the paper is now maintained in
`02-tex/references.bib`. Older draft-only reference lists with unresolved
verification tags have been removed to avoid divergence from the main
manuscript.
