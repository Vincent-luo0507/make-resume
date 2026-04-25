"""Scan a project dir, compare to manifest, emit new/modified/deleted/renamed.

`scan_and_diff` stays pure (no side effects). The manifest refresh was
previously claimed in docs but never implemented — `commit_manifest` closes
that loop. Callers should:

    entries = read_manifest(resume_dir)
    diff    = scan_and_diff(root, entries)
    # ... user confirms the changes ...
    commit_manifest(resume_dir, build_snapshot(root))
"""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EXCLUDE_DIRS = {".resume", ".git", "__pycache__", ".venv", "node_modules"}
EXCLUDE_FILES = {".DS_Store", "Thumbs.db"}


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _walk(root: Path) -> list[Path]:
    out: list[Path] = []
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if any(part in EXCLUDE_DIRS for part in p.parts):
            continue
        if p.name in EXCLUDE_FILES:
            continue
        out.append(p)
    return out


def scan_and_diff(root: Path, manifest_entries: list[dict[str, Any]]) -> dict[str, list]:
    """Compare current tree to a manifest snapshot. Pure; no side effects."""
    old_by_path: dict[str, dict[str, Any]] = {e["path"]: e for e in manifest_entries}
    old_by_sha: dict[str, dict[str, Any]] = {e["sha256"]: e for e in manifest_entries}

    seen_paths: set[str] = set()
    new: list[dict[str, Any]] = []
    modified: list[dict[str, Any]] = []
    renamed: list[dict[str, Any]] = []

    for abs_path in _walk(root):
        rel = abs_path.relative_to(root).as_posix()
        seen_paths.add(rel)
        sha = _sha256(abs_path)
        mtime = datetime.fromtimestamp(abs_path.stat().st_mtime, tz=timezone.utc).isoformat()

        entry = {
            "schema_version": 1,
            "path": rel,
            "sha256": sha,
            "mtime": mtime,
            "section_id": None,
            "extracted_at": None,
            "status": "pending",
        }

        if rel in old_by_path:
            old = old_by_path[rel]
            if old["sha256"] != sha:
                modified.append(entry)
        elif sha in old_by_sha:
            old = old_by_sha[sha]
            renamed.append({
                "old_path": old["path"],
                "new_path": rel,
                "sha256": sha,
                "mtime": mtime,
            })
        else:
            new.append(entry)

    renamed_old_paths = {r["old_path"] for r in renamed}
    deleted = [
        e for e in manifest_entries
        if e["path"] not in seen_paths and e["path"] not in renamed_old_paths
    ]

    return {"new": new, "modified": modified, "deleted": deleted, "renamed": renamed}


def build_snapshot(root: Path) -> list[dict[str, Any]]:
    """Build a fresh manifest snapshot from the current filesystem tree.

    This is what should be written back after the user confirms the diff.
    Separating snapshot-taking from scan_and_diff keeps the side-effect
    explicit and skippable (e.g. user declined to sync — don't overwrite).
    """
    snapshot: list[dict[str, Any]] = []
    for abs_path in _walk(root):
        rel = abs_path.relative_to(root).as_posix()
        sha = _sha256(abs_path)
        mtime = datetime.fromtimestamp(abs_path.stat().st_mtime, tz=timezone.utc).isoformat()
        snapshot.append({
            "schema_version": 1,
            "path": rel,
            "sha256": sha,
            "mtime": mtime,
            "section_id": None,
            "extracted_at": None,
            "status": "synced",
        })
    return snapshot


def commit_manifest(resume_dir: Path, snapshot: list[dict[str, Any]]) -> None:
    """Write snapshot to .resume/manifest.jsonl. Call only after user accepts diff."""
    from scripts.state import write_manifest
    write_manifest(resume_dir, snapshot)
