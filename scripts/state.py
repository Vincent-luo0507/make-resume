"""Read/write .resume/ config files + workspace state validation.

`validate_workspace_state` is the single entry point the Skill calls at the
top of every invocation. It returns one of four workspace statuses, based on
cheap deterministic signals only (no LLM, no file content parsing):

    cold_start    — never initialized.
    incremental   — initialized AND manifest shows diff vs current tree.
    fast_generate — initialized AND manifest has no diff.
    recovery      — initialized but `overview_path` is gone or unreadable.

The main entry doc lives at ../../SKILL.md — this file is just the control
plane. All personal knowledge lives in Markdown (个人信息总览.md +
项目档案/*.md); state.json / preferences.yml / manifest.jsonl only carry
control-plane signals.
"""

import json
import logging
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger(__name__)

DEFAULT_STATE: dict[str, Any] = {
    "schema_version": 3,
    "phase": "uninitialized",
    "overview_path": None,         # relative path to 个人信息总览.md; None until init
    "initialized_at": None,
    "last_init_at": None,
    "last_update_at": None,
    "resume_count": 0,
}

DEFAULT_PREFERENCES: dict[str, Any] = {
    "schema_version": 1,
    "show_gender": True,
    "show_photo": False,
    "bilingual": False,
    "prefer_one_page": True,
    "exclude_experiences": [],
    "default_template": "classic-zh",
    "preferred_template": None,
    "template_asked": False,
}


def read_state(resume_dir: Path) -> dict[str, Any]:
    p = resume_dir / "state.json"
    if not p.exists():
        return dict(DEFAULT_STATE)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        merged = dict(DEFAULT_STATE)
        merged.update(data)
        return merged
    except (json.JSONDecodeError, OSError) as e:
        log.warning("state.json corrupt or unreadable (%s); resetting to defaults", e)
        return dict(DEFAULT_STATE)


def write_state(resume_dir: Path, state: dict[str, Any]) -> None:
    resume_dir.mkdir(parents=True, exist_ok=True)
    p = resume_dir / "state.json"
    p.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def read_preferences(resume_dir: Path) -> dict[str, Any]:
    p = resume_dir / "preferences.yml"
    if not p.exists():
        return dict(DEFAULT_PREFERENCES)
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return dict(DEFAULT_PREFERENCES)
        merged = dict(DEFAULT_PREFERENCES)
        merged.update(data)
        return merged
    except (yaml.YAMLError, OSError) as e:
        log.warning("preferences.yml unreadable (%s); using defaults", e)
        return dict(DEFAULT_PREFERENCES)


def write_preferences(resume_dir: Path, prefs: dict[str, Any]) -> None:
    resume_dir.mkdir(parents=True, exist_ok=True)
    p = resume_dir / "preferences.yml"
    p.write_text(yaml.safe_dump(prefs, allow_unicode=True, sort_keys=False), encoding="utf-8")


def read_manifest(resume_dir: Path) -> list[dict[str, Any]]:
    p = resume_dir / "manifest.jsonl"
    if not p.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            log.warning("skipping corrupt manifest line: %s", line[:80])
    return entries


def write_manifest(resume_dir: Path, entries: list[dict[str, Any]]) -> None:
    resume_dir.mkdir(parents=True, exist_ok=True)
    p = resume_dir / "manifest.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def read_triage(resume_dir: Path) -> dict[str, Any]:
    p = resume_dir / "triage.yml"
    if not p.exists():
        return {"schema_version": 1, "classifications": []}
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {"schema_version": 1, "classifications": []}
    except (yaml.YAMLError, OSError) as e:
        log.warning("triage.yml unreadable (%s); using empty", e)
        return {"schema_version": 1, "classifications": []}


def write_triage(resume_dir: Path, triage: dict[str, Any]) -> None:
    resume_dir.mkdir(parents=True, exist_ok=True)
    p = resume_dir / "triage.yml"
    p.write_text(yaml.safe_dump(triage, allow_unicode=True, sort_keys=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Workspace state validation — deterministic, cheap, no content parsing.
# ---------------------------------------------------------------------------

def validate_workspace_state(root: Path, resume_dir: Path | None = None) -> dict[str, Any]:
    """Classify current workspace for the Skill's top-level router.

    Returns:
      {
        "status": "cold_start" | "incremental" | "fast_generate" | "recovery",
        "reason": str,
        "state": dict,
        "overview_abs_path": Path|None,
        "diff": dict|None,
      }
    """
    from scripts.manifest_scan import scan_and_diff  # local import avoids cycle

    resume_dir = resume_dir or (root / ".resume")
    state = read_state(resume_dir)

    # 1. Never initialized.
    if not state.get("initialized_at"):
        return {
            "status": "cold_start",
            "reason": "workspace has never been initialized (no initialized_at)",
            "state": state,
            "overview_abs_path": None,
            "diff": None,
        }

    # 2. Initialized but overview is missing → recovery.
    overview_rel = state.get("overview_path")
    if not overview_rel:
        return {
            "status": "recovery",
            "reason": "state says initialized but overview_path is empty",
            "state": state,
            "overview_abs_path": None,
            "diff": None,
        }

    overview_abs = (root / overview_rel).resolve()
    if not overview_abs.exists() or not overview_abs.is_file():
        return {
            "status": "recovery",
            "reason": f"overview file missing at {overview_rel} — state points to nothing",
            "state": state,
            "overview_abs_path": None,
            "diff": None,
        }

    # 3. State is valid; compare manifest to current tree.
    entries = read_manifest(resume_dir)
    diff = scan_and_diff(root, entries)
    changed = bool(diff["new"] or diff["modified"] or diff["deleted"] or diff["renamed"])

    if changed:
        return {
            "status": "incremental",
            "reason": "file tree differs from last manifest",
            "state": state,
            "overview_abs_path": overview_abs,
            "diff": diff,
        }

    return {
        "status": "fast_generate",
        "reason": "state valid and no file changes since last run",
        "state": state,
        "overview_abs_path": overview_abs,
        "diff": diff,
    }
