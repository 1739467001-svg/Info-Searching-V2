#!/usr/bin/env python3
"""把网页阅读器和知识库文件组装成可直接托管的静态站点目录（默认 _site/）。

用法：
  python3 tools/build_site.py [输出目录]
  python3 -m http.server -d _site 8000     # 本地预览：http://localhost:8000
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIRS = ["kb", "system", "graph", "templates"]
FILES = ["README.md", "INDEX.md", "ROADMAP.md", "AGENTS.md", "inbox.md"]


def build(out: Path) -> int:
    if out.resolve() == ROOT:
        raise SystemExit("输出目录不能是仓库根目录")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copy2(ROOT / "site" / "index.html", out / "index.html")
    count = 1
    for d in DIRS:
        for p in (ROOT / d).rglob("*"):
            if p.is_file() and p.suffix in {".md", ".json"}:
                dest = out / p.relative_to(ROOT)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(p, dest)
                count += 1
    for f in FILES:
        if (ROOT / f).exists():
            shutil.copy2(ROOT / f, out / f)
            count += 1
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return count


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "_site"
    n = build(target)
    print(f"已生成 {target}（{n} 个文件）。本地预览：python3 -m http.server -d {target} 8000")
