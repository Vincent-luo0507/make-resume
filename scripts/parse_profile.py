"""Parse 个人信息总览.md into a structured dict. Lenient input, strict canonical output.

The overview page is the single entry point for the knowledge base. It carries
only *index-level* information:

  - basic (name/phone/email/school/major/degree/...)
  - academics (GPA/rank/courses/language certs/...)
  - project_index (list of {name, time_range, role, one_liner, detail_path})
  - student_work
  - skills
  - awards
  - other / extras
  - sensitive (bucket, not rendered on resume)

The *deep* content of each project lives in 项目档案/<name>.md and is NOT parsed
here — the Agent reads those files on demand during generate. That keeps this
parser simple and lets project pages preserve conflicts and rich context
without forcing them into a rigid schema.

Backward-compat: if the overview uses the old deep-list style (`## 核心经历`
with `### entries + tables + bullets`), we still parse it into the legacy
`experiences` key. New files should prefer the `## 核心经历索引` table form.
"""

import logging
import re
from pathlib import Path
from typing import Any

import mistune

from scripts.field_mapping import normalize_profile

log = logging.getLogger(__name__)

SECTION_MAP: dict[str, tuple[str, ...]] = {
    "basic":         ("基本档案", "基本信息", "个人档案", "基础资料", "basic", "profile"),
    "academics":     ("学业概览", "教育背景", "学习经历", "学历", "education", "academic"),
    "project_index": ("核心经历索引", "项目索引", "经历索引", "project index"),
    "experiences":   ("核心经历", "项目经历", "实习经历", "社团经历", "项目/实习经历", "experience"),
    "student_work":  ("学生工作", "校园角色", "校园经历", "学生干部"),
    "skills":        ("技能与知识结构", "技能", "能力", "skill"),
    "awards":        ("奖项与荣誉", "奖项", "荣誉", "获奖", "荣誉奖项", "award"),
    "other":         ("其他补充", "其他", "证书", "语言", "兴趣", "other"),
    "sensitive":     ("敏感信息", "仅个人留存"),
    "sources":       ("文件版本与来源说明", "来源", "版本说明", "sources"),
}

_KV_LINE = re.compile(r"^\s*[-*•]\s*([^:：]+)[:：]\s*(.+?)\s*$")

# Accepted column headers for the project index table.
# We try to recognise (name, time_range, role, one_liner, detail_path) in any
# order, by prefix-matching header text.
_INDEX_HEADER_MAP: dict[str, str] = {
    "项目": "name",
    "经历": "name",
    "名称": "name",
    "name": "name",
    "时间": "time_range",
    "起止": "time_range",
    "time": "time_range",
    "角色": "role",
    "职位": "role",
    "岗位": "role",
    "role": "role",
    "一句话产出": "one_liner",
    "一句话": "one_liner",
    "产出": "one_liner",
    "summary": "one_liner",
    "详情": "detail_path",
    "档案": "detail_path",
    "link": "detail_path",
    "detail": "detail_path",
}


def _match_section(heading_text: str) -> str | None:
    cleaned = re.sub(r"^[\d\.\s]+", "", heading_text).strip().lower()
    # Order matters: "核心经历索引" must win over "核心经历". SECTION_MAP dict
    # preserves insertion order so we check project_index before experiences.
    for key, syns in SECTION_MAP.items():
        for syn in syns:
            if syn.lower() in cleaned:
                return key
    return None


def parse_overview(md_path: Path, *, normalize: bool = True) -> dict[str, Any]:
    """Parse 个人信息总览.md.

    Args:
        md_path: Path to the overview markdown file.
        normalize: When True (default), basic/academics/experience-field keys
            are translated to English canonical form; original Chinese keys are
            kept as aliases so legacy templates still work.
    """
    text = md_path.read_text(encoding="utf-8")
    parser = mistune.create_markdown(renderer=None, plugins=["table"])
    tokens = parser(text)

    profile: dict[str, Any] = {
        "basic": {},
        "academics": {},
        "project_index": [],
        "experiences": [],
        "student_work": [],
        "skills": [],
        "awards": [],
        "other": [],
        "sensitive": {},
        "sources": [],
        "extras": {},
    }

    current_section: str | None = None
    current_unknown_heading: str | None = None
    current_experience: dict[str, Any] | None = None

    def _flush_experience():
        nonlocal current_experience
        if current_experience is not None:
            profile["experiences"].append(current_experience)
            current_experience = None

    for tok in tokens:
        ttype = tok["type"]

        if ttype == "heading":
            level = tok["attrs"]["level"]
            text_content = _inline_text(tok["children"])

            if level == 2:
                _flush_experience()
                matched = _match_section(text_content)
                if matched:
                    current_section = matched
                    current_unknown_heading = None
                else:
                    current_section = None
                    current_unknown_heading = text_content
                    profile["extras"].setdefault(text_content, [])
            elif level == 3 and current_section in ("experiences", "student_work"):
                _flush_experience()
                current_experience = {
                    "title": text_content,
                    "fields": {},
                    "bullets": [],
                    "_section": current_section,
                }

        elif ttype == "table":
            # Decide whether this is a kv table (2 cols, one-field-per-row) or a
            # multi-column list table (project_index, or a wide kv table whose
            # headers name the fields).
            if current_section == "project_index":
                profile["project_index"].extend(_parse_index_table(tok))
            elif current_section in ("basic", "academics", "sensitive"):
                for k, v in _parse_kv_table(tok):
                    if k and v:
                        profile[current_section][k] = v
            elif current_section in ("experiences", "student_work") and current_experience is not None:
                for k, v in _parse_kv_table(tok):
                    if k and v:
                        current_experience["fields"][k] = v

        elif ttype == "list":
            items = _parse_list(tok)
            if current_section in ("experiences", "student_work") and current_experience is not None:
                current_experience["bullets"].extend(items)
            elif current_section in ("basic", "academics", "sensitive"):
                for item in items:
                    m = _KV_LINE.match("- " + item)
                    if m:
                        k, v = m.group(1).strip(), m.group(2).strip()
                        if k and v:
                            profile[current_section][k] = v
            elif current_section in ("skills", "awards", "other", "sources", "student_work"):
                profile[current_section].extend(items)
            elif current_unknown_heading:
                profile["extras"].setdefault(current_unknown_heading, []).extend(items)

    _flush_experience()

    # Route student_work experience-like entries out of `experiences`.
    kept_exp: list[dict[str, Any]] = []
    for exp in profile["experiences"]:
        if exp.pop("_section", None) == "student_work":
            profile["student_work"].append({
                "title": exp["title"],
                "fields": exp["fields"],
                "bullets": exp["bullets"],
            })
        else:
            kept_exp.append(exp)
    profile["experiences"] = kept_exp

    if normalize:
        return normalize_profile(profile)
    return profile


# Backwards-compatible alias. Old code paths and tests may still call
# `parse_profile`; the function simply parses whatever overview-style or
# legacy 信息.md file you hand it.
parse_profile = parse_overview


def _inline_text(children: list[dict[str, Any]] | None) -> str:
    if not children:
        return ""
    parts = []
    for c in children:
        if c.get("type") == "text":
            parts.append(c.get("raw", ""))
        elif c.get("type") in ("codespan", "emphasis", "strong"):
            parts.append(_inline_text(c.get("children")) or c.get("raw", ""))
        elif c.get("type") == "link":
            # For a link, keep the visible text AND stash the URL inline as
            # "<text>|<url>" only if the caller wants it; here we return the
            # display text. URL is recovered separately by _parse_index_table.
            parts.append(_inline_text(c.get("children")))
    return "".join(parts)


def _link_url(children: list[dict[str, Any]] | None) -> str | None:
    """Return the first link URL inside an inline tree (percent-decoded), or None."""
    from urllib.parse import unquote
    if not children:
        return None
    for c in children:
        if c.get("type") == "link":
            attrs = c.get("attrs") or {}
            url = attrs.get("url") or c.get("link") or c.get("href")
            if url:
                return unquote(url)
        nested = _link_url(c.get("children"))
        if nested:
            return nested
    return None


def _table_rows(tok: dict[str, Any]):
    """Yield (header_cells, body_rows) as lists of cell-children-lists.

    mistune 3.x structure:
      table → [table_head, table_body]
      table_head.children = [table_cell, ...]
      table_body.children = [table_row, ...]; each row.children = [table_cell, ...]
    """
    header_cells: list[list[dict[str, Any]]] = []
    body_rows: list[list[list[dict[str, Any]]]] = []
    for group in tok.get("children", []):
        gt = group.get("type")
        if gt == "table_head":
            for cell in group.get("children", []):
                header_cells.append(cell.get("children", []))
        elif gt == "table_body":
            for row in group.get("children", []):
                body_rows.append([cell.get("children", []) for cell in row.get("children", [])])
    return header_cells, body_rows


def _parse_kv_table(tok: dict[str, Any]) -> list[tuple[str, str]]:
    """Parse a 2-column key-value table (the common 字段/值 form)."""
    header, body = _table_rows(tok)
    rows: list[tuple[str, str]] = []
    # Treat header as data if it isn't a 字段/值 filler row
    if len(header) >= 2:
        k = _inline_text(header[0]).strip()
        v = _inline_text(header[1]).strip()
        if k and k not in ("字段", "key", "Field", "结构化结果", "值", "content", ""):
            rows.append((k, v))
    for cells in body:
        if len(cells) >= 2:
            k = _inline_text(cells[0]).strip()
            v = _inline_text(cells[1]).strip()
            if k in ("字段", "key", "Field", ""):
                continue
            rows.append((k, v))
    return rows


def _parse_index_table(tok: dict[str, Any]) -> list[dict[str, Any]]:
    """Parse the 核心经历索引 table (multi-column list of projects)."""
    header, body = _table_rows(tok)
    if not header or not body:
        return []
    col_keys: list[str | None] = []
    for cell in header:
        h = _inline_text(cell).strip().lower()
        mapped: str | None = None
        for cn, en in _INDEX_HEADER_MAP.items():
            if cn.lower() in h:
                mapped = en
                break
        col_keys.append(mapped)

    out: list[dict[str, Any]] = []
    for cells in body:
        row: dict[str, Any] = {}
        for i, cell in enumerate(cells):
            if i >= len(col_keys) or col_keys[i] is None:
                continue
            key = col_keys[i]
            if key == "detail_path":
                url = _link_url(cell)
                row["detail_path"] = url or _inline_text(cell).strip()
            else:
                row[key] = _inline_text(cell).strip()
        if any(row.values()):
            out.append(row)
    return out


def _parse_list(tok: dict[str, Any]) -> list[str]:
    items: list[str] = []
    for child in tok.get("children", []):
        if child.get("type") == "list_item":
            text_parts = []
            for sub in child.get("children", []):
                if sub.get("type") == "block_text":
                    text_parts.append(_inline_text(sub.get("children")))
                elif sub.get("type") == "paragraph":
                    text_parts.append(_inline_text(sub.get("children")))
            combined = " ".join(t for t in text_parts if t).strip()
            if combined:
                items.append(combined)
    return items
