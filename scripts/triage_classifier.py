"""Heuristic classification of user files into 3 triage categories.

Categories
----------
profile  : suspected structured-info main doc
           stem matches (信息|简历|个人|profile|resume) (case-insensitive)
           AND extension is .md or .markdown
template : resume template docx
           stem matches (模板|template) (case-insensitive)
           AND extension is .docx or .dotx
evidence : everything else
"""

import re
from pathlib import Path

from scripts.manifest_scan import EXCLUDE_DIRS

_PROFILE_RE = re.compile(r"(信息|简历|个人|profile|resume)", re.IGNORECASE)
_TEMPLATE_RE = re.compile(r"(模板|template)", re.IGNORECASE)

_PROFILE_EXTS = {".md", ".markdown"}
_TEMPLATE_EXTS = {".docx", ".dotx"}


def _is_excluded(path: Path, root: Path) -> bool:
    """Return True if any ancestor component (relative to root) is in EXCLUDE_DIRS."""
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    return any(part in EXCLUDE_DIRS for part in rel.parts)


def classify_all(root: Path) -> dict[str, list[Path]]:
    """Walk *root* and classify every file into profile / template / evidence.

    Returns
    -------
    dict with exactly three keys: "profile", "template", "evidence".
    Each value is a list of absolute Path objects (files only, no dirs).
    """
    result: dict[str, list[Path]] = {"profile": [], "template": [], "evidence": []}

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if _is_excluded(p, root):
            continue

        stem = p.stem
        ext = p.suffix.lower()

        if _PROFILE_RE.search(stem) and ext in _PROFILE_EXTS:
            result["profile"].append(p)
        elif _TEMPLATE_RE.search(stem) and ext in _TEMPLATE_EXTS:
            result["template"].append(p)
        else:
            result["evidence"].append(p)

    return result
