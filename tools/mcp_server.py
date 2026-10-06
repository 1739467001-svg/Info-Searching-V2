#!/usr/bin/env python3
"""info-kb MCP 服务：把知识库的分层检索开放给任何支持 MCP 的 AI 客户端。

传输方式：stdio（每行一条 JSON-RPC 2.0 消息），仅依赖 Python 标准库。
所有工具都是只读的；写入条目仍然通过编辑 Markdown 文件 + `kb.py index` 完成。

在 Claude Code 中：仓库根目录的 .mcp.json 已注册本服务（名称 info-kb）。
在其他客户端中：命令 `python3 /绝对路径/tools/mcp_server.py`。
"""
from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kblib  # noqa: E402
from kblib import KB, KBError  # noqa: E402

SERVER_NAME = "info-kb"
SERVER_VERSION = "1.0.0"
SUPPORTED_VERSIONS = ["2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05"]

INSTRUCTIONS = """这是一个分层组织的个人知识库（Info-Searching-V2）。请按"由浅入深、够用就停"的顺序检索，保持上下文干净：
1. kb_find：先确认条目是否存在（只返回一句话）
2. kb_card：读卡片（≤25 行的核心内容）
3. kb_outline → kb_section：只读回答所需的那一章/小节（自动附带该段引用的来源）
4. kb_neighbors：仅在需要关联、对比、前置知识时使用，且先只看邻居的一句话
不要一次性读取整篇条目；引用内容时保留来源脚注。"""


def _id_arg(desc: str = "条目 id，如 attention-mechanism；不知道 id 时先用 kb_find") -> dict:
    return {"type": "string", "description": desc}


TOOLS = [
    {
        "name": "kb_find",
        "description": "L0：按名称、英文名、别名、标签、一句话摘要查找条目，返回 id 与一句话。检索的第一步。",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "要查找的词，中英文均可"},
                "limit": {"type": "integer", "description": "最多返回条数，默认 8", "minimum": 1, "maximum": 50},
            },
            "required": ["query"],
        },
    },
    {
        "name": "kb_card",
        "description": "L1：读取一个或多个条目的卡片（一句话 + 30 秒版 + 要点 + 最常见误解）及元数据。",
        "inputSchema": {
            "type": "object",
            "properties": {"ids": {"type": "array", "items": {"type": "string"}, "description": "条目 id 列表"}},
            "required": ["ids"],
        },
    },
    {
        "name": "kb_outline",
        "description": "列出条目的章节目录（含小节与行数），用于决定接下来只读哪一章。",
        "inputSchema": {"type": "object", "properties": {"id": _id_arg()}, "required": ["id"]},
    },
    {
        "name": "kb_section",
        "description": "L2：只读取条目中的某一章或某一小节，并附上该段引用的来源。selector 可以是章序号（如 3）、小节号（如 3.2）或标题关键词（如 别搞混）。",
        "inputSchema": {
            "type": "object",
            "properties": {"id": _id_arg(), "selector": {"type": "string", "description": "章序号、小节号或关键词"}},
            "required": ["id", "selector"],
        },
    },
    {
        "name": "kb_neighbors",
        "description": "列出与条目有关系的其他条目（关系类型 + 一句话）。只在需要关联、对比、前置知识时使用。",
        "inputSchema": {
            "type": "object",
            "properties": {"id": _id_arg(), "depth": {"type": "integer", "minimum": 1, "maximum": 3, "description": "关系跳数，默认 1"}},
            "required": ["id"],
        },
    },
    {
        "name": "kb_context",
        "description": "一次取得干净的上下文包：目标卡片 + 目录 + 一跳邻居的一句话。",
        "inputSchema": {"type": "object", "properties": {"id": _id_arg()}, "required": ["id"]},
    },
    {
        "name": "kb_path",
        "description": "学习路径：沿'前置知识'关系展开，按先后顺序列出要学的条目（含尚未建立的条目）。",
        "inputSchema": {"type": "object", "properties": {"id": _id_arg()}, "required": ["id"]},
    },
    {
        "name": "kb_grep",
        "description": "全文搜索（兜底手段）：返回匹配行的条目 id、行号与片段。",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 100}},
            "required": ["query"],
        },
    },
    {
        "name": "kb_frontier",
        "description": "研究前沿：被引用但尚未建立的条目（按被引用次数排序），以及成熟度未达深度级的条目。用于决定下一步研究什么。",
        "inputSchema": {"type": "object", "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 100}}},
    },
    {
        "name": "kb_stats",
        "description": "知识库统计：条目数、成熟度分布、关系数、来源数、各领域条目数、最近更新。",
        "inputSchema": {"type": "object", "properties": {}},
    },
]
for _t in TOOLS:
    _t["annotations"] = {"readOnlyHint": True, "openWorldHint": False}


def _frontier(kb: KB, limit: int) -> str:
    pend = sorted(kb.pending().items(), key=lambda kv: (-len(kv[1]), kv[0]))[:limit]
    lines = ["# 待建条目（被引用次数）"]
    for tgt, refs in pend:
        who = "、".join(sorted({s for s, _ in refs}))
        lines.append(f"- `{tgt}` ×{len(refs)}（被 {who} 引用）")
    lines.append("")
    lines.append("# 未达深度级的条目")
    rest = [e for e in kb.entries if e.status != "deep"]
    lines += [f"- {kblib.view_l0(kb, e.id)}" for e in rest] or ["（无）"]
    return "\n".join(lines)


def call_tool(name: str, args: dict) -> str:
    kb = KB.load()  # 每次重新加载，保证读到最新的文件
    if name == "kb_find":
        hits = kb.find(str(args["query"]), int(args.get("limit", 8)))
        return "\n".join(kblib.view_l0(kb, eid) for _, eid in hits) or f"未找到「{args['query']}」。"
    if name == "kb_card":
        ids = args.get("ids") or ([args["id"]] if "id" in args else [])
        if isinstance(ids, str):
            ids = [ids]
        return "\n\n---\n\n".join(kblib.view_card(kb, i) for i in ids)
    if name == "kb_outline":
        return kblib.view_outline(kb, args["id"])
    if name == "kb_section":
        return kblib.view_section(kb, args["id"], str(args["selector"]))
    if name == "kb_neighbors":
        return kblib.view_neighbors(kb, args["id"], int(args.get("depth", 1)))
    if name == "kb_context":
        return kblib.view_context(kb, args["id"])
    if name == "kb_path":
        return kblib.view_path(kb, args["id"])
    if name == "kb_grep":
        rows = kb.grep(str(args["query"]), int(args.get("limit", 20)))
        return "\n".join(f"{eid}:{ln}: {txt}" for eid, ln, txt in rows) or "无匹配。"
    if name == "kb_frontier":
        return _frontier(kb, int(args.get("limit", 20)))
    if name == "kb_stats":
        return kblib.gen_readme_stats(kb)
    raise KBError(f"未知工具：{name}")


def handle(msg: dict) -> dict | None:
    method = msg.get("method")
    mid = msg.get("id")
    is_request = "id" in msg

    def ok(result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": mid, "result": result}

    def fail(code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": mid, "error": {"code": code, "message": message}}

    if method == "initialize":
        requested = (msg.get("params") or {}).get("protocolVersion")
        version = requested if requested in SUPPORTED_VERSIONS else SUPPORTED_VERSIONS[1]
        return ok({
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
            "instructions": INSTRUCTIONS,
        })
    if method == "ping":
        return ok({})
    if method == "tools/list":
        return ok({"tools": TOOLS})
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name", "")
        args = params.get("arguments") or {}
        if name not in {t["name"] for t in TOOLS}:
            return fail(-32602, f"未知工具：{name}")
        try:
            text = call_tool(name, args)
            return ok({"content": [{"type": "text", "text": text}], "isError": False})
        except (KBError, KeyError, ValueError, TypeError) as exc:
            return ok({"content": [{"type": "text", "text": f"错误：{exc}"}], "isError": True})
    if not is_request:  # 通知（如 notifications/initialized）无需回复
        return None
    return fail(-32601, f"不支持的方法：{method}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            out = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON 解析失败"}}
        else:
            try:
                out = handle(msg) if isinstance(msg, dict) else None
            except Exception:  # 兜底：任何意外都不能让服务退出
                traceback.print_exc(file=sys.stderr)
                out = {"jsonrpc": "2.0", "id": msg.get("id"), "error": {"code": -32603, "message": "服务内部错误"}}
        if out is not None:
            sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
