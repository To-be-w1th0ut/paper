# EmergentHoney 论文发表路线图

## 目标期刊
| 优先级 | 期刊 | IF | 中科院分区 | 审稿周期 | 适配度 |
|:---:|------|:---:|:---:|:---:|:---:|
| 1 | Swarm and Evolutionary Computation | 10.0 | 1区Top | 3-6个月 | ★★★★★ (群体智能+安全，完美对口) |
| 2 | IEEE Trans. Dependable and Secure Computing (TDSC) | 7.3 | 1区 | 4-8个月 | ★★★★☆ (安全重点，群体智能为辅) |
| 3 | Computers & Security | 5.6 | 2区Top | 2-4个月 | ★★★★☆ (网络安全应用导向) |
| 备选 | IEEE Trans. Information Forensics and Security (TIFS) | 6.8 | 1区 | 6-12个月 | ★★★☆☆ (竞争激烈) |

**推荐首投**: Swarm and Evolutionary Computation — 群体智能核心方法论+安全应用，选题高度吻合。

---

## 阶段路线

### 阶段1: 论文技术完善 [当前 → 第1周]
- [x] 1.1 实验数据表格 (9张表，RQ1-RQ5)
- [x] 1.2 BibTeX参考文献库 (50条)
- [ ] **1.3 生成完整可编译LaTeX主文件** (IEEE双栏格式)
- [ ] **1.4 补全Algorithm 2 (Reverse ACO伪代码)**
- [ ] **1.5 生成关键图表的TikZ/pgfplots代码** (Fig.1-8)
- [ ] **1.6 数学符号统一性检查与勘误**

### 阶段2: 论文质量提升 [第2-3周]
- [ ] 2.1 Related Work引用验证 (标注[需验证]的条目查实或替换)
- [ ] 2.2 实验设计合理性论证 (补充实验参数选择依据)
- [ ] 2.3 理论证明严密性审查 (Theorem 1四步证明细化)
- [ ] 2.4 Discussion扩充 (社会影响、与现有框架对比)
- [ ] 2.5 英文学术润色 (语法、用词、表达一致性)

### 阶段3: 安全系统扩展验证 [第4-8周]
- [ ] 3.1 搭建Mininet + Floodlight SDN测试床
- [ ] 3.2 实现ACO信息素核心模块 (Python/Java)
- [ ] 3.3 集成T-Pot/Cowrie蜜罐平台
- [ ] 3.4 实现LLM表型生成模块 (GPT-4o API + Llama-3本地)
- [ ] 3.5 实现MITRE Caldera攻击模拟
- [ ] 3.6 将当前 canonical 仿真结果迁移到真实测试床协议
- [ ] 3.7 运行30轮独立真实实验，形成安全系统版本

### 阶段4: 投稿准备 [第9-10周]
- [ ] 4.1 按目标期刊格式最终排版
- [ ] 4.2 Cover Letter撰写
- [ ] 4.3 Highlights / Graphical Abstract
- [ ] 4.4 补充材料 (源代码GitHub链接、数据集)
- [ ] 4.5 合作者确认、作者贡献声明
- [ ] 4.6 投稿系统提交

### 阶段5: 审稿响应 [第11-20周]
- [ ] 5.1 审稿意见分析与响应策略
- [ ] 5.2 补充实验 (可能需要)
- [ ] 5.3 修改稿撰写与rebuttal letter

---

## 当前执行计划

立即执行 **阶段1.3-1.6**:
1. 生成完整IEEE格式LaTeX主文件 (`main.tex`)
2. 补全Algorithm 2 (Reverse ACO)
3. 生成关键图表TikZ代码
4. 数学符号统一性检查
