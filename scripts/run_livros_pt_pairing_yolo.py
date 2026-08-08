#!/usr/bin/env python3
"""YOLO — pareamento PT livro a livro (132), ajusta segmentação JP quando necessário."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import work_root  # noqa: E402
from audit_manual_livros_segmentacao import audit_file, write_audit_report  # noqa: E402
from rebuild_all_livros_segmentation import rebuild_file  # noqa: E402

MANUAL_DIR_NAME = "segmentacao_manual"
REPORT_NAME = "PAIRING_FINAL_REPORT.json"
PROGRESS_LOG = "PAIRING_PROGRESS.log"
EXCESSIVE_THRESHOLD = 400


def _log(manual_dir: Path, msg: str) -> None:
    line = f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} {msg}\n"
    with (manual_dir / PROGRESS_LOG).open("a", encoding="utf-8") as f:
        f.write(line)


def _load_order(wr: Path, manual_dir: Path) -> list[str]:
    queue_path = manual_dir / "YOLO_QUEUE.json"
    if queue_path.is_file():
        q = json.loads(queue_path.read_text(encoding="utf-8"))
        done = q.get("done") or []
        pending = q.get("pending") or []
        if done:
            return done + pending
    return sorted(p.name for p in (wr / "jp").glob("*.txt"))


def _needs_rebuild(fn: str, manual_dir: Path) -> bool:
    spec_path = manual_dir / f"{fn}.json"
    if not spec_path.is_file():
        return True
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    n = len(spec.get("articles") or [])
    if n >= EXCESSIVE_THRESHOLD and "山と水" in fn:
        return True
    if n >= EXCESSIVE_THRESHOLD and "笑の泉" in fn:
        return True
    if spec.get("segmentation_pass") != "jp_line_v2":
        return True
    return False


def _run_compare(fn: str) -> bool:
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "build_manual_segmentacao_compare.py"), "--file", fn],
        cwd=str(SCRIPTS.parent),
        capture_output=True,
        text=True,
    )
    return r.returncode == 0


def main() -> int:
    p = argparse.ArgumentParser(description="YOLO pareamento PT — acervo livros")
    p.add_argument("--work-root", type=Path, default=None)
    p.add_argument("--rebuild-all", action="store_true", help="Rebuild segmentação JP antes do pareamento")
    p.add_argument("--compare", action="store_true", help="Gera HTML comparativo por ficheiro")
    p.add_argument("--file", action="append", help="Só estes ficheiros")
    args = p.parse_args()

    wr = args.work_root or work_root("livros_acervo")
    manual_dir = wr / MANUAL_DIR_NAME
    manual_dir.mkdir(parents=True, exist_ok=True)

    if args.rebuild_all:
        subprocess.run(
            [sys.executable, str(SCRIPTS / "rebuild_all_livros_segmentation.py")],
            cwd=str(SCRIPTS.parent),
            check=False,
        )

    filenames = args.file or _load_order(wr, manual_dir)
    results: list[dict] = []
    audit_results = []

    for fn in filenames:
        entry: dict = {"filename": fn, "status": "ok"}
        try:
            if _needs_rebuild(fn, manual_dir):
                rb = rebuild_file(fn, wr, manual_dir)
                entry["rebuild"] = {
                    "old_count": rb.get("old_count"),
                    "new_count": rb.get("new_count"),
                    "profile": rb.get("profile"),
                }
                _log(manual_dir, f"REBUILD [{fn}]: {rb.get('old_count')}→{rb.get('new_count')}")

            spec_path = manual_dir / f"{fn}.json"
            if not spec_path.is_file():
                entry["status"] = "fail"
                entry["error"] = "spec_missing"
                results.append(entry)
                _log(manual_dir, f"FAIL [{fn}]: spec_missing")
                continue

            pt_path = wr / "pt" / fn
            if not pt_path.is_file():
                entry["status"] = "fail"
                entry["error"] = "pt_missing"
                results.append(entry)
                _log(manual_dir, f"FAIL [{fn}]: pt_missing")
                continue

            fa = audit_file(spec_path, wr, fix=True)
            audit_results.append(fa)

            ok = sum(1 for a in fa.articles if a.status in ("ok", "anchor_fixed", "ratio_warn", "anchor_diff"))
            warn = sum(1 for a in fa.articles if a.status not in ("ok", "anchor_fixed"))
            ratio_warn = sum(1 for a in fa.articles if a.status == "ratio_warn")
            err = sum(1 for a in fa.articles if a.status == "error")
            anchored = sum(1 for a in fa.articles if a.pt_anchor_new)

            entry["articles"] = len(fa.articles)
            entry["paired_ok"] = ok
            entry["paired_warn"] = warn
            entry["ratio_warn"] = ratio_warn
            entry["anchored"] = anchored
            entry["errors"] = fa.errors
            entry["profile"] = fa.profile

            if fa.errors or err:
                entry["status"] = "partial" if anchored else "fail"
            elif warn and not ok:
                entry["status"] = "partial"

            if args.compare:
                entry["compare_ok"] = _run_compare(fn)

            _log(
                manual_dir,
                f"OK [{fn}]: {len(fa.articles)} trechos, {ok} ok, {warn} warn, profile={fa.profile}",
            )
        except Exception as exc:
            entry["status"] = "fail"
            entry["error"] = str(exc)[:300]
            _log(manual_dir, f"FAIL [{fn}]: {exc}")

        results.append(entry)

    write_audit_report(manual_dir, audit_results)

    ok_files = sum(1 for r in results if r.get("status") == "ok")
    partial = sum(1 for r in results if r.get("status") == "partial")
    fail = sum(1 for r in results if r.get("status") == "fail")
    total_trechos = sum(r.get("articles", 0) for r in results)
    total_paired = sum(r.get("anchored", r.get("paired_ok", 0)) for r in results)

    report = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "phase": "pt_pairing_yolo",
        "summary": {
            "files": len(results),
            "ok": ok_files,
            "partial": partial,
            "fail": fail,
            "trechos_total": total_trechos,
            "trechos_paired_ok": total_paired,
        },
        "segmentation_fixes": [
            r for r in results if r.get("rebuild")
        ],
        "failures": [r for r in results if r.get("status") == "fail"],
        "partials": [r for r in results if r.get("status") == "partial"],
        "files": results,
    }
    (manual_dir / REPORT_NAME).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
