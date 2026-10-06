# 🤖 技术与 AI（`tech-ai`）

**范围**：计算机、人工智能、互联网、电子与工程技术

> 本页上半部分可手写领域导读；`AUTO` 区块由 `python3 tools/kb.py index` 自动维护。

## 条目

<!-- AUTO:START -->
### 概念

- [注意力机制（Attention Mechanism）](attention-mechanism.md) — 按"相关程度"给所有输入分配权重再加权求和的神经网络机制，是 Transformer 与大模型的核心。 `🌳深度`
- [上下文工程（Context Engineering）](context-engineering.md) — 为大模型的每一步推理挑选、组织、压缩"恰好够用"的上下文信息的工程方法。 `🌳深度`

### 关系图（本领域 + 一跳邻居）

```mermaid
graph LR
  n0["注意力机制"]:::here
  n1["上下文工程"]:::here
  n2["softmax<br/><small>待建</small>"]:::todo
  n3["word-embedding<br/><small>待建</small>"]:::todo
  n4["seq2seq<br/><small>待建</small>"]:::todo
  n5["transformer<br/><small>待建</small>"]:::todo
  n6["kv-cache<br/><small>待建</small>"]:::todo
  n7["selective-attention<br/><small>待建</small>"]:::todo
  n8["state-space-model<br/><small>待建</small>"]:::todo
  n9["large-language-model<br/><small>待建</small>"]:::todo
  n10["prompt-engineering<br/><small>待建</small>"]:::todo
  n11["retrieval-augmented-generation<br/><small>待建</small>"]:::todo
  n12["ai-agent<br/><small>待建</small>"]:::todo
  n13["working-memory<br/><small>待建</small>"]:::todo
  n0 -.->|前置知识| n2
  n0 -.->|前置知识| n3
  n0 -.->|前置知识| n4
  n0 -.->|催生/演化出| n5
  n0 -.->|催生/演化出| n6
  n0 -.->|区别于| n7
  n0 -.->|区别于| n8
  n1 -->|前置知识| n0
  n1 -.->|前置知识| n9
  n1 -.->|区别于| n10
  n1 -.->|相关| n11
  n1 -.->|应用于| n12
  n1 -.->|相关| n13
  classDef here fill:#e8f1ff,stroke:#2f6feb,stroke-width:2px;
  classDef other fill:#eef9f0,stroke:#2da44e;
  classDef todo fill:#fff8e5,stroke:#bf8700,stroke-dasharray: 4 3;
```
<!-- AUTO:END -->
