---
name: deepen
description: 升级知识库中已有的条目：草稿→标准→深度，补全【待核】论断、补充来源与视角、刷新过期的时效内容。当用户说"把某条写深一点""补充一下某条""某条过时了"或运行 /deepen <id> 时使用。
---

# /deepen —— 升级一个已有条目

输入：`$ARGUMENTS`（条目 id；不确定时先 `python3 tools/kb.py find <词>`）

1. **诊断**（只读必要部分）：
   - `python3 tools/kb.py context <id>` —— 卡片、目录、邻居
   - `python3 tools/kb.py check` 中与该条目有关的错误/提醒
   - 对照 `system/taxonomy.md` 第 5 节，确定目标成熟度还差什么（来源数、S1 数、自测题数、缺失章节、【待核】）
2. **定计划**：列出本次要补的具体缺口（不超过 5 项），优先级：事实错误 > 【待核】 > 缺失章节 > 来源不足 > 表达优化。
3. **逐章修改**：用 `kb.py section <id> <章>` 只读要改的章节；按 `system/research-protocol.md` 第 2–3 步检索与核实；修改。
4. **记录**：在「变更记录」追加一行；修正事实时写明"原说法 → 新说法 → 依据"；更新 `updated`，必要时更新 `status`、`confidence`、`review_after`。
5. **校验**：`python3 tools/kb.py index && python3 tools/kb.py check`，0 错误。
6. **回复用户**：改了什么、为什么、还剩什么缺口。
