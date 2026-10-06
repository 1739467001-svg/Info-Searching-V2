#!/usr/bin/env python3
"""kb —— Info-Searching-V2 知识库命令行（仅依赖 Python 标准库）。

检索（渐进式披露，从轻到重）：
  kb.py find <词>                 L0：查条目是否存在（标题/英文名/别名/标签/一句话）
  kb.py card <id> [<id> ...]      L1：读卡片（一句话 + 30 秒版 + 要点）
  kb.py outline <id>              看目录与每章行数，决定要不要深入
  kb.py section <id> <序号|关键词>  L2：只读某一章（自动附上该章引用的来源）
  kb.py neighbors <id> [-d 2]     邻居条目的一句话（需要关联时才用）
  kb.py context <id>              干净上下文包 = 卡片 + 目录 + 一跳邻居
  kb.py path <id>                 学习路径（沿"前置知识"关系展开）
  kb.py grep <文本>                全文搜索（兜底）

维护：
  kb.py new <kind> <id> --domain <领域> --title <中文名> [--en <英文名>]
  kb.py index [--check]           重新生成 INDEX.md / graph / 领域 README / 关联区块
  kb.py check [--strict]          按体系规范校验全部条目
  kb.py due                       列出到期需要复核的条目
  kb.py stats                     统计
  kb.py anki [-o 文件]             把自测题导出为 Anki 可导入的 TSV
"""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kblib  # noqa: E402
from kblib import KB, KBError  # noqa: E402


def _out(text: str) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass
    print(text)


def cmd_find(kb: KB, a) -> int:
    hits = kb.find(" ".join(a.query), a.limit)
    if not hits:
        _out(f"未找到「{' '.join(a.query)}」。可以新建：python3 tools/kb.py new concept <id> --domain <领域> --title <名称>")
        return 1
    for score, eid in hits:
        _out(f"{score:5.1f}  {kblib.view_l0(kb, eid)}")
    return 0


def cmd_grep(kb: KB, a) -> int:
    rows = kb.grep(" ".join(a.query), a.limit)
    for eid, line, text in rows:
        _out(f"{eid}:{line}: {text}")
    return 0 if rows else 1


def cmd_card(kb: KB, a) -> int:
    _out("\n\n---\n\n".join(kblib.view_card(kb, i) for i in a.ids))
    return 0


def cmd_outline(kb: KB, a) -> int:
    _out(kblib.view_outline(kb, a.id))
    return 0


def cmd_section(kb: KB, a) -> int:
    _out(kblib.view_section(kb, a.id, " ".join(a.selector)))
    return 0


def cmd_neighbors(kb: KB, a) -> int:
    _out(kblib.view_neighbors(kb, a.id, a.depth))
    return 0


def cmd_context(kb: KB, a) -> int:
    _out(kblib.view_context(kb, a.id))
    return 0


def cmd_path(kb: KB, a) -> int:
    _out(kblib.view_path(kb, a.id))
    return 0


def cmd_new(kb: KB, a) -> int:
    if a.kind not in kblib.KINDS:
        raise KBError(f"未知类型 {a.kind}，可选：{', '.join(kblib.KINDS)}")
    if a.domain not in kblib.DOMAINS:
        raise KBError(f"未知领域 {a.domain}，可选：{', '.join(kblib.DOMAINS)}")
    if not kblib.ID_RE.match(a.id):
        raise KBError("id 只允许小写字母、数字、连字符，例如 attention-mechanism")
    if a.id in kb.by_id:
        raise KBError(f"条目已存在：{kb.by_id[a.id].rel_path}")
    dup = [eid for _, eid in kb.find(a.title, 3) if eid in kb.by_id]
    if dup and not a.force:
        raise KBError(f"可能已有相近条目：{', '.join(dup)}。确认不是重复后加 --force")
    tpl = kblib.TEMPLATE_DIR / f"{a.kind}.md"
    text = tpl.read_text(encoding="utf-8")
    today = dt.date.today().isoformat()
    for k, v in {"id": a.id, "title": a.title, "en": a.en or "", "domain": a.domain, "date": today}.items():
        text = text.replace("{{" + k + "}}", v)
    dest = kblib.KB_DIR / a.domain / f"{a.id}.md"
    dest.write_text(text, encoding="utf-8")
    _out(f"已创建 {dest.relative_to(kblib.ROOT)}。写完后运行：python3 tools/kb.py index && python3 tools/kb.py check")
    return 0


def cmd_index(kb: KB, a) -> int:
    outputs = kblib.planned_outputs(kb)
    if a.check:
        stale = kblib.stale_outputs(outputs)
        if stale:
            _out("以下派生文件不是最新，请运行 python3 tools/kb.py index：")
            for p in stale:
                _out(f"  - {p.relative_to(kblib.ROOT)}")
            return 1
        _out(f"派生文件均为最新（{len(outputs)} 个）。")
        return 0
    changed = kblib.write_outputs(outputs)
    _out(f"已更新 {len(changed)} 个文件：" + ("、".join(str(p.relative_to(kblib.ROOT)) for p in changed) or "无变化"))
    return 0


def cmd_check(kb: KB, a) -> int:
    issues = kblib.check_all(kb)
    errors = [i for i in issues if i.level == "ERROR"]
    warns = [i for i in issues if i.level == "WARN"]
    for i in issues:
        _out(str(i))
    _out(f"\n共检查 {len(kb.entries)} 个条目：{len(errors)} 个错误，{len(warns)} 个提醒。")
    return 1 if errors or (a.strict and warns) else 0


def cmd_due(kb: KB, a) -> int:
    es = kblib.due_entries(kb)
    if not es:
        _out("没有到期需要复核的条目。")
        return 0
    for e in es:
        _out(f"{e.meta.get('review_after')}  {kblib.view_l0(kb, e.id)}")
    return 0


def cmd_stats(kb: KB, a) -> int:
    _out(kblib.gen_readme_stats(kb))
    return 0


def cmd_anki(kb: KB, a) -> int:
    rows = []
    for e in kb.entries:
        for q, ans in e.quiz:
            front = q.replace("\t", " ").replace("\n", "<br>")
            back = (ans.replace("\t", " ").replace("\n", "<br>") + f"<br><br>—— {e.title}")
            rows.append(f"{front}\t{back}\tinfo-kb {e.domain} {e.id}")
    text = "#separator:tab\n#html:true\n#tags column:3\n" + "\n".join(rows) + "\n"
    if a.output:
        Path(a.output).write_text(text, encoding="utf-8")
        _out(f"已导出 {len(rows)} 张卡片到 {a.output}（Anki：文件 → 导入）")
    else:
        _out(text)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="kb.py", description="Info-Searching-V2 知识库工具", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("find", help="L0：按名称/别名/标签查找条目")
    s.add_argument("query", nargs="+")
    s.add_argument("-n", "--limit", type=int, default=10)
    s.set_defaults(func=cmd_find)

    s = sub.add_parser("grep", help="全文搜索")
    s.add_argument("query", nargs="+")
    s.add_argument("-n", "--limit", type=int, default=20)
    s.set_defaults(func=cmd_grep)

    s = sub.add_parser("card", help="L1：读卡片")
    s.add_argument("ids", nargs="+")
    s.set_defaults(func=cmd_card)

    s = sub.add_parser("outline", help="条目目录")
    s.add_argument("id")
    s.set_defaults(func=cmd_outline)

    s = sub.add_parser("section", help="L2：读某一章")
    s.add_argument("id")
    s.add_argument("selector", nargs="+")
    s.set_defaults(func=cmd_section)

    s = sub.add_parser("neighbors", help="关联条目的一句话")
    s.add_argument("id")
    s.add_argument("-d", "--depth", type=int, default=1)
    s.set_defaults(func=cmd_neighbors)

    s = sub.add_parser("context", help="干净上下文包")
    s.add_argument("id")
    s.set_defaults(func=cmd_context)

    s = sub.add_parser("path", help="学习路径")
    s.add_argument("id")
    s.set_defaults(func=cmd_path)

    s = sub.add_parser("new", help="从模板新建条目")
    s.add_argument("kind", choices=list(kblib.KINDS))
    s.add_argument("id")
    s.add_argument("--domain", required=True, choices=list(kblib.DOMAINS))
    s.add_argument("--title", required=True)
    s.add_argument("--en", default="")
    s.add_argument("--force", action="store_true", help="跳过疑似重复检查")
    s.set_defaults(func=cmd_new)

    s = sub.add_parser("index", help="重新生成派生文件")
    s.add_argument("--check", action="store_true", help="只检查是否最新（CI 用）")
    s.set_defaults(func=cmd_index)

    s = sub.add_parser("check", help="校验")
    s.add_argument("--strict", action="store_true", help="提醒也视为失败")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("due", help="到期复核")
    s.set_defaults(func=cmd_due)

    s = sub.add_parser("stats", help="统计")
    s.set_defaults(func=cmd_stats)

    s = sub.add_parser("anki", help="导出自测题")
    s.add_argument("-o", "--output")
    s.set_defaults(func=cmd_anki)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(KB.load(), args)
    except KBError as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
