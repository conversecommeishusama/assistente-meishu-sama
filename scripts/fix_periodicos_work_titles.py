#!/usr/bin/env python3
"""Aplica TITLE_PT_OVERRIDES nos ficheiros periodicos_trabalho (sem reescrever estrutura JP)."""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
DEPLOY = Path("/var/www/goshinsho/scripts")
if DEPLOY.is_dir():
    sys.path.insert(0, str(DEPLOY))

from build_periodicos_work_files import TITLE_PT_OVERRIDES  # noqa: E402
from fix_periodicos_work_headers import process_pair  # noqa: E402
from repair_periodicos_work_separators import repair_text  # noqa: E402

from acervo_work_paths import work_root, article_sep as _article_sep  # noqa: E402

WORK_ROOT = work_root()
ENTRY_RE = re.compile(
    r"(=== ARTIGO ===\n)?(entry_id: (publication-jp-\d+)\n(?:.*?\n)*?title_pt: )([^\n]+)",
    re.S,
)


def sync_jp_title_fields_safe(jp_path: Path) -> list[dict]:
    text = jp_path.read_text(encoding="utf-8")
    changes: list[dict] = []

    def repl(match: re.Match[str]) -> str:
        entry_id = match.group(2)
        prefix = match.group(1) or ""
        head = match.group(3)
        old = match.group(4)
        new = TITLE_PT_OVERRIDES.get(entry_id)
        if not new or new == old:
            return match.group(0)
        changes.append({"entry_id": entry_id, "old": old, "new": new})
        block = match.group(0)
        block = block.replace(f"title_pt: {old}", f"title_pt: {new}", 1)
        block = re.sub(
            r"^Paired Portuguese title: .*$",
            f"Paired Portuguese title: {new}",
            block,
            count=1,
            flags=re.M,
        )
        return block

    new_text = ENTRY_RE.sub(repl, text)
    if changes:
        jp_path.write_text(new_text, encoding="utf-8")
    return changes


def main() -> int:
    for sub in ("jp", "pt"):
        for path in sorted((WORK_ROOT / sub).glob("*.txt")):
            text = path.read_text(encoding="utf-8")
            fixed, _ = repair_text(text)
            if fixed != text:
                path.write_text(fixed, encoding="utf-8")

    jp_changes: list[dict] = []
    for jp_file in sorted((WORK_ROOT / "jp").glob("*.txt")):
        jp_changes.extend(sync_jp_title_fields_safe(jp_file))
        pt_file = WORK_ROOT / "pt" / jp_file.name
        if pt_file.exists():
            process_pair(jp_file, pt_file)

    from fix_periodicos_work_paragraphs import main as reflow_main  # noqa: E402

    reflow_main()

    sys.path.insert(0, str(SCRIPTS))
    if DEPLOY.is_dir():
        sys.path.insert(0, str(DEPLOY))
    from audit_periodicos_titles_full import collect_rows, render_html, summarize  # noqa: E402

    rows = collect_rows()
    summary = summarize(rows)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    audit_path = WORK_ROOT / "TITULOS_AUDIT_FULL.json"
    html_path = WORK_ROOT / "TITULOS_AUDIT_FULL.html"
    audit_path.write_text(
        json.dumps({"timestamp": ts, **summary, "articles": rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    html_path.write_text(render_html(rows, summary, ts), encoding="utf-8")

    report = {
        "timestamp": ts,
        "jp_field_updates": len(jp_changes),
        "jp_changes": jp_changes,
        "post_audit": summary,
    }
    (WORK_ROOT / "TITULOS_FIX_REPORT.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    deploy = Path("/var/www/goshinsho/reports/periodicos_trabalho")
    if deploy.is_dir():
        import shutil

        for name in ("jp", "pt"):
            for f in (WORK_ROOT / name).glob("*.txt"):
                shutil.copy2(f, deploy / name / f.name)
        for name in (
            "TITULOS_FIX_REPORT.json",
            "TITULOS_AUDIT_FULL.json",
            "TITULOS_AUDIT_FULL.html",
            "TITLE_PT_OVERRIDES_AUDIT.json",
            "AMOSTRA_CONFERENCIA_JP_PT.html",
        ):
            src = WORK_ROOT / name
            if src.is_file():
                shutil.copy2(src, deploy / name)

    print(json.dumps({"jp_updates": len(jp_changes), "post_audit": summary}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
