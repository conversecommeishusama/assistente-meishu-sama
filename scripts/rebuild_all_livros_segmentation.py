#!/usr/bin/env python3
"""Rebuild JP-first de todos os specs livros + relatório de realidade."""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import work_root  # noqa: E402
from bootstrap_manual_livros_segmentacao import update_manifest  # noqa: E402
from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402
from jp_line_split import split_jp_line_by_line  # noqa: E402

MANUAL_DIR_NAME = "segmentacao_manual"
REPORT_JSON = "SEGMENTACAO_REALIDADE_REPORT.json"
REPORT_HTML = "SEGMENTACAO_REALIDADE_REPORT.html"
PROGRESS_LOG = "PROGRESS.log"


def _jp_anchor(text: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if len(s) >= 8:
            return s[:120]
    return text.strip()[:120]


def boundaries_to_spec_articles(slices, method: str) -> list[dict]:
    return [
        {
            "kind": sl.kind,
            "title_jp": sl.title_jp.split(" — ")[-1][:120],
            "title_pt": "",
            "jp_anchor": _jp_anchor(sl.jp),
            "pt_anchor": "",
            "notes": method,
        }
        for sl in slices
    ]


def _log(manual_dir: Path, msg: str) -> None:
    line = f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} {msg}\n"
    with (manual_dir / PROGRESS_LOG).open("a", encoding="utf-8") as f:
        f.write(line)
    print(msg, flush=True)


def _load_old_count(spec_path: Path) -> int:
    if not spec_path.is_file():
        return 0
    try:
        return len(json.loads(spec_path.read_text(encoding="utf-8")).get("articles", []))
    except Exception:
        return 0


def rebuild_file(
    fn: str,
    wr: Path,
    manual_dir: Path,
    *,
    dry_run: bool = False,
) -> dict:
    jp_path = wr / "jp" / fn
    spec_path = manual_dir / f"{fn}.json"
    old_count = _load_old_count(spec_path)

    if not jp_path.is_file():
        return {"filename": fn, "status": "fail", "error": "jp_missing", "old_count": old_count}

    jp_text = jp_path.read_text(encoding="utf-8")
    _, blocks = split_file(jp_text)
    if not blocks:
        return {"filename": fn, "status": "fail", "error": "no_article_block", "old_count": old_count}
    jp_body = parse_article(blocks[0]).content
    book_title = parse_article(blocks[0]).fields.get("title_jp", fn)

    profile, slices, method = split_jp_line_by_line(jp_body, fn)
    new_count = len(slices)
    warnings: list[str] = []
    if new_count <= 1:
        warnings.append("line_scan: monolith_after_split")

    entry = {
        "filename": fn,
        "status": "ok",
        "profile": profile,
        "split_method": method,
        "old_count": old_count,
        "new_count": new_count,
        "delta": new_count - old_count,
        "was_monolith": old_count <= 1,
        "still_monolith": new_count <= 1,
        "warnings": warnings,
        "kinds": {},
    }
    for sl in slices:
        entry["kinds"][sl.kind] = entry["kinds"].get(sl.kind, 0) + 1

    if dry_run:
        return entry

    spec = {
        "filename": fn,
        "profile": profile,
        "method": "jp_line_by_line",
        "approved": False,
        "editor_notes": (
            f"Segmentação linha-a-linha JP {datetime.now(timezone.utc).strftime('%Y-%m-%d')}. "
            f"Trechos: {old_count}→{new_count}. PT pairing pendente."
        ),
        "segmentation_pass": "jp_line_v2",
        "previous_article_count": old_count,
        "split_method": method,
        "bootstrap_warnings": warnings,
        "articles": boundaries_to_spec_articles(slices, method),
        "audited_at": None,
        "audit_method": None,
    }
    spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    update_manifest(manual_dir, fn, status="jp_first_rebuilt")
    return entry


def write_html(report: dict, out_path: Path) -> None:
    files = report["files"]
    rows = []
    for f in sorted(files, key=lambda x: (-x.get("delta", 0), x["filename"])):
        kinds = ", ".join(f"{k}:{v}" for k, v in sorted(f.get("kinds", {}).items()))
        warn = "; ".join(f.get("warnings", [])[:2])
        cls = "mono" if f.get("still_monolith") else "multi"
        rows.append(
            f"<tr class='{cls}'>"
            f"<td>{html.escape(f['filename'])}</td>"
            f"<td>{html.escape(f.get('profile',''))}</td>"
            f"<td>{f.get('old_count',0)}</td>"
            f"<td>{f.get('new_count',0)}</td>"
            f"<td>{f.get('delta',0):+d}</td>"
            f"<td>{html.escape(kinds)}</td>"
            f"<td>{html.escape(warn)}</td>"
            f"</tr>"
        )

    doc = f"""<!DOCTYPE html>
<html lang="pt-BR"><head>
<meta charset="utf-8">
<title>Segmentação JP-first — realidade do acervo</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 1.5rem; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: left; vertical-align: top; }}
th {{ background: #f0f0f0; position: sticky; top: 0; }}
tr.mono {{ background: #fff5f5; }}
tr.multi {{ background: #f5fff5; }}
.summary {{ display: flex; gap: 2rem; flex-wrap: wrap; margin-bottom: 1rem; }}
.card {{ border: 1px solid #ddd; padding: 12px 16px; border-radius: 8px; min-width: 140px; }}
</style></head><body>
<h1>Segmentação JP-first — livros_acervo</h1>
<p>Gerado: {html.escape(report.get('generated_at',''))}</p>
<div class="summary">
  <div class="card"><strong>Ficheiros</strong><br>{report['summary']['files']}</div>
  <div class="card"><strong>Trechos (antes)</strong><br>{report['summary']['trechos_before']}</div>
  <div class="card"><strong>Trechos (depois)</strong><br>{report['summary']['trechos_after']}</div>
  <div class="card"><strong>Δ trechos</strong><br>{report['summary']['trechos_delta']:+d}</div>
  <div class="card"><strong>Ainda monólito</strong><br>{report['summary']['still_monolith']}</div>
  <div class="card"><strong>Expandidos (&gt;1→N)</strong><br>{report['summary']['expanded']}</div>
</div>
<table>
<thead><tr>
  <th>Ficheiro</th><th>Perfil</th><th>Antes</th><th>Depois</th><th>Δ</th><th>Tipos</th><th>Avisos</th>
</tr></thead>
<tbody>
{"".join(rows)}
</tbody></table>
</body></html>"""
    out_path.write_text(doc, encoding="utf-8")


def main() -> int:
    p = argparse.ArgumentParser(description="Rebuild segmentação JP-first — acervo livros")
    p.add_argument("--work-root", type=Path, default=None)
    p.add_argument("--file", action="append", help="Só estes ficheiros")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-html", action="store_true")
    args = p.parse_args()

    wr = args.work_root or work_root("livros_acervo")
    manual_dir = wr / MANUAL_DIR_NAME
    manual_dir.mkdir(parents=True, exist_ok=True)

    if args.file:
        filenames = args.file
    else:
        filenames = sorted(p.name for p in (wr / "jp").glob("*.txt"))

    results: list[dict] = []
    for fn in filenames:
        try:
            entry = rebuild_file(fn, wr, manual_dir, dry_run=args.dry_run)
            results.append(entry)
            if entry.get("status") == "ok":
                _log(
                    manual_dir,
                    f"OK [{fn}]: {entry['old_count']}→{entry['new_count']} trechos ({entry['profile']})",
                )
            else:
                _log(manual_dir, f"FAIL [{fn}]: {entry.get('error','?')}")
        except Exception as exc:
            results.append({"filename": fn, "status": "fail", "error": str(exc)[:200]})
            _log(manual_dir, f"FAIL [{fn}]: {exc}")

    ok = [r for r in results if r.get("status") == "ok"]
    trechos_before = sum(r.get("old_count", 0) for r in ok)
    trechos_after = sum(r.get("new_count", 0) for r in ok)
    still_mono = sum(1 for r in ok if r.get("still_monolith"))
    expanded = sum(1 for r in ok if r.get("old_count", 0) <= 1 and r.get("new_count", 0) > 1)

    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pass": "jp_first_v1",
        "dry_run": args.dry_run,
        "summary": {
            "files": len(results),
            "ok": len(ok),
            "fail": len(results) - len(ok),
            "trechos_before": trechos_before,
            "trechos_after": trechos_after,
            "trechos_delta": trechos_after - trechos_before,
            "still_monolith": still_mono,
            "expanded": expanded,
        },
        "files": results,
    }

    if not args.dry_run:
        (manual_dir / REPORT_JSON).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if not args.no_html:
            write_html(report, manual_dir / REPORT_HTML)

        progress = {
            "phase": "jp_first_segmentation",
            "completed_at": report["generated_at"],
            "summary": report["summary"],
        }
        (manual_dir / "YOLO_PROGRESS.json").write_text(
            json.dumps(progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if report["summary"]["fail"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
