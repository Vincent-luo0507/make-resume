"""Preflight: check resume data satisfies template requirements before render.

Replaces the old `_SilentUndefined` behaviour where missing fields silently
became empty strings. That failure mode made generated resumes look
successful while key information was actually blank.

Usage:
    missing = preflight_validate(resume_data, required_fields=DEFAULT_REQUIRED)
    if missing:
        # surface a plain-language report to the user; do NOT render silently
"""

from typing import Any

# Default minimum contract every Chinese student resume should satisfy.
# Templates can override by providing their own list (read from the template
# README "必需 profile 字段" section).
DEFAULT_REQUIRED_FIELDS: list[str] = [
    "profile.basic.name",
    "profile.basic.phone",
    "profile.basic.email",
    "profile.academics.school",
    "profile.academics.major",
    "profile.academics.degree",
]

DEFAULT_REQUIRED_COLLECTIONS: list[tuple[str, int]] = [
    ("profile.experiences", 1),
]


def _get_path(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            return None
    return cur


FIELD_LABELS: dict[str, str] = {
    "profile.basic.name": "姓名",
    "profile.basic.phone": "手机号",
    "profile.basic.email": "邮箱",
    "profile.basic.target_role": "意向岗位",
    "profile.academics.school": "学校",
    "profile.academics.major": "专业",
    "profile.academics.degree": "学历",
    "profile.academics.gpa": "GPA",
    "profile.experiences": "核心经历",
}


def preflight_validate(
    resume_data: dict[str, Any],
    required_fields: list[str] | None = None,
    required_collections: list[tuple[str, int]] | None = None,
) -> list[str]:
    """Return list of plain-language messages for any missing required items.

    Empty list = all checks pass.
    Non-empty list = surface each message to the user verbatim; do not render.

    `required_fields` — dotted paths that must be truthy (non-empty string).
    `required_collections` — (path, min_len) pairs; e.g. experiences ≥ 1.
    """
    fields = required_fields if required_fields is not None else DEFAULT_REQUIRED_FIELDS
    collections = required_collections if required_collections is not None else DEFAULT_REQUIRED_COLLECTIONS

    problems: list[str] = []

    for path in fields:
        val = _get_path(resume_data, path)
        if val is None or (isinstance(val, str) and not val.strip()):
            label = FIELD_LABELS.get(path, path.split(".")[-1])
            problems.append(f"缺少「{label}」—— 请在 个人信息总览.md 里补上再生成")

    for path, min_len in collections:
        val = _get_path(resume_data, path)
        if not isinstance(val, list) or len(val) < min_len:
            label = FIELD_LABELS.get(path, path.split(".")[-1])
            problems.append(
                f"「{label}」至少要有 {min_len} 条 —— 现在是 {len(val) if isinstance(val, list) else 0} 条"
            )

    return problems


def parse_readme_required(readme_path) -> tuple[list[str], list[tuple[str, int]]]:
    """Parse a template README.md and extract the '必需 profile 字段' section.

    Returns (fields, collections). Fields look like "basic.name"; we prepend
    "profile." for path lookup. Collections are detected via " (≥ N条)" suffix.

    Gracefully falls back to defaults if the README is missing or unparseable.
    """
    from pathlib import Path
    import re

    try:
        text = Path(readme_path).read_text(encoding="utf-8")
    except OSError:
        return DEFAULT_REQUIRED_FIELDS, DEFAULT_REQUIRED_COLLECTIONS

    # Look for a section header like "## 必需 profile 字段" or "## Required fields"
    section_re = re.compile(r"##\s*(必需\s*profile\s*字段|Required\s*fields)", re.IGNORECASE)
    m = section_re.search(text)
    if not m:
        return DEFAULT_REQUIRED_FIELDS, DEFAULT_REQUIRED_COLLECTIONS

    body = text[m.end():]
    # Stop at the next top-level section
    next_h = re.search(r"\n##\s", body)
    if next_h:
        body = body[:next_h.start()]

    fields: list[str] = []
    collections: list[tuple[str, int]] = []

    for line in body.splitlines():
        line = line.strip()
        if not line.startswith(("-", "*")):
            continue
        item = line.lstrip("-* ").strip()
        m_coll = re.search(r"（\s*至少\s*(\d+)\s*条\s*）|\(\s*>=\s*(\d+)\s*\)|\(\s*≥\s*(\d+)\s*\)", item)
        path = re.sub(r"[（\(].*", "", item).strip()
        if not path:
            continue
        full_path = path if path.startswith("profile.") else f"profile.{path}"
        if m_coll:
            n = int(next(g for g in m_coll.groups() if g))
            collections.append((full_path, n))
        else:
            fields.append(full_path)

    if not fields and not collections:
        return DEFAULT_REQUIRED_FIELDS, DEFAULT_REQUIRED_COLLECTIONS
    return fields, collections
