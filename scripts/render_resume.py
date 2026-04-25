"""Render a resume docx from a template + data dict.

Optionally convert to PDF via LibreOffice. Missing required fields are surfaced
via a preflight check *before* render — the old `_SilentUndefined` behaviour
is gone because it silently swallowed errors and produced blank-looking PDFs
that looked successful.

Templates that genuinely have optional fields still work: unreferenced items
simply aren't accessed; the jinja DebugUndefined only raises when the code
tries to iterate or convert an undefined value, which is the signal we want.
"""

import logging
import shutil
import subprocess
from pathlib import Path
from typing import Any

from docxtpl import DocxTemplate
from jinja2 import Environment, ChainableUndefined

log = logging.getLogger(__name__)


class _ReportingUndefined(ChainableUndefined):
    """Undefined that tolerates chained access but reports on coercion.

    - `{{ profile.missing.field }}` chains safely (ChainableUndefined).
    - `{{ undefined_var }}` renders as empty string but logs a warning.
    - `{% for x in undefined_list %}` raises, so missing loops aren't silent.
    """

    def __str__(self) -> str:
        name = self._undefined_name or "<unknown>"
        log.warning("template accessed undefined variable: %s", name)
        return ""

    def __bool__(self) -> bool:
        return False


def render(
    template_path: Path,
    data: dict[str, Any],
    out_docx: Path,
    *,
    preflight: bool = True,
) -> Path:
    """Render `data` into `template_path`, write to `out_docx`.

    If `preflight=True` (default), validate required fields first. Callers who
    need stricter checking should call `preflight.preflight_validate` directly
    and decide whether to proceed.
    """
    if preflight:
        from scripts.preflight import preflight_validate, parse_readme_required
        readme = template_path.parent / "README.md"
        fields, collections = parse_readme_required(readme)
        problems = preflight_validate(data, fields, collections)
        if problems:
            raise PreflightError(problems)

    tpl = DocxTemplate(str(template_path))
    jinja_env = Environment(undefined=_ReportingUndefined, autoescape=False)
    tpl.render(data, jinja_env=jinja_env)
    out_docx.parent.mkdir(parents=True, exist_ok=True)
    tpl.save(str(out_docx))
    return out_docx


class PreflightError(Exception):
    """Raised when required resume fields are missing before render.

    `problems` is a list of plain-language Chinese messages meant to be shown
    to the user verbatim — they already start with 「xxx」 style labels.
    """

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("\n".join(problems))


def _find_libreoffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    candidates = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def to_pdf(out_docx_path: Path) -> Path | None:
    """Convert docx to pdf via LibreOffice headless. Returns pdf path or None if unavailable."""
    soffice = _find_libreoffice()
    if not soffice:
        log.info("LibreOffice not found; skipping PDF conversion")
        return None
    out_dir = out_docx_path.parent
    try:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(out_dir), str(out_docx_path)],
            check=True,
            timeout=60,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        log.warning("LibreOffice PDF conversion failed: %s", e)
        return None
    pdf = out_docx_path.with_suffix(".pdf")
    return pdf if pdf.exists() else None


def render_from_stdin() -> None:
    """CLI entry: read JSON {template, data, out_docx, make_pdf, preflight} from stdin.

    Output JSON: {docx, pdf, preflight_problems}.
    If preflight fails, `docx` is null and `preflight_problems` is the list.
    """
    import json
    import sys
    cfg = json.loads(sys.stdin.read())
    result: dict[str, Any] = {"docx": None, "pdf": None, "preflight_problems": []}
    try:
        out = render(
            Path(cfg["template"]),
            cfg["data"],
            Path(cfg["out_docx"]),
            preflight=cfg.get("preflight", True),
        )
        result["docx"] = str(out)
        if cfg.get("make_pdf", True):
            pdf = to_pdf(out)
            result["pdf"] = str(pdf) if pdf else None
    except PreflightError as e:
        result["preflight_problems"] = e.problems
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    render_from_stdin()
