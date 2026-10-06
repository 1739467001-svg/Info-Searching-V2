@AGENTS.md

## Claude Code 专属

- **技能**（`.claude/skills/`）：
  - `/research <词>` —— 联网研究并新建条目（完整流程）
  - `/deepen <id>` —— 把已有条目升级一个成熟度，或补全【待核】、刷新时效内容
  - `/review` —— 知识库体检：校验、到期复核、研究前沿，给出下一步建议
- **MCP 服务**：仓库根目录的 `.mcp.json` 注册了 `info-kb`（`tools/mcp_server.py`），提供 `kb_find`、`kb_card`、`kb_outline`、`kb_section`、`kb_neighbors`、`kb_context`、`kb_path`、`kb_frontier` 等只读工具。
- 研究任务较大时，可以让子代理分头检索不同类别的来源，再由你统一做交叉核实——但最终写入条目的每个论断都必须由你确认过来源。
