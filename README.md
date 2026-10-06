# 📚 Info-Searching-V2 · 信息搜集与知识沉淀系统

> 给一个名词，联网多源检索、交叉核实，从八个维度把它讲清楚，并沉淀为**分层组织、按需加载**的知识条目。
> 覆盖全学科：科学、技术、人文、历史、地理、商业、思维方法……

搜索引擎给你的是**网页**：碎片化、有广告、来源单一、深度不够，看完也留不下什么。这个仓库要给你的是**知识**：

| | 搜索引擎 | 本系统 |
|---|---|---|
| 来源 | 单个网页 | ≥4 类来源、中英文交叉核实，每条来源标注分级与核实方式 |
| 深度 | 看运气 | 八维解析：是什么 · 为什么 · 怎么运作 · 从哪来 · 看例子 · 别搞混 · 怎么看 · 怎么用 |
| 理解 | 自己拼 | 一句话 → 30 秒卡片 → 全文；例子可复算；类比写明在哪里失效 |
| 沉淀 | 关掉就忘 | 条目互相关联，形成知识图谱；自测题可导出 Anki；"我的思考"留给你自己 |
| 给 AI 用 | — | 分层记忆 + 按需加载，避免长上下文"稀释注意力"导致的准确率下降 |

---

## 🚀 怎么用

### 1. 在 Claude Code 里（推荐）

```text
/research 熵            联网研究一个新词，写成条目（完整流程见 system/research-protocol.md）
/deepen entropy         把已有条目升级一个成熟度、补全待核实的论断
/review                 知识库体检：校验、到期复核、下一步研究建议
```

也可以直接问问题（"注意力为什么要除以 √d_k？"）——AI 会按 [AGENTS.md](AGENTS.md) 的读取协议，先查库、再只加载需要的那一小段来回答。

### 2. 在任何 AI 工具里

- 支持 MCP 的客户端（Claude Code、Claude Desktop、Cursor 等）：仓库根目录的 [`.mcp.json`](.mcp.json) 注册了只读的 `info-kb` 服务，提供 `kb_find` / `kb_card` / `kb_section` / `kb_neighbors` 等分层检索工具。
- 其他 AI 工具：让它先读 [AGENTS.md](AGENTS.md)（AI 协作协议，刻意保持简短）。

### 3. 命令行（只需 Python 3.9+，无任何依赖）

```bash
python3 tools/kb.py find 注意力                 # L0：查有没有
python3 tools/kb.py card attention-mechanism    # L1：读卡片
python3 tools/kb.py outline attention-mechanism # 看目录
python3 tools/kb.py section attention-mechanism 3.2   # L2：只读一个小节
python3 tools/kb.py neighbors entropy           # 关联条目
python3 tools/kb.py path attention-mechanism    # 学习路径
python3 tools/kb.py anki -o cards.tsv           # 自测题导出到 Anki
```

### 4. 网页阅读器

```bash
python3 tools/build_site.py && python3 -m http.server -d _site 8000
# 打开 http://localhost:8000 ：搜索、领域导航、公式与图表渲染、交互式关系图
```

发布到 GitHub Pages：Settings → Pages → Source 选 **GitHub Actions**，再新建仓库变量 `ENABLE_PAGES=true`（见 [`.github/workflows/pages.yml`](.github/workflows/pages.yml)）。

---

## 🧭 体系一览

**约法三章**（[来源规范](system/source-policy.md) · [写作规范](system/writing-standard.md)）

1. **准确第一**：只列实际读到的来源；标注分级（S1 一手/权威、S2 专业二手、S3 一般二手）和核实方式（全文/摘要/转引）；训练记忆不等于事实。
2. **兼听则明**：至少覆盖 4 类来源、中英文都查；【共识】【主流】【争议】【待核】分开标注。
3. **讲明白**：理解梯度、可复算的例子、写明失效边界的类比、考理解的自测题。

**分层记忆**（[架构说明](system/ARCHITECTURE.md)）——针对"上下文越长，模型越不准"的问题：

| 层 | 内容 | 什么时候读 |
|---|---|---|
| L0 登记簿 | 每个条目一句话（[INDEX.md](INDEX.md)） | 每次检索的第一步 |
| L1 卡片 | ≤25 行的核心内容 | 确认相关后 |
| L2 章节 | 八个维度中的某一章 | 需要细节时，只读那一章 |
| 图层 | 条目之间的关系 | 需要关联时，先只读邻居的一句话 |

**规范即代码**：`kb.py check` 校验字段、章节、来源分级、置信度底线、断链；CI 每次推送自动运行。

---

## 📊 知识库现状

<!-- AUTO:START -->
- 条目 **4** 个（🌳深度 4 · 🌿标准 0 · 🌱草稿 0）
- 关系 **26** 条 · 待建前沿 **25** 个 · 已核实来源 **59** 条 · 自测题 **25** 道

| 领域 | 条目数 |
|---|---|
| 🧮 [形式科学](kb/formal-sciences/README.md) | 0 |
| 🔭 [自然科学](kb/natural-sciences/README.md) | 1 |
| 🧬 [生命与医学](kb/life-medicine/README.md) | 0 |
| 🤖 [技术与 AI](kb/tech-ai/README.md) | 2 |
| 🏛️ [社会科学](kb/social-sciences/README.md) | 0 |
| 📜 [人文艺术](kb/humanities/README.md) | 0 |
| ⏳ [历史](kb/history/README.md) | 1 |
| 🌍 [地理与地区](kb/geography/README.md) | 0 |
| 💼 [商业与产业](kb/business/README.md) | 0 |
| 🧠 [思维与方法](kb/thinking/README.md) | 0 |

**最近更新**

- 2026-10-06 · [丝绸之路（Silk Road）](kb/history/silk-road.md) — 19 世纪学者对古代欧亚之间陆海贸易与文化交流网络的统称；不是一条路，也不只运丝绸。
- 2026-10-06 · [熵（Entropy）](kb/natural-sciences/entropy.md) — 衡量一个系统"有多少种微观方式能实现同一个宏观状态"的物理量；孤立系统的熵不会减少。
- 2026-10-06 · [上下文工程（Context Engineering）](kb/tech-ai/context-engineering.md) — 为大模型的每一步推理挑选、组织、压缩"恰好够用"的上下文信息的工程方法。
- 2026-10-06 · [注意力机制（Attention Mechanism）](kb/tech-ai/attention-mechanism.md) — 按"相关程度"给所有输入分配权重再加权求和的神经网络机制，是 Transformer 与大模型的核心。
<!-- AUTO:END -->

---

## 🗂️ 目录结构

```
Info-Searching-V2/
├── AGENTS.md / CLAUDE.md   AI 协作协议（入口，短）
├── INDEX.md                L0 全库登记簿（自动生成）
├── ROADMAP.md              项目完善计划
├── inbox.md                想研究的词（随手记）
├── kb/<领域>/<id>.md        知识条目（一个概念一个文件）
├── kb/<领域>/README.md      领域导读 + 局部关系图（自动生成部分）
├── graph/                  graph.json（机器读）· frontier.md（研究前沿）
├── system/                 架构 · 研究流程 · 来源规范 · 写作规范 · 分类体系
├── templates/              概念 · 专题 · 事件 · 人物 · 地点 · 作品
├── tools/                  kb.py 命令行 · kblib.py 核心库 · mcp_server.py · build_site.py · tests/
├── site/                   网页阅读器
└── .claude/skills/         /research · /deepen · /review
```

## 📖 文档地图

| 想了解 | 读这里 |
|---|---|
| 为什么这样设计、和 V1 相比改了什么 | [system/ARCHITECTURE.md](system/ARCHITECTURE.md) |
| 研究一个词的完整流程 | [system/research-protocol.md](system/research-protocol.md) |
| 来源怎么分级、置信度怎么定 | [system/source-policy.md](system/source-policy.md) |
| 条目怎么写才讲得明白 | [system/writing-standard.md](system/writing-standard.md) |
| 领域、类型、关系怎么选 | [system/taxonomy.md](system/taxonomy.md) |
| 接下来做什么 | [ROADMAP.md](ROADMAP.md) · [graph/frontier.md](graph/frontier.md) |
