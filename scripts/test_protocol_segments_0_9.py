#!/usr/bin/env python3
"""Teste protocolo A→D nos trechos 0–9 — pesquisa, retradução, persistência."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(PROJECT_ROOT))

from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402
from line_by_line_slices import invalidate_slice_cache, resplit_report  # noqa: E402
from acervo_studio_agent import process_segment, _load_spec, _read_jp_body, _read_pt_body  # noqa: E402
from goshinsho.services.acervo_studio_service import file_segment_statuses, workbench_segment  # noqa: E402

FILENAME = "19480101-御光話録（補）.txt"
WR = PROJECT_ROOT / "reports/livros_trabalho"


def _pt_size() -> int:
    return (WR / "pt" / FILENAME).stat().st_size


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Não gravar PT no disco (rollback automático no fim)",
    )
    ap.add_argument("--from", dest="from_seg", type=int, default=0, help="Trecho inicial (inclusivo)")
    ap.add_argument("--to", dest="to_seg", type=int, default=10, help="Trecho final (exclusivo)")
    args = ap.parse_args()

    spec = _load_spec(FILENAME)
    articles = spec.get("articles") or []
    seg_from = max(0, args.from_seg)
    seg_to = min(args.to_seg, len(articles))
    pt_path = WR / "pt" / FILENAME
    snapshot = pt_path.read_bytes() if args.dry_run else None
    size0 = _pt_size()
    rows: list[dict] = []

    mode = "dry-run" if args.dry_run else "persist"
    print(f"=== Teste protocolo trechos {seg_from}–{seg_to - 1} ({mode}) | PT inicial {size0} bytes ===\n")

    try:
        for i in range(seg_from, seg_to):
            title = articles[i].get("title_pt") or articles[i].get("title_jp") or str(i)
            invalidate_slice_cache(FILENAME)
            before = file_segment_statuses(FILENAME)["segments"][i]
            size_before = _pt_size()

            print(f"--- Trecho #{i} ({title[:40]}) status antes: {before['status']} ---")
            try:
                result = process_segment(FILENAME, i, translate=True, dry_run=args.dry_run)
            except Exception as exc:
                rows.append({"index": i, "title": title, "error": str(exc)})
                print(f"  ERRO: {exc}\n")
                continue

            invalidate_slice_cache(FILENAME)
            after = file_segment_statuses(FILENAME)["segments"][i]
            size_after = _pt_size()
            wb = workbench_segment(FILENAME, i)
            flagged = [t for t in wb["turns"] if t.get("flags")]

            row = {
                "index": i,
                "title": title,
                "blocking": result.get("blocking"),
                "translated": result.get("translated", 0),
                "corpus": result.get("corpus_fixes", 0),
                "status_after": after["status"],
                "flagged_units": len(flagged),
                "pt_file_delta": size_after - size_before,
                "issues": result.get("review_issues", [])[:4],
                "sample_flags": [
                    {
                        "line": t.get("jp_line"),
                        "kind": t.get("jp_kind"),
                        "flags": t.get("flags"),
                        "note": (t.get("editorial_note") or "")[:80],
                    }
                    for t in flagged[:3]
                ],
            }
            rows.append(row)
            print(
                f"  blocking={row['blocking']} | API={row['translated']} corpus={row['corpus']} | "
                f"status={row['status_after']} | flagged={row['flagged_units']} | "
                f"PT Δ={row['pt_file_delta']} | issues={row['issues']}"
            )
            if row["sample_flags"]:
                for sf in row["sample_flags"]:
                    print(f"    L{sf['line']} {sf['kind']}: {sf['note']}")
            print()
    finally:
        if snapshot is not None:
            pt_path.write_bytes(snapshot)
            invalidate_slice_cache(FILENAME)

    jp = _read_jp_body(FILENAME)
    pt = _read_pt_body(FILENAME)
    invalidate_slice_cache(FILENAME)
    slices = resplit_report(FILENAME, jp, pt, spec)
    summary = {
        "dry_run": args.dry_run,
        "segment_range": [seg_from, seg_to],
        "pt_size_start": size0,
        "pt_size_end": _pt_size(),
        "segments": rows,
        "slice_sizes": [
            {"i": s["index"], "jp": s["jp_chars"], "pt": s["pt_chars"]}
            for s in slices["segments"][seg_from:seg_to]
        ],
    }
    out_path = PROJECT_ROOT / "reports/acervo_studio/test_segments_0_9.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    n = len(rows)
    approved = sum(1 for r in rows if r.get("status_after") == "approved")
    fail = sum(1 for r in rows if r.get("status_after") == "fail")
    print(f"=== RESUMO: {approved}/{n} approved, {fail}/{n} fail, PT {size0} → {_pt_size()} ===")
    print(f"Relatório: {out_path}")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
