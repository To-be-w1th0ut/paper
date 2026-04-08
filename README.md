# 📝 AI+Security Paper Writing Repository

用于撰写 AI 与安全交叉领域学术论文的写作仓库，同时支持 LaTeX 和 Markdown 格式。

## 📁 目录结构

```
paper/
├── latex/                  # LaTeX 论文模板
│   ├── main.tex           # 主文档
│   └── references.bib     # 参考文献
├── markdown/              # Markdown 论文模板
│   └── paper.md           # 主文档
├── figures/               # 图片资源
│   ├── architecture/      # 架构图
│   ├── results/           # 实验结果图
│   └── diagrams/          # 其他图表
├── data/                  # 实验数据
├── scripts/               # 辅助脚本
├── notes/                 # 研究笔记
└── README.md              # 本文件
```

## 🚀 快速开始

### 使用 LaTeX

1. 编辑 `latex/main.tex` 文件
2. 在 `latex/references.bib` 中添加参考文献
3. 编译 PDF：
   ```bash
   cd latex
   pdflatex main.tex
   bibtex main.aux
   pdflatex main.tex
   pdflatex main.tex
   ```
4. 或者使用 `latexmk`（推荐）：
   ```bash
   latexmk -pdf main.tex
   ```

### 使用 Markdown

1. 编辑 `markdown/paper.md` 文件
2. 使用 Markdown 编辑器预览（如 Typora、Obsidian、VS Code）
3. 导出为 PDF（可选）：
   ```bash
   # 使用 pandoc
   pandoc markdown/paper.md -o paper.pdf --pdf-engine=xelatex
   ```

## 📝 写作建议

### 论文结构

1. **Title（标题）** - 简洁明确，突出创新点
2. **Abstract（摘要）** - 150-250 字，概括全文
3. **Introduction（引言）** - 背景、动机、贡献
4. **Related Work（相关工作）** - 文献综述
5. **Methodology（方法）** - 问题定义、方法细节
6. **Experiments（实验）** - 设置、结果、分析
7. **Discussion（讨论）** - 优势、局限、未来工作
8. **Conclusion（结论）** - 总结全文

### AI+Security 研究方向参考

- 恶意软件检测（Malware Detection）
- 入侵检测系统（Intrusion Detection Systems）
- 网络流量分析（Network Traffic Analysis）
- 对抗性机器学习（Adversarial Machine Learning）
- 隐私保护（Privacy Preservation）
- 威胁情报（Threat Intelligence）
- 漏洞挖掘（Vulnerability Discovery）

## 🛠️ 工具推荐

### LaTeX 工具
- **Overleaf** - 在线 LaTeX 编辑器
- **TeXShop / TeXworks** - 本地 LaTeX 编辑器
- **LaTeX Workshop** - VS Code 插件

### Markdown 工具
- **Typora** - 优雅的 Markdown 编辑器
- **Obsidian** - 知识管理与写作
- **VS Code** + Markdown 插件

### 绘图工具
- **TikZ** - LaTeX 原生绘图
- **Draw.io** - 免费流程图工具
- **matplotlib / seaborn** - Python 绘图

### 参考文献管理
- **Zotero** - 免费开源
- **Mendeley** - Elsevier 出品
- **JabRef** - BibTeX 管理

## 📊 实验数据管理

```
data/
├── raw/                 # 原始数据
├── processed/           # 处理后数据
├── results/             # 实验结果
└── README.md            # 数据说明
```

## 🔧 辅助脚本

在 `scripts/` 目录下可以存放：

- 数据处理脚本（Python/R）
- 实验运行脚本
- 结果可视化脚本
- 格式转换脚本

## 📖 版本控制最佳实践

```bash
# 提交实验结果
git add figures/results/experiment_01.png
git commit -m "Add results for experiment 01: accuracy 94.2%"

# 提交论文修改
git add latex/main.tex
git commit -m "Update methodology section: add algorithm pseudocode"

# 创建版本标签
git tag -a v0.1-draft -m "First complete draft"
git push origin v0.1-draft
```

## 📜 License

MIT License

---

**Happy Writing!** 🎓
