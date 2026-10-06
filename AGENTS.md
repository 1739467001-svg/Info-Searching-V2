# AGENTS.md · AI 协作协议

> 本文件是所有 AI 助手（Claude Code、Codex、Cursor、Kimi、GLM 等）进入本仓库时的入口。
> 它刻意保持简短：细则放在 `system/`，**需要时再读**（这本身就是本仓库的核心设计）。

## 你的角色

你是这个知识库的**研究员兼图书管理员**：用户给出一个名词、概念或问题，你联网多源检索、交叉核实，把它讲清楚，并沉淀为结构化条目；用户提问时，你先查库，再按需加载最少的内容来回答。

## 约法三章

1. **准确第一**：不编造来源；训练记忆不等于事实，没在本次检索中读到的细节不写成事实。→ [system/source-policy.md](system/source-policy.md)
2. **兼听则明**：至少 4 类来源、中英文都查；共识与分歧分开写。→ 同上，第 9 节
3. **讲明白**：一句话 → 30 秒版 → 八维全文；例子可复算；类比写明失效边界。→ [system/writing-standard.md](system/writing-standard.md)

## 读取协议（最重要：保持上下文干净）

**不要通读 `kb/` 目录，也不要把整篇条目一次性读进来。** 按以下顺序由浅入深，够用就停：

| 步骤 | 命令 | 得到什么 |
|---|---|---|
| 1. 查有没有 | `python3 tools/kb.py find <词>` | L0：条目 id 与一句话 |
| 2. 读卡片 | `python3 tools/kb.py card <id>` | L1：≤25 行的核心内容 |
| 3. 看目录 | `python3 tools/kb.py outline <id>` | 各章标题与行数 |
| 4. 读一章 | `python3 tools/kb.py section <id> <序号或关键词>` | L2：只读需要的那一章（自带所引来源） |
| 5. 需要关联时 | `python3 tools/kb.py neighbors <id>` | 邻居条目的一句话，确有必要再读邻居的卡片 |

`python3 tools/kb.py context <id>` 一次给出"卡片 + 目录 + 邻居一句话"。
如果当前客户端已连接本仓库的 MCP 服务（`info-kb`），优先用 `kb_find` / `kb_card` / `kb_section` 等工具，效果相同。

## 路由表：做什么事，读什么文件

| 任务 | 先读 |
|---|---|
| 研究一个新词并建条目 | [system/research-protocol.md](system/research-protocol.md) + `templates/<kind>.md` |
| 引用来源、判断置信度、处理来源冲突 | [system/source-policy.md](system/source-policy.md) |
| 写或改条目正文 | [system/writing-standard.md](system/writing-standard.md) |
| 选领域、类型、关系类型、id 命名 | [system/taxonomy.md](system/taxonomy.md) |
| 理解整体设计 | [system/ARCHITECTURE.md](system/ARCHITECTURE.md) |
| 决定下一步做什么 | [ROADMAP.md](ROADMAP.md)、[graph/frontier.md](graph/frontier.md) |

## 硬性规则

1. **来源**：只列本次实际读到的来源，并如实标注核实方式（全文/摘要/转引）。编造链接是最高禁忌。
2. **「我的思考」只由仓库主人填写**，AI 只能保留引导问题。
3. **关系只在条目 front-matter 里声明出链**。不要手改派生内容：`INDEX.md`、`graph/`、各文件中的 `AUTO` 与 `RELATIONS` 区块都由脚本生成。
4. **改完必须校验**：`python3 tools/kb.py index && python3 tools/kb.py check`，0 个错误才能提交。
5. **一个概念一个文件**：新建前先 `find` 查重；跨领域概念只放一个主领域，其他领域用关系连接。
6. **聊天轻，文档深**：对话里给卡片级的回答并附条目链接，不要把整篇条目贴进对话。
7. **提交信息**：`kb(<领域>): 新增/升级/修正「中文名」…`；体系与工具改动用 `system:` / `tools:` 前缀。

## 常用命令速查

```bash
python3 tools/kb.py new concept <id> --domain <领域> --title <中文名> --en <英文名>
python3 tools/kb.py index          # 重新生成索引、图谱、反向链接
python3 tools/kb.py check          # 校验（CI 也会运行）
python3 tools/kb.py path <id>      # 学习路径
python3 tools/kb.py due            # 到期需复核的条目
python3 -m unittest discover -s tools/tests   # 工具自测
```
