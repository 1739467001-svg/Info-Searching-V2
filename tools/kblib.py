"""kblib —— Info-Searching-V2 知识库核心库（仅依赖 Python 标准库，Python ≥ 3.9）。

职责：
  1. 解析条目（front-matter + 卡片 + 章节 + 脚注来源 + 自测题）
  2. 校验条目是否满足体系规范（system/ 下的各项标准）
  3. 生成派生文件（INDEX.md、graph/、领域 README、条目内关联区块）
  4. 按需检索（find / card / outline / section / neighbors / context / path）

设计原则：所有"可被推导的东西"都由脚本生成，人和 AI 只维护条目本身的 front-matter 与正文。
"""
from __future__ import annotations

import datetime as dt
import difflib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB_DIR = ROOT / "kb"
GRAPH_DIR = ROOT / "graph"
TEMPLATE_DIR = ROOT / "templates"

# ---------------------------------------------------------------------------
# 体系常量（与 system/taxonomy.md 保持一致）
# ---------------------------------------------------------------------------

DOMAINS: dict[str, tuple[str, str, str]] = {
    # id: (中文名, 图标, 范围)
    "formal-sciences": ("形式科学", "🧮", "数学、逻辑、统计学、理论计算机科学"),
    "natural-sciences": ("自然科学", "🔭", "物理、化学、天文、地球科学"),
    "life-medicine": ("生命与医学", "🧬", "生物学、遗传、生态、医学与健康"),
    "tech-ai": ("技术与 AI", "🤖", "计算机、人工智能、互联网、电子与工程技术"),
    "social-sciences": ("社会科学", "🏛️", "经济、心理、社会、政治、法律、教育"),
    "humanities": ("人文艺术", "📜", "哲学、宗教、语言、文学、艺术、传统文化"),
    "history": ("历史", "⏳", "历史事件、时代、文明与史学概念"),
    "geography": ("地理与地区", "🌍", "自然地理、人文地理、国家与地区"),
    "business": ("商业与产业", "💼", "企业、产业、金融、产品与商业模式"),
    "thinking": ("思维与方法", "🧠", "心智模型、学习方法、决策与认知工具"),
}

KINDS: dict[str, str] = {
    "concept": "概念",
    "topic": "专题",
    "event": "事件",
    "person": "人物",
    "place": "地点",
    "work": "作品",
}

STATUSES: dict[str, str] = {"draft": "草稿", "standard": "标准", "deep": "深度"}
CONFIDENCE: dict[str, str] = {"high": "高", "medium": "中", "low": "低"}

# 关系类型：id -> (正向标签, 反向标签)
# "A based-on B" 读作"A 的前置知识是 B"；在 B 的页面上显示为"A · 后续延伸"。
RELATIONS: dict[str, tuple[str, str]] = {
    "is-a": ("是一种", "下位/实例"),
    "part-of": ("属于", "包含"),
    "based-on": ("前置知识", "后续延伸"),
    "leads-to": ("催生/演化出", "源自"),
    "contrasts": ("区别于", "区别于"),
    "applies-to": ("应用于", "所用方法"),
    "influenced": ("影响了", "受其影响"),
    "located-in": ("位于", "境内/包含"),
    "covers": ("涵盖", "收录于"),
    "related": ("相关", "相关"),
}

# 各类型在 status ≥ standard 时必须出现的 H2 章节关键词（按顺序书写，检查时只看是否出现）
REQUIRED_SECTIONS: dict[str, list[str]] = {
    "concept": ["是什么", "为什么", "怎么运作", "从哪来", "看例子", "别搞混", "怎么看", "怎么用"],
    "topic": ["是什么", "版图", "脉络", "关键概念", "代表", "趋势", "怎么看", "学习路径"],
    "event": ["是什么", "背景", "经过", "人物与力量", "影响", "史料与争议", "别搞混", "怎么用"],
    "person": ["是谁", "生平", "贡献", "思想", "影响", "评价", "别搞混", "怎么用"],
    "place": ["在哪里", "自然", "人文", "历史", "经济", "文化", "别搞混", "今日"],
    "work": ["基本信息", "主旨", "结构", "核心观点", "评价", "适合谁"],
}
COMMON_SECTIONS = ["自测", "关联", "来源", "我的思考"]
DRAFT_SECTIONS = ["关联", "来源"]

# 成熟度底线
STATUS_FLOOR = {
    "draft": {"sources": 1, "s1": 0, "quiz": 0},
    "standard": {"sources": 5, "s1": 1, "quiz": 3},
    "deep": {"sources": 8, "s1": 2, "quiz": 5},
}
# 置信度底线（只校验可量化部分；"核心论断是否被交叉印证"仍需写作者判断）
CONFIDENCE_FLOOR = {
    "high": {"sources": 3, "s1": 1},
    "medium": {"sources": 2, "s1": 0},
    "low": {"sources": 0, "s1": 0},
}

REQUIRED_FIELDS = ["id", "title", "kind", "domain", "summary", "confidence", "status", "created", "updated"]
ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SUMMARY_MAX = 60
CARD_MAX_LINES = 25

CARD_START, CARD_END = "<!-- CARD:START -->", "<!-- CARD:END -->"
REL_START, REL_END = "<!-- RELATIONS:START -->", "<!-- RELATIONS:END -->"
AUTO_START, AUTO_END = "<!-- AUTO:START -->", "<!-- AUTO:END -->"

FOOTNOTE_DEF_RE = re.compile(r"^\[\^([\w-]+)\]:\s*(.+)$", re.M)
FOOTNOTE_REF_RE = re.compile(r"\[\^([\w-]+)\](?!:)")
TIER_RE = re.compile(r"\*\*(S[123])\*\*")
VERIFY_RE = re.compile(r"核实[：:]\s*(全文|摘要|转引)")
QUIZ_RE = re.compile(r"<details>\s*<summary>(.*?)</summary>(.*?)</details>", re.S)
MD_LINK_RE = re.compile(r"\]\(([^)\s]+\.md)(#[^)]*)?\)")
PENDING_MARK_RE = re.compile(r"【待核】")


class KBError(Exception):
    pass


# ---------------------------------------------------------------------------
# front-matter：YAML 的一个安全子集（标量 / 行内列表 / 块列表 / "- key: value | 备注"）
# ---------------------------------------------------------------------------

def _strip_comment(value: str) -> str:
    in_quote = None
    for i, ch in enumerate(value):
        if ch in "\"'" and (in_quote is None or in_quote == ch):
            # 只把出现在开头或分隔符后的引号当作引号，避免把 Bayes' 这种撇号当成引号
            if in_quote is None and i > 0 and value[i - 1] not in " [,":
                continue
            in_quote = None if in_quote == ch else ch
        elif ch == "#" and in_quote is None and i > 0 and value[i - 1] in " \t":
            return value[:i].rstrip()
    return value.strip()


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        return s[1:-1]
    return s


def _split_flow_list(inner: str) -> list[str]:
    items, buf, quote = [], [], None
    for i, ch in enumerate(inner):
        if ch in "\"'" and (quote == ch or (quote is None and (i == 0 or inner[i - 1] in " ,"))):
            quote = None if quote == ch else ch
            buf.append(ch)
        elif ch == "," and quote is None:
            items.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    items.append("".join(buf))
    return [_unquote(x) for x in items if x.strip()]


def _parse_scalar(value: str):
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        return _split_flow_list(value[1:-1])
    return _unquote(value)


def parse_front_matter(text: str) -> tuple[dict, str, int]:
    """返回 (元数据, 正文, 正文起始行号)。没有 front-matter 时元数据为空字典。"""
    if not text.startswith("---\n"):
        return {}, text, 1
    end = text.find("\n---\n", 4)
    if end == -1:
        raise KBError("front-matter 缺少结束分隔线 ---")
    block = text[4:end]
    body = text[end + 5:]
    data: dict = {}
    key = None
    for lineno, raw in enumerate(block.splitlines(), start=2):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if raw[:1] in (" ", "\t") or raw.startswith("- "):
            item = raw.strip()
            if not item.startswith("- ") or key is None:
                raise KBError(f"front-matter 第 {lineno} 行无法解析：{raw!r}")
            item = _strip_comment(item[2:])
            if not isinstance(data.get(key), list):
                data[key] = []
            m = re.match(r"^([A-Za-z][\w-]*):\s*(.+)$", item)
            if m:
                target, _, note = m.group(2).partition("|")
                data[key].append({"type": m.group(1), "target": _unquote(target), "note": note.strip()})
            else:
                data[key].append(_unquote(item))
            continue
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", raw)
        if not m:
            raise KBError(f"front-matter 第 {lineno} 行无法解析：{raw!r}")
        key, value = m.group(1), _strip_comment(m.group(2))
        data[key] = _parse_scalar(value) if value else []
    return data, body, block.count("\n") + 3


# ---------------------------------------------------------------------------
# 条目模型
# ---------------------------------------------------------------------------

@dataclass
class Section:
    heading: str
    level: int
    start: int  # 正文中的行号（1 起）
    text: str
    children: list["Section"] = field(default_factory=list)

    @property
    def number(self) -> str:
        m = re.match(r"^(\d+(?:\.\d+)?)[.、\s]", self.heading)
        return m.group(1) if m else ""


@dataclass
class Source:
    key: str
    text: str
    tier: str  # S1 / S2 / S3 / ""
    verify: str  # 全文 / 摘要 / 转引 / ""


@dataclass
class Entry:
    path: Path
    meta: dict
    body: str
    title_line: str = ""
    card: str = ""
    sections: list[Section] = field(default_factory=list)
    sources: list[Source] = field(default_factory=list)
    footnote_refs: set[str] = field(default_factory=set)
    quiz: list[tuple[str, str]] = field(default_factory=list)
    parse_error: str = ""

    # -- 便捷属性 -------------------------------------------------------
    @property
    def id(self) -> str:
        return str(self.meta.get("id", self.path.stem))

    @property
    def title(self) -> str:
        return str(self.meta.get("title", self.path.stem))

    @property
    def en(self) -> str:
        v = self.meta.get("en", "")
        return v if isinstance(v, str) else ""

    @property
    def aliases(self) -> list[str]:
        v = self.meta.get("aliases", [])
        return [v] if isinstance(v, str) and v else (v if isinstance(v, list) else [])

    @property
    def tags(self) -> list[str]:
        v = self.meta.get("tags", [])
        return [v] if isinstance(v, str) and v else (v if isinstance(v, list) else [])

    @property
    def domain(self) -> str:
        return str(self.meta.get("domain", ""))

    @property
    def kind(self) -> str:
        return str(self.meta.get("kind", ""))

    @property
    def status(self) -> str:
        return str(self.meta.get("status", ""))

    @property
    def confidence(self) -> str:
        return str(self.meta.get("confidence", ""))

    @property
    def summary(self) -> str:
        return str(self.meta.get("summary", ""))

    @property
    def updated(self) -> str:
        return str(self.meta.get("updated", ""))

    @property
    def relations(self) -> list[dict]:
        v = self.meta.get("relations", [])
        return [r for r in v if isinstance(r, dict)] if isinstance(v, list) else []

    @property
    def rel_path(self) -> str:
        return self.path.relative_to(ROOT).as_posix()

    def display(self) -> str:
        return f"{self.title}（{self.en}）" if self.en else self.title

    def s1_count(self) -> int:
        return sum(1 for s in self.sources if s.tier == "S1")


def _split_sections(lines: list[str], lo: int, hi: int, marker: str, offset: int = 0) -> list[Section]:
    """按标题标记切分 lines[lo:hi]，忽略代码块中的标题。"""
    heads = []
    in_code = False
    for i in range(lo, hi):
        ln = lines[i]
        if ln.startswith("```"):
            in_code = not in_code
        if not in_code and ln.startswith(marker):
            heads.append((i, ln[len(marker):].strip()))
    out = []
    for idx, (i, h) in enumerate(heads):
        j = heads[idx + 1][0] if idx + 1 < len(heads) else hi
        out.append(Section(h, len(marker) - 1, offset + i + 1, "\n".join(lines[i:j]).rstrip()))
    return out


def _parse_body(entry: Entry) -> None:
    body = entry.body
    m = re.search(r"^#\s+(.+)$", body, re.M)
    entry.title_line = m.group(1).strip() if m else ""
    if CARD_START in body and CARD_END in body:
        entry.card = body.split(CARD_START, 1)[1].split(CARD_END, 1)[0].strip("\n")
    # 章节（只按 H2 切分；H3 归入所属 H2；忽略代码块里的 "## "）
    lines = body.splitlines()
    entry.sections = _split_sections(lines, 0, len(lines), "## ")
    for sec in entry.sections:
        sub_lines = sec.text.splitlines()
        sec.children = _split_sections(sub_lines, 1, len(sub_lines), "### ", offset=sec.start - 1)
    for key, text in FOOTNOTE_DEF_RE.findall(body):
        tier = TIER_RE.search(text)
        ver = VERIFY_RE.search(text)
        entry.sources.append(Source(key, text.strip(), tier.group(1) if tier else "", ver.group(1) if ver else ""))
    entry.footnote_refs = set(FOOTNOTE_REF_RE.findall(body))
    entry.quiz = [(_clean_html(q), _clean_html(a)) for q, a in QUIZ_RE.findall(body)]


def _clean_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{2,}", "\n", s).strip()


def load_entry(path: Path) -> Entry:
    text = path.read_text(encoding="utf-8")
    try:
        meta, body, _ = parse_front_matter(text)
    except KBError as exc:
        return Entry(path=path, meta={}, body=text, parse_error=str(exc))
    entry = Entry(path=path, meta=meta, body=body)
    _parse_body(entry)
    return entry


def iter_entry_paths() -> list[Path]:
    paths = []
    for d in sorted(KB_DIR.iterdir()) if KB_DIR.exists() else []:
        if d.is_dir():
            paths += [p for p in sorted(d.glob("*.md")) if p.name != "README.md"]
    return paths


class KB:
    """整个知识库的内存视图。"""

    def __init__(self, entries: list[Entry]):
        self.entries = entries
        self.by_id: dict[str, Entry] = {}
        for e in entries:
            self.by_id.setdefault(e.id, e)

    @classmethod
    def load(cls) -> "KB":
        return cls([load_entry(p) for p in iter_entry_paths()])

    # -- 图 -------------------------------------------------------------
    def edges(self) -> list[tuple[str, str, str, str]]:
        """(source, type, target, note)，按出现顺序。"""
        out = []
        for e in self.entries:
            for r in e.relations:
                out.append((e.id, r.get("type", ""), r.get("target", ""), r.get("note", "")))
        return out

    def outgoing(self, eid: str) -> list[tuple[str, str, str]]:
        return [(t, tgt, note) for s, t, tgt, note in self.edges() if s == eid]

    def incoming(self, eid: str) -> list[tuple[str, str, str]]:
        return [(s, t, note) for s, t, tgt, note in self.edges() if tgt == eid]

    def pending(self) -> dict[str, list[tuple[str, str]]]:
        """被引用但尚未建立条目的目标 -> [(引用者, 关系类型)]。"""
        out: dict[str, list[tuple[str, str]]] = {}
        for s, t, tgt, _ in self.edges():
            if tgt and tgt not in self.by_id:
                out.setdefault(tgt, []).append((s, t))
        return out

    def neighbors(self, eid: str, depth: int = 1) -> list[tuple[int, str, str, str, str]]:
        """BFS 邻居：(距离, 方向 out/in, 关系类型, 邻居 id, 备注)。"""
        seen = {eid}
        frontier = [eid]
        result = []
        for d in range(1, depth + 1):
            nxt = []
            for cur in frontier:
                for t, tgt, note in self.outgoing(cur):
                    if tgt not in seen:
                        seen.add(tgt)
                        nxt.append(tgt)
                        result.append((d, "out", t, tgt, note))
                for src, t, note in self.incoming(cur):
                    if src not in seen:
                        seen.add(src)
                        nxt.append(src)
                        result.append((d, "in", t, src, note))
            frontier = [x for x in nxt if x in self.by_id]
        return result

    def learning_path(self, eid: str) -> list[str]:
        """沿 based-on 边做后序 DFS，得到"先学什么、后学什么"的顺序（含待建条目）。"""
        order: list[str] = []
        visiting: set[str] = set()

        def dfs(node: str) -> None:
            if node in order or node in visiting:
                return
            visiting.add(node)
            for t, tgt, _ in self.outgoing(node):
                if t == "based-on":
                    dfs(tgt)
            visiting.discard(node)
            order.append(node)

        dfs(eid)
        return order

    # -- 检索 -----------------------------------------------------------
    def find(self, query: str, limit: int = 10) -> list[tuple[float, str]]:
        q = query.strip().lower()
        if not q:
            return []
        scored = []
        candidates = {e.id: e for e in self.entries}
        for eid, e in candidates.items():
            fields = {
                "id": [e.id],
                "title": [e.title],
                "en": [e.en],
                "alias": e.aliases,
                "tag": e.tags,
                "summary": [e.summary],
            }
            weights = {"id": 5, "title": 6, "en": 5, "alias": 5, "tag": 2, "summary": 1}
            score = 0.0
            for name, vals in fields.items():
                for v in vals:
                    v = (v or "").lower()
                    if not v:
                        continue
                    if v == q:
                        score += weights[name] * 3
                    elif q in v:
                        score += weights[name] * 1.5
                    elif v in q and len(v) >= 2:
                        score += weights[name]
                    elif name in ("title", "en", "alias", "id"):
                        score += weights[name] * _fuzzy(q, v) * 0.5
            if score > 0:
                scored.append((score, eid))
        for tgt in self.pending():
            if q in tgt or tgt in q.replace(" ", "-"):
                scored.append((1.0, tgt))
        scored.sort(key=lambda x: (-x[0], x[1]))
        return scored[:limit]

    def grep(self, query: str, limit: int = 20) -> list[tuple[str, int, str]]:
        out = []
        for e in self.entries:
            for i, ln in enumerate(e.body.splitlines(), start=1):
                if query.lower() in ln.lower():
                    out.append((e.id, i, ln.strip()[:160]))
                    if len(out) >= limit:
                        return out
        return out


def _fuzzy(q: str, v: str) -> float:
    """模糊相似度：中文按字重合率（≥0.6 才算），拉丁字母按编辑相似度（≥0.75 才算）。"""
    if any("\u4e00" <= ch <= "\u9fff" for ch in q):
        common = len(set(q) & set(v)) / max(len(set(q)), 1)
        return common if common >= 0.6 else 0.0
    ratio = difflib.SequenceMatcher(None, q, v).ratio()
    return ratio if ratio >= 0.75 else 0.0


# ---------------------------------------------------------------------------
# 链接与渲染辅助
# ---------------------------------------------------------------------------

def rel_link(from_path: Path, to_path: Path) -> str:
    return Path(os.path.relpath(to_path, from_path.parent)).as_posix()


def entry_link(kb: KB, from_path: Path, target_id: str) -> str:
    t = kb.by_id.get(target_id)
    if not t:
        return f"`{target_id}` 〔待建〕"
    return f"[{t.title}]({rel_link(from_path, t.path)})"


def render_relations_block(kb: KB, e: Entry) -> str:
    lines = []
    out = e.relations
    inc = kb.incoming(e.id)
    if out:
        lines.append("**出链**（本条 → 其他）")
        lines.append("")
        for r in out:
            label = RELATIONS.get(r.get("type", ""), (r.get("type", ""), ""))[0]
            note = f"：{r['note']}" if r.get("note") else ""
            lines.append(f"- **{label}** → {entry_link(kb, e.path, r.get('target', ''))}{note}")
    if inc:
        if lines:
            lines.append("")
        lines.append("**入链**（其他 → 本条）")
        lines.append("")
        for src, t, note in sorted(inc, key=lambda x: (x[1], x[0])):
            label = RELATIONS.get(t, ("", t))[1]
            note = f"：{note}" if note else ""
            lines.append(f"- {entry_link(kb, e.path, src)} · **{label}**{note}")
    if not lines:
        lines.append("（暂无关联。请在 front-matter 的 `relations` 中声明。）")
    lines.append("")
    lines.append(f"> 学习路径：`python3 tools/kb.py path {e.id}` ｜ 一跳邻居：`python3 tools/kb.py neighbors {e.id}`")
    return "\n".join(lines)


def replace_block(text: str, start: str, end: str, content: str) -> str:
    if start not in text or end not in text:
        raise KBError(f"缺少区块标记 {start} / {end}")
    pre, rest = text.split(start, 1)
    _, post = rest.split(end, 1)
    return f"{pre}{start}\n{content}\n{end}{post}"


def md_escape_cell(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ")


def status_badge(e: Entry) -> str:
    return {"draft": "🌱草稿", "standard": "🌿标准", "deep": "🌳深度"}.get(e.status, e.status)


def conf_badge(e: Entry) -> str:
    return CONFIDENCE.get(e.confidence, e.confidence)


# ---------------------------------------------------------------------------
# 校验
# ---------------------------------------------------------------------------

@dataclass
class Issue:
    level: str  # ERROR / WARN
    path: str
    msg: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.path}: {self.msg}"


def check_entry(kb: KB, e: Entry, today: dt.date | None = None) -> list[Issue]:
    today = today or dt.date.today()
    p = e.rel_path
    issues: list[Issue] = []

    def err(msg: str) -> None:
        issues.append(Issue("ERROR", p, msg))

    def warn(msg: str) -> None:
        issues.append(Issue("WARN", p, msg))

    if e.parse_error:
        err(e.parse_error)
        return issues
    if not e.meta:
        err("缺少 front-matter")
        return issues
    for f in REQUIRED_FIELDS:
        if f not in e.meta or e.meta[f] in ("", []):
            err(f"缺少必填字段 `{f}`")
    if not ID_RE.match(e.id):
        err(f"id `{e.id}` 不合规：只允许小写字母、数字和连字符（kebab-case）")
    if e.id != e.path.stem:
        err(f"id `{e.id}` 与文件名 `{e.path.stem}` 不一致")
    if kb.by_id.get(e.id) is not e:
        err(f"id `{e.id}` 重复（另见 {kb.by_id[e.id].rel_path}）")
    if e.domain not in DOMAINS:
        err(f"未知领域 `{e.domain}`（可选：{', '.join(DOMAINS)}）")
    elif e.path.parent.name != e.domain:
        err(f"领域 `{e.domain}` 与所在目录 `{e.path.parent.name}` 不一致")
    if e.kind not in KINDS:
        err(f"未知类型 `{e.kind}`（可选：{', '.join(KINDS)}）")
    if e.status not in STATUSES:
        err(f"未知成熟度 `{e.status}`（可选：{', '.join(STATUSES)}）")
    if e.confidence not in CONFIDENCE:
        err(f"未知置信度 `{e.confidence}`（可选：{', '.join(CONFIDENCE)}）")
    dates = {}
    for f in ("created", "updated", "review_after"):
        v = e.meta.get(f)
        if v in (None, "", []):
            continue
        if not isinstance(v, str) or not DATE_RE.match(v):
            err(f"`{f}` 日期格式应为 YYYY-MM-DD")
            continue
        try:
            dates[f] = dt.date.fromisoformat(v)
        except ValueError:
            err(f"`{f}` 不是合法日期：{v}")
    if "created" in dates and "updated" in dates and dates["updated"] < dates["created"]:
        err("`updated` 早于 `created`")
    if "review_after" in dates and dates["review_after"] < today:
        warn(f"已过复核日期 {e.meta['review_after']}，内容可能过时，请复核后更新 `review_after`")
    if len(e.summary) > SUMMARY_MAX:
        warn(f"summary 共 {len(e.summary)} 字，建议 ≤ {SUMMARY_MAX} 字（L0 登记簿要求一句话）")

    # 关系
    for r in e.relations:
        t, tgt = r.get("type", ""), r.get("target", "")
        if t not in RELATIONS:
            err(f"未知关系类型 `{t}`（可选：{', '.join(RELATIONS)}）")
        if not ID_RE.match(tgt or ""):
            err(f"关系目标 `{tgt}` 不是合法 id")
        if tgt == e.id:
            err("关系不能指向自己")
    raw_rel = e.meta.get("relations", [])
    if isinstance(raw_rel, list) and any(not isinstance(r, dict) for r in raw_rel):
        err("relations 每一项应写成 `- 关系类型: 目标id | 备注`")

    # 卡片
    if not e.card:
        err(f"缺少卡片区块 {CARD_START} … {CARD_END}")
    else:
        n = len([ln for ln in e.card.splitlines() if ln.strip()])
        if n > CARD_MAX_LINES:
            warn(f"卡片 {n} 行，超过 {CARD_MAX_LINES} 行上限（卡片是 L1 层，必须短）")
    if REL_START not in e.body or REL_END not in e.body:
        err(f"缺少关联区块 {REL_START} … {REL_END}（放在「关联」章节内）")

    # 章节
    headings = [s.heading for s in e.sections]
    need = list(DRAFT_SECTIONS)
    if e.status in ("standard", "deep"):
        need = REQUIRED_SECTIONS.get(e.kind, []) + COMMON_SECTIONS
    for kw in need:
        if not any(kw in h for h in headings):
            err(f"缺少必需章节（标题需包含「{kw}」）")

    # 来源
    defined = {s.key for s in e.sources}
    for ref in sorted(e.footnote_refs - defined):
        err(f"正文引用了未定义的来源 [^{ref}]")
    for key in sorted(defined - e.footnote_refs):
        warn(f"来源 [^{key}] 已定义但正文未引用")
    for s in e.sources:
        if not s.tier:
            err(f"来源 [^{s.key}] 缺少分级标注 **S1**/**S2**/**S3**")
        if not s.verify:
            err(f"来源 [^{s.key}] 缺少核实方式（核实：全文/摘要/转引）")
        if not re.search(r"https?://", s.text) and "ISBN" not in s.text:
            warn(f"来源 [^{s.key}] 没有可访问链接或 ISBN")
    nsrc, ns1 = len(e.sources), e.s1_count()
    floor = STATUS_FLOOR.get(e.status)
    if floor:
        if nsrc < floor["sources"]:
            err(f"成熟度 `{e.status}` 需要 ≥{floor['sources']} 个来源，当前 {nsrc}")
        if ns1 < floor["s1"]:
            err(f"成熟度 `{e.status}` 需要 ≥{floor['s1']} 个 S1 一手/权威来源，当前 {ns1}")
        if len(e.quiz) < floor["quiz"]:
            err(f"成熟度 `{e.status}` 需要 ≥{floor['quiz']} 道自测题，当前 {len(e.quiz)}")
    cfloor = CONFIDENCE_FLOOR.get(e.confidence)
    if cfloor:
        if nsrc < cfloor["sources"] or ns1 < cfloor["s1"]:
            err(
                f"置信度 `{e.confidence}` 需要 ≥{cfloor['sources']} 个来源且 ≥{cfloor['s1']} 个 S1，"
                f"当前 {nsrc} 个 / S1 {ns1} 个"
            )
    in_code = False
    for ln in e.body.splitlines():
        if ln.startswith("```"):
            in_code = not in_code
        elif in_code and FOOTNOTE_REF_RE.search(ln):
            warn(f"代码块中出现脚注引用（不会被渲染）：{ln.strip()[:40]}")
    pending_marks = len(PENDING_MARK_RE.findall(e.body))
    if pending_marks:
        warn(f"有 {pending_marks} 处【待核】论断")

    # 内部链接
    for link, _ in MD_LINK_RE.findall(e.body):
        if link.startswith(("http://", "https://")):
            continue
        if not (e.path.parent / link).resolve().exists():
            err(f"内部链接失效：{link}")
    return issues


def check_all(kb: KB, today: dt.date | None = None) -> list[Issue]:
    issues: list[Issue] = []
    for e in kb.entries:
        issues += check_entry(kb, e, today)
    alias_owner: dict[str, str] = {}
    for e in kb.entries:
        for name in [e.title, e.en, *e.aliases]:
            k = (name or "").strip().lower()
            if not k:
                continue
            if k in alias_owner and alias_owner[k] != e.id:
                issues.append(Issue("WARN", e.rel_path, f"名称/别名「{name}」与条目 `{alias_owner[k]}` 冲突，可能是重复条目"))
            alias_owner.setdefault(k, e.id)
    return issues


# ---------------------------------------------------------------------------
# 派生文件生成（输出必须确定：不含"生成时间"之类随时间变化的内容）
# ---------------------------------------------------------------------------

GEN_NOTE = "> ⚙️ 本文件由 `python3 tools/kb.py index` 自动生成，请勿手改。"


def gen_index_md(kb: KB) -> str:
    lines = [
        "# 📇 INDEX · 全库登记簿（L0 层）",
        "",
        GEN_NOTE,
        ">",
        "> **AI 检索第一站**：先在这里（或 `python3 tools/kb.py find <词>`）确认条目是否存在，",
        "> 再用 `kb.py card <id>` 读卡片（L1），需要细节时 `kb.py section <id> <章节>`（L2）。不要整库通读。",
        "",
        f"共 **{len(kb.entries)}** 个条目 · 待建前沿 **{len(kb.pending())}** 个（见 [graph/frontier.md](graph/frontier.md)）",
        "",
    ]
    for dom, (name, icon, scope) in DOMAINS.items():
        es = sorted([e for e in kb.entries if e.domain == dom], key=lambda e: e.id)
        if not es:
            continue
        lines += [f"## {icon} {name} · `{dom}`", "", "| 条目 | id | 一句话 | 类型 | 成熟度 | 置信 | 更新 |", "|---|---|---|---|---|---|---|"]
        for e in es:
            lines.append(
                f"| [{md_escape_cell(e.display())}]({e.rel_path}) | `{e.id}` | {md_escape_cell(e.summary)} "
                f"| {KINDS.get(e.kind, e.kind)} | {status_badge(e)} | {conf_badge(e)} | {e.updated} |"
            )
        lines.append("")
    empty = [f"{DOMAINS[d][1]} {DOMAINS[d][0]}" for d in DOMAINS if not any(e.domain == d for e in kb.entries)]
    if empty:
        lines += ["## 尚未收录的领域", "", "、".join(empty), ""]
    return "\n".join(lines)


def gen_graph_json(kb: KB) -> str:
    nodes = []
    for e in sorted(kb.entries, key=lambda e: e.id):
        nodes.append({
            "id": e.id, "title": e.title, "en": e.en, "aliases": e.aliases, "tags": e.tags,
            "kind": e.kind, "domain": e.domain, "status": e.status, "confidence": e.confidence,
            "summary": e.summary, "updated": e.updated, "path": e.rel_path,
            "sources": len(e.sources), "quiz": len(e.quiz),
        })
    for tgt in sorted(kb.pending()):
        nodes.append({"id": tgt, "title": tgt, "pending": True})
    edges = [{"source": s, "type": t, "target": tgt, "note": note} for s, t, tgt, note in kb.edges()]
    data = {
        "domains": {k: {"name": v[0], "icon": v[1], "scope": v[2]} for k, v in DOMAINS.items()},
        "kinds": KINDS,
        "relations": {k: {"label": v[0], "inverse": v[1]} for k, v in RELATIONS.items()},
        "nodes": nodes,
        "edges": edges,
    }
    return json.dumps(data, ensure_ascii=False, indent=1) + "\n"


def gen_frontier_md(kb: KB) -> str:
    pend = kb.pending()
    lines = [
        "# 🧭 研究前沿（Frontier）",
        "",
        GEN_NOTE,
        "",
        "知识库的生长方式：每写一个条目，它在 `relations` 里引用的、但还不存在的概念就会出现在这里。",
        "被引用次数越多，说明它越是现有知识的\"枢纽\"，越值得优先研究。",
        "",
        "## 1. 待建条目（按被引用次数排序）",
        "",
    ]
    if pend:
        lines += ["| 待建 id | 被引用 | 引用者（关系） |", "|---|---|---|"]
        for tgt, refs in sorted(pend.items(), key=lambda kv: (-len(kv[1]), kv[0])):
            who = "；".join(f"{kb.by_id[s].title}（{RELATIONS.get(t, (t,))[0]}）" for s, t in refs if s in kb.by_id)
            lines.append(f"| `{tgt}` | {len(refs)} | {who} |")
    else:
        lines.append("（暂无）")
    lines += ["", "## 2. 深度回填队列（草稿 → 标准 → 深度）", ""]
    drafts = [e for e in kb.entries if e.status != "deep"]
    if drafts:
        lines += ["| 条目 | 当前成熟度 | 来源数 | S1 | 自测题 | 【待核】 |", "|---|---|---|---|---|---|"]
        for e in sorted(drafts, key=lambda e: (list(STATUSES).index(e.status) if e.status in STATUSES else 9, e.id)):
            lines.append(
                f"| [{e.title}](../{e.rel_path}) | {status_badge(e)} | {len(e.sources)} | {e.s1_count()} "
                f"| {len(e.quiz)} | {len(PENDING_MARK_RE.findall(e.body))} |"
            )
    else:
        lines.append("（全部条目均已达到深度级）")
    lines += ["", "## 3. 复核计划（按 review_after 排序）", ""]
    rev = sorted([e for e in kb.entries if e.meta.get("review_after")], key=lambda e: str(e.meta["review_after"]))
    if rev:
        lines += ["| 条目 | 复核日期 | 原因 |", "|---|---|---|"]
        for e in rev:
            lines.append(f"| [{e.title}](../{e.rel_path}) | {e.meta['review_after']} | {e.meta.get('volatility', '时效性内容')} |")
        lines += ["", "> 到期检查：`python3 tools/kb.py due`"]
    else:
        lines.append("（暂无设置复核日期的条目）")
    lines.append("")
    return "\n".join(lines)


def _mermaid_id(i: int) -> str:
    return f"n{i}"


def gen_domain_auto(kb: KB, dom: str) -> str:
    es = sorted([e for e in kb.entries if e.domain == dom], key=lambda e: (e.kind, e.id))
    lines = []
    if not es:
        return "（本领域暂无条目。用 `python3 tools/kb.py new concept <id> --domain " + dom + " --title 名称` 创建第一个。）"
    readme = KB_DIR / dom / "README.md"
    for kind, kname in KINDS.items():
        ks = [e for e in es if e.kind == kind]
        if not ks:
            continue
        lines += [f"### {kname}", ""]
        for e in ks:
            lines.append(f"- [{e.display()}]({rel_link(readme, e.path)}) — {e.summary} `{status_badge(e)}`")
        lines.append("")
    # 局部关系图：本领域条目 + 一跳邻居
    ids: list[str] = [e.id for e in es]
    edges = [(s, t, tgt) for s, t, tgt, _ in kb.edges() if s in ids or tgt in ids]
    for s, _, tgt in edges:
        for x in (s, tgt):
            if x not in ids:
                ids.append(x)
    idx = {x: _mermaid_id(i) for i, x in enumerate(ids)}
    lines += ["### 关系图（本领域 + 一跳邻居）", "", "```mermaid", "graph LR"]
    for x in ids:
        e = kb.by_id.get(x)
        label = (e.title if e else x).replace('"', "'")
        if e and e.domain == dom:
            lines.append(f'  {idx[x]}["{label}"]:::here')
        elif e:
            lines.append(f'  {idx[x]}["{label}<br/><small>{DOMAINS.get(e.domain, ("",))[0]}</small>"]:::other')
        else:
            lines.append(f'  {idx[x]}["{label}<br/><small>待建</small>"]:::todo')
    for s, t, tgt in edges:
        arrow = "-.->" if tgt not in kb.by_id else "-->"
        lines.append(f"  {idx[s]} {arrow}|{RELATIONS.get(t, (t,))[0]}| {idx[tgt]}")
    lines += [
        "  classDef here fill:#e8f1ff,stroke:#2f6feb,stroke-width:2px;",
        "  classDef other fill:#eef9f0,stroke:#2da44e;",
        "  classDef todo fill:#fff8e5,stroke:#bf8700,stroke-dasharray: 4 3;",
        "```",
    ]
    return "\n".join(lines)


def domain_readme_skeleton(dom: str) -> str:
    name, icon, scope = DOMAINS[dom]
    return (
        f"# {icon} {name}（`{dom}`）\n\n"
        f"**范围**：{scope}\n\n"
        f"> 本页上半部分可手写领域导读；`AUTO` 区块由 `python3 tools/kb.py index` 自动维护。\n\n"
        f"## 条目\n\n{AUTO_START}\n{AUTO_END}\n"
    )


def gen_readme_stats(kb: KB) -> str:
    n = len(kb.entries)
    by_status = {s: sum(1 for e in kb.entries if e.status == s) for s in STATUSES}
    nsrc = sum(len(e.sources) for e in kb.entries)
    nquiz = sum(len(e.quiz) for e in kb.entries)
    lines = [
        f"- 条目 **{n}** 个（🌳深度 {by_status['deep']} · 🌿标准 {by_status['standard']} · 🌱草稿 {by_status['draft']}）",
        f"- 关系 **{len(kb.edges())}** 条 · 待建前沿 **{len(kb.pending())}** 个 · 已核实来源 **{nsrc}** 条 · 自测题 **{nquiz}** 道",
        "",
        "| 领域 | 条目数 |",
        "|---|---|",
    ]
    for dom, (name, icon, _) in DOMAINS.items():
        c = sum(1 for e in kb.entries if e.domain == dom)
        lines.append(f"| {icon} [{name}](kb/{dom}/README.md) | {c} |")
    recent = sorted(kb.entries, key=lambda e: (e.updated, e.id), reverse=True)[:8]
    if recent:
        lines += ["", "**最近更新**", ""]
        for e in recent:
            lines.append(f"- {e.updated} · [{e.display()}]({e.rel_path}) — {e.summary}")
    return "\n".join(lines)


def planned_outputs(kb: KB) -> dict[Path, str]:
    """计算全部派生文件的目标内容（不写盘）。"""
    out: dict[Path, str] = {}
    out[ROOT / "INDEX.md"] = gen_index_md(kb)
    out[GRAPH_DIR / "graph.json"] = gen_graph_json(kb)
    out[GRAPH_DIR / "frontier.md"] = gen_frontier_md(kb)
    for dom in DOMAINS:
        p = KB_DIR / dom / "README.md"
        cur = p.read_text(encoding="utf-8") if p.exists() else domain_readme_skeleton(dom)
        out[p] = replace_block(cur, AUTO_START, AUTO_END, gen_domain_auto(kb, dom))
    readme = ROOT / "README.md"
    if readme.exists():
        cur = readme.read_text(encoding="utf-8")
        if AUTO_START in cur:
            out[readme] = replace_block(cur, AUTO_START, AUTO_END, gen_readme_stats(kb))
    for e in kb.entries:
        if e.parse_error or REL_START not in e.body:
            continue
        cur = e.path.read_text(encoding="utf-8")
        out[e.path] = replace_block(cur, REL_START, REL_END, render_relations_block(kb, e))
    return out


def write_outputs(outputs: dict[Path, str]) -> list[Path]:
    changed = []
    for p, content in outputs.items():
        old = p.read_text(encoding="utf-8") if p.exists() else None
        if old != content:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            changed.append(p)
    return changed


def stale_outputs(outputs: dict[Path, str]) -> list[Path]:
    return [p for p, c in outputs.items() if not p.exists() or p.read_text(encoding="utf-8") != c]


# ---------------------------------------------------------------------------
# 按需加载（渐进式披露）的视图
# ---------------------------------------------------------------------------

def view_l0(kb: KB, eid: str) -> str:
    e = kb.by_id.get(eid)
    if not e:
        return f"`{eid}` 〔待建〕"
    return f"`{e.id}` {e.display()} — {e.summary} [{DOMAINS.get(e.domain, ('?',))[0]}·{status_badge(e)}·置信{conf_badge(e)}]"


def view_card(kb: KB, eid: str) -> str:
    e = require(kb, eid)
    head = (
        f"# {e.display()}  `{e.id}`\n"
        f"领域：{DOMAINS.get(e.domain, ('?',))[0]} ｜ 类型：{KINDS.get(e.kind, e.kind)} ｜ 成熟度：{status_badge(e)} ｜ "
        f"置信度：{conf_badge(e)} ｜ 来源 {len(e.sources)} 条 ｜ 更新 {e.updated} ｜ 文件：{e.rel_path}\n"
    )
    return head + "\n" + (e.card or "（无卡片）")


def view_outline(kb: KB, eid: str) -> str:
    e = require(kb, eid)
    lines = [f"# {e.display()} 目录（共 {len(e.body.splitlines())} 行）", ""]
    for i, s in enumerate(e.sections, start=1):
        lines.append(f"[{i}] {_strip_number(s.heading)}  （{len(s.text.splitlines())} 行）")
        for c in s.children:
            lines.append(f"      {c.heading}  （{len(c.text.splitlines())} 行）")
    lines += ["", f"按需加载：python3 tools/kb.py section {e.id} <序号 | 小节号如 3.2 | 标题关键词>"]
    return "\n".join(lines)


def _strip_number(heading: str) -> str:
    return re.sub(r"^\d+(?:\.\d+)?[.、]?\s*", "", heading)


def find_sections(e: Entry, selector: str) -> list[Section]:
    """序号（第几个 H2）→ 小节号（如 3.2，匹配 H3 标题前缀）→ 关键词（先 H2 后 H3）。"""
    sel = selector.strip()
    if sel.isdigit():
        i = int(sel)
        return [e.sections[i - 1]] if 1 <= i <= len(e.sections) else []
    subs = [c for s in e.sections for c in s.children]
    if re.fullmatch(r"\d+\.\d+", sel):
        return [c for c in subs if re.match(re.escape(sel) + r"(?!\d)", c.heading)]
    low = sel.lower()
    hits = [s for s in e.sections if low in s.heading.lower()]
    hits = hits or [c for c in subs if low in c.heading.lower()]
    if hits:
        return hits
    # 兜底：标题都不含关键词时，返回正文提到它最多的那个最小单元（小节优先）
    skip = ("来源", "关联", "自测", "变更记录", "我的思考")
    units = subs + [s for s in e.sections if not s.children and not any(k in s.heading for k in skip)]
    scored = sorted(((u.text.lower().count(low), u) for u in units), key=lambda x: -x[0])
    return [u for n, u in scored[:2] if n > 0]


def view_section(kb: KB, eid: str, selector: str) -> str:
    e = require(kb, eid)
    secs = find_sections(e, selector)
    if not secs:
        raise KBError(f"条目 `{eid}` 中没有匹配「{selector}」的章节；先用 outline 查看目录")
    text = "\n\n".join(s.text for s in secs)
    # 附上本段引用到的来源定义，保证"断章"也可溯源
    refs = sorted(set(FOOTNOTE_REF_RE.findall(text)))
    defs = {s.key: s.text for s in e.sources}
    if refs and not any(FOOTNOTE_DEF_RE.search(s.text) for s in secs):
        text += "\n\n---\n本段引用的来源：\n" + "\n".join(f"[^{r}]: {defs.get(r, '（未定义）')}" for r in refs)
    return text


def view_neighbors(kb: KB, eid: str, depth: int = 1) -> str:
    if eid not in kb.by_id:
        raise KBError(f"不存在条目 `{eid}`")
    rows = kb.neighbors(eid, depth)
    if not rows:
        return f"`{eid}` 暂无关联。"
    lines = [f"# `{eid}` 的邻居（深度 {depth}）", ""]
    for d, direction, t, nid, note in rows:
        label = RELATIONS.get(t, (t, t))[0 if direction == "out" else 1]
        arrow = "→" if direction == "out" else "←"
        note = f"（{note}）" if note else ""
        lines.append(f"- [{d}] {arrow} **{label}** {view_l0(kb, nid)}{note}")
    return "\n".join(lines)


def view_context(kb: KB, eid: str) -> str:
    """一次性给出"干净上下文包"：目标卡片 + 目录 + 一跳邻居的一句话。"""
    e = require(kb, eid)
    parts = [
        "<!-- 上下文包：只含 L1 卡片 + 目录 + 邻居 L0。需要细节再 section，需要邻居再 card。 -->",
        view_card(kb, eid),
        "",
        "## 目录",
        "\n".join(f"{i}. {s.heading}" for i, s in enumerate(e.sections, start=1)),
        "",
        "## 一跳邻居",
        view_neighbors(kb, eid, 1).split("\n", 2)[-1] if kb.neighbors(eid, 1) else "（无）",
    ]
    return "\n".join(parts)


def view_path(kb: KB, eid: str) -> str:
    require(kb, eid)
    order = kb.learning_path(eid)
    lines = [f"# 学习路径：{kb.by_id[eid].title}", "", "按顺序学习（沿 based-on 前置关系展开）：", ""]
    for i, x in enumerate(order, start=1):
        lines.append(f"{i}. {view_l0(kb, x)}")
    return "\n".join(lines)


def require(kb: KB, eid: str) -> Entry:
    e = kb.by_id.get(eid)
    if e is None:
        hits = kb.find(eid, 3)
        hint = "；你是不是要找：" + "、".join(h for _, h in hits) if hits else ""
        raise KBError(f"不存在条目 `{eid}`{hint}")
    return e


def due_entries(kb: KB, today: dt.date | None = None) -> list[Entry]:
    today = today or dt.date.today()
    out = []
    for e in kb.entries:
        v = e.meta.get("review_after")
        if isinstance(v, str) and DATE_RE.match(v) and dt.date.fromisoformat(v) <= today:
            out.append(e)
    return out
