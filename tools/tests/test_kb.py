"""知识库工具自测：python3 -m unittest discover -s tools/tests"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))
import kblib  # noqa: E402
from kblib import KB, Entry  # noqa: E402

GOOD = """---
id: demo-concept
title: 示例概念
en: Demo Concept
aliases: [示例, Bayes' theorem, "a, b"]
kind: concept
domain: tech-ai
tags: [测试]
summary: 一个用于测试的示例概念。
confidence: medium
status: draft
created: 2026-01-01
updated: 2026-01-02
relations:
  - based-on: attention-mechanism | 先懂注意力
  - contrasts: not-yet-written   # 注释会被忽略
---

# 示例概念

<!-- CARD:START -->
> **一句话**：示例。[^a]
<!-- CARD:END -->

## 1. 是什么：定义

正文[^a][^b]。

### 1.1 小节一

细节。

## 2. 关联

<!-- RELATIONS:START -->
<!-- RELATIONS:END -->

## 3. 来源

[^a]: **S1** · 作者，《标题》 · <https://example.org/a> · 核实：全文 · 访问 2026-01-01 · 支撑：定义
[^b]: **S3** · 作者，《标题二》 · <https://example.org/b> · 核实：摘要 · 访问 2026-01-01 · 支撑：细节
"""


def make_entry(text: str, domain: str = "tech-ai", name: str = "demo-concept") -> Entry:
    path = kblib.KB_DIR / domain / f"{name}.md"
    meta, body, _ = kblib.parse_front_matter(text)
    e = Entry(path=path, meta=meta, body=body)
    kblib._parse_body(e)
    return e


def errors_of(kb: KB, e: Entry) -> list[str]:
    return [i.msg for i in kblib.check_entry(kb, e, dt.date(2026, 6, 1)) if i.level == "ERROR"]


class FrontMatterTest(unittest.TestCase):
    def test_parse(self):
        meta, body, _ = kblib.parse_front_matter(GOOD)
        self.assertEqual(meta["id"], "demo-concept")
        self.assertEqual(meta["aliases"], ["示例", "Bayes' theorem", "a, b"])
        self.assertEqual(meta["relations"][0], {"type": "based-on", "target": "attention-mechanism", "note": "先懂注意力"})
        self.assertEqual(meta["relations"][1]["target"], "not-yet-written")
        self.assertTrue(body.lstrip().startswith("# 示例概念"))

    def test_unterminated(self):
        with self.assertRaises(kblib.KBError):
            kblib.parse_front_matter("---\nid: x\n")


class EntryTest(unittest.TestCase):
    def setUp(self):
        self.kb = KB.load()

    def test_body_parsing(self):
        e = make_entry(GOOD)
        self.assertIn("一句话", e.card)
        self.assertEqual([s.heading for s in e.sections][:2], ["1. 是什么：定义", "2. 关联"])
        self.assertEqual(e.sections[0].children[0].heading, "1.1 小节一")
        self.assertEqual({s.key for s in e.sources}, {"a", "b"})
        self.assertEqual(e.s1_count(), 1)

    def test_good_draft_passes(self):
        e = make_entry(GOOD)
        kb = KB(self.kb.entries + [e])
        self.assertEqual(errors_of(kb, e), [])

    def test_missing_tier_and_verify(self):
        e = make_entry(GOOD.replace("**S3** · ", "").replace("核实：摘要 · ", ""))
        errs = errors_of(KB(self.kb.entries + [e]), e)
        self.assertTrue(any("分级" in m for m in errs))
        self.assertTrue(any("核实方式" in m for m in errs))

    def test_undefined_footnote(self):
        e = make_entry(GOOD.replace("正文[^a][^b]。", "正文[^a][^zz]。"))
        errs = errors_of(KB(self.kb.entries + [e]), e)
        self.assertTrue(any("[^zz]" in m for m in errs))

    def test_status_floor(self):
        e = make_entry(GOOD.replace("status: draft", "status: standard"))
        errs = errors_of(KB(self.kb.entries + [e]), e)
        self.assertTrue(any("≥5 个来源" in m for m in errs))
        self.assertTrue(any("必需章节" in m for m in errs))

    def test_confidence_floor(self):
        e = make_entry(GOOD.replace("confidence: medium", "confidence: high"))
        errs = errors_of(KB(self.kb.entries + [e]), e)
        self.assertTrue(any("置信度 `high`" in m for m in errs))

    def test_bad_relation_and_domain(self):
        bad = GOOD.replace("- contrasts: not-yet-written", "- loves: Not_An_Id").replace("domain: tech-ai", "domain: magic")
        e = make_entry(bad)
        errs = errors_of(KB(self.kb.entries + [e]), e)
        self.assertTrue(any("未知关系类型" in m for m in errs))
        self.assertTrue(any("不是合法 id" in m for m in errs))
        self.assertTrue(any("未知领域" in m for m in errs))

    def test_wrong_directory(self):
        e = make_entry(GOOD, domain="history")
        errs = errors_of(KB(self.kb.entries + [e]), e)
        self.assertTrue(any("所在目录" in m for m in errs))


class RepositoryTest(unittest.TestCase):
    """对仓库里真实的条目做集成检查。"""

    def setUp(self):
        self.kb = KB.load()

    def test_repo_has_no_errors(self):
        errs = [str(i) for i in kblib.check_all(self.kb) if i.level == "ERROR"]
        self.assertEqual(errs, [])

    def test_generated_files_fresh(self):
        stale = kblib.stale_outputs(kblib.planned_outputs(self.kb))
        self.assertEqual(stale, [], "派生文件过期，请运行 python3 tools/kb.py index")

    def test_graph_json_consistent(self):
        data = json.loads(kblib.gen_graph_json(self.kb))
        ids = {n["id"] for n in data["nodes"]}
        for edge in data["edges"]:
            self.assertIn(edge["source"], ids)
            self.assertIn(edge["target"], ids)

    def test_find_and_views(self):
        self.assertEqual(self.kb.find("熵")[0][1], "entropy")
        self.assertEqual(self.kb.find("entorpy")[0][1], "entropy")  # 拼写容错
        self.assertEqual(self.kb.find("nope"), [])
        self.assertIn("3.2", kblib.view_section(self.kb, "attention-mechanism", "3.2").splitlines()[0])
        self.assertIn("本段引用的来源", kblib.view_section(self.kb, "attention-mechanism", "3.2"))
        self.assertIn("目录", kblib.view_outline(self.kb, "silk-road"))
        path = self.kb.learning_path("attention-mechanism")
        self.assertEqual(path[-1], "attention-mechanism")
        self.assertIn("softmax", path)
        with self.assertRaises(kblib.KBError):
            kblib.view_card(self.kb, "does-not-exist")


class McpServerTest(unittest.TestCase):
    def rpc(self, messages: list[dict]) -> list[dict]:
        proc = subprocess.run(
            [sys.executable, str(TOOLS / "mcp_server.py")],
            input="\n".join(json.dumps(m) for m in messages) + "\n",
            capture_output=True, text=True, timeout=60,
        )
        return [json.loads(line) for line in proc.stdout.splitlines() if line.strip()]

    def test_handshake_and_tools(self):
        out = self.rpc([
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "kb_find", "arguments": {"query": "丝路"}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "kb_card", "arguments": {"ids": ["nope"]}}},
            {"jsonrpc": "2.0", "id": 5, "method": "nope"},
        ])
        by_id = {m["id"]: m for m in out}
        self.assertEqual(len(out), 5)  # 通知没有回复
        self.assertEqual(by_id[1]["result"]["protocolVersion"], "2025-06-18")
        names = {t["name"] for t in by_id[2]["result"]["tools"]}
        self.assertTrue({"kb_find", "kb_card", "kb_section", "kb_neighbors"} <= names)
        self.assertIn("silk-road", by_id[3]["result"]["content"][0]["text"])
        self.assertTrue(by_id[4]["result"]["isError"])
        self.assertEqual(by_id[5]["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
