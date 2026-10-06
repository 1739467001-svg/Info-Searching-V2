# 🧭 研究前沿（Frontier）

> ⚙️ 本文件由 `python3 tools/kb.py index` 自动生成，请勿手改。

知识库的生长方式：每写一个条目，它在 `relations` 里引用的、但还不存在的概念就会出现在这里。
被引用次数越多，说明它越是现有知识的"枢纽"，越值得优先研究。

## 1. 待建条目（按被引用次数排序）

| 待建 id | 被引用 | 引用者（关系） |
|---|---|---|
| `ai-agent` | 1 | 上下文工程（应用于） |
| `arrow-of-time` | 1 | 熵（相关） |
| `belt-and-road-initiative` | 1 | 丝绸之路（区别于） |
| `buddhism-in-china` | 1 | 丝绸之路（催生/演化出） |
| `central-asia` | 1 | 丝绸之路（位于） |
| `hexi-corridor` | 1 | 丝绸之路（相关） |
| `information-entropy` | 1 | 熵（区别于） |
| `kv-cache` | 1 | 注意力机制（催生/演化出） |
| `landauer-principle` | 1 | 熵（相关） |
| `large-language-model` | 1 | 上下文工程（前置知识） |
| `maritime-silk-road` | 1 | 丝绸之路（区别于） |
| `probability` | 1 | 熵（前置知识） |
| `prompt-engineering` | 1 | 上下文工程（区别于） |
| `retrieval-augmented-generation` | 1 | 上下文工程（相关） |
| `second-law-of-thermodynamics` | 1 | 熵（催生/演化出） |
| `selective-attention` | 1 | 注意力机制（区别于） |
| `seq2seq` | 1 | 注意力机制（前置知识） |
| `softmax` | 1 | 注意力机制（前置知识） |
| `sogdians` | 1 | 丝绸之路（相关） |
| `state-space-model` | 1 | 注意力机制（区别于） |
| `thermodynamics` | 1 | 熵（属于） |
| `transformer` | 1 | 注意力机制（催生/演化出） |
| `word-embedding` | 1 | 注意力机制（前置知识） |
| `working-memory` | 1 | 上下文工程（相关） |
| `zhang-qian` | 1 | 丝绸之路（前置知识） |

## 2. 深度回填队列（草稿 → 标准 → 深度）

（全部条目均已达到深度级）

## 3. 复核计划（按 review_after 排序）

| 条目 | 复核日期 | 原因 |
|---|---|---|
| [上下文工程](../kb/tech-ai/context-engineering.md) | 2027-04-06 | 2025 年才流行的新术语，方法与工具变化快 |
| [注意力机制](../kb/tech-ai/attention-mechanism.md) | 2027-10-06 | 高效注意力与替代架构（线性注意力、状态空间模型）进展快 |

> 到期检查：`python3 tools/kb.py due`
