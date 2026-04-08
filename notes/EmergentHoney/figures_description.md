# Key Figures Description

| # | Title | Content | Position | Demonstrates |
|---|-------|---------|----------|-------------|
| Fig.1 | System Architecture of EmergentHoney | Full system panorama: SDN network base layer → Pheromone layer (heatmap visualization) → Honeypot self-organization layer (proliferation/migration/mutation arrows) → LLM phenotype generation layer → Attacker reverse modeling layer | Section IV opening | System overview at a glance |
| Fig.2 | Biological-Cyber Isomorphism | Side-by-side diagram: Left - ant colony foraging (ants, pheromone trails, food sources) ↔ Right - honeypot network (honeypots, attack pheromone, attackers), with dashed lines connecting corresponding concepts | Section I (Introduction) | Visual demonstration of core isomorphism |
| Fig.3 | Pheromone-Driven Topology Evolution | Time-series snapshots (t=0, t=10, t=50, t=100): showing honeypot distribution evolving from random initialization → gradual aggregation toward attack hotspots → stable deception topology emergence | Section IV-A | Visualization of self-organization emergence |
| Fig.4 | Deception Effectiveness Comparison | Bar/box plots: ADT, HIR, TIC across EmergentHoney vs 5 baselines | Section VI-B (RQ1) | Method effectiveness proof |
| Fig.5 | DEI Emergence Curve | Line plot: DEI value over time, with DEI=1 horizontal reference line, showing emergence inflection point from <1 to >1 | Section VI-C (RQ2) | Proof of emergence existence |
| Fig.6 | Ablation Study Results | Radar chart or grouped bar chart: Full system vs 6 ablation variants across all metrics | Section VI-D (RQ3) | Necessity of each component, especially pheromone irreplaceability |
| Fig.7 | Scalability Analysis | Dual-Y-axis line plot: X-axis = network scale (50-5000), left Y-axis = ADT/HIR performance, right Y-axis = system overhead (CPU/memory) | Section VI-E (RQ4) | Scalability proof |
| Fig.8 | Adaptive Attacker Arms Race | Time-series line plot: L3 adaptive attacker's honeypot identification rate over time — attacker briefly learns to identify → EmergentHoney pheromone-driven mutation → identification rate drops again — showing "arms race" dynamics | Section VI-F (RQ5) | Most critical figure — proves self-evolution capability |
