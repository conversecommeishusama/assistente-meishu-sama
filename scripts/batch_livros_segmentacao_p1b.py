#!/usr/bin/env python3
"""Batch P1b: bootstrap specs, audit, Q/A verify, comparativos — todo o acervo livros."""

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
from apply_manual_livros_segmentacao import Boundary, load_boundary_file, split_by_anchors  # noqa: E402
from audit_manual_livros_segmentacao import audit_file, write_audit_report  # noqa: E402
from bootstrap_manual_livros_segmentacao import build_spec, update_manifest  # noqa: E402
from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402
from livros_segmentacao_pairing import split_pt_chunks  # noqa: E402
from qa_dialogue_annotation import parse_qa_turns, qa_turn_counts, verify_qa_alignment  # noqa: E402
from split_livros_work_articles import process_file  # noqa: E402

MANUAL_DIR_NAME = "segmentacao_manual"
QA_PROFILES = frozenset({"gokowa_roku_qa", "gokowa_roku_ho", "ochishiji_roku", "mioshie_shu"})


def bootstrap_missing(wr: Path, manual_dir: Path, *, force: bool) -> list[str]:
    created: list[str] = []
    for jp_path in sorted((wr / "jp").glob("*.txt")):
        fn = jp_path.name
        pt_path = wr / "pt" / fn
        if not pt_path.is_file():
            continue
        spec_path = manual_dir / f"{fn}.json"
        if spec_path.is_file() and not force:
            continue
        result = process_file(jp_path, pt_path)
        spec = build_spec(result)
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        update_manifest(manual_dir, fn)
        created.append(fn)
    return created


def verify_file_qa(spec_path: Path, wr: Path) -> list[str]:
    spec = load_boundary_file(spec_path)
    profile = spec.get("profile", "")
    if profile not in QA_PROFILES:
        return []
    fn = spec["filename"]
    bounds = [Boundary.from_article(a) for a in spec["articles"]]
    jp_body = parse_article(split_file((wr / "jp" / fn).read_text(encoding="utf-8"))[1][0]).content
    pt_body = parse_article(split_file((wr / "pt" / fn).read_text(encoding="utf-8"))[1][0]).content
    jp_chunks = split_by_anchors(jp_body, [b.jp_anchor for b in bounds], label="JP")
    pt_chunks = split_pt_chunks(pt_body, jp_chunks, bounds, profile=profile)
    issues: list[str] = []
    for b, jp_c, pt_c in zip(bounds, jp_chunks, pt_chunks, strict=True):
        w = verify_qa_alignment(jp_c, pt_c, profile=profile)
        if w:
            issues.append(f"{b.title_jp}: {'; '.join(w)}")
    return issues


def run_compare(fn: str) -> bool:
    r = subprocess.run(
        [sys.executable, str(SCRIPTS / "build_manual_segmentacao_compare.py"), "--file", fn],
        cwd=str(SCRIPTS.parent),
        capture_output=True,
        text=True,
    )
    return r.returncode == 0


def main() -> int:
    p = argparse.ArgumentParser(description="Batch segmentação manual P1b — acervo livros")
    p.add_argument("--work-root", type=Path, default=None)
    p.add_argument("--bootstrap", action="store_true", help="Gera specs em falta")
    p.add_argument("--force-bootstrap", action="store_true")
    p.add_argument("--fix", action="store_true", help="Audit --fix em todos os specs")
    p.add_argument("--compare", action="store_true", help="Gera HTML comparativo")
    p.add_argument("--repair-pt", action="store_true", help="Repara PT Gosuiji conhecido")
    args = p.parse_args()

    wr = args.work_root or work_root("livros_acervo")
    manual_dir = wr / MANUAL_DIR_NAME
    manual_dir.mkdir(parents=True, exist_ok=True)

    if args.bootstrap or args.force_bootstrap:
        created = bootstrap_missing(wr, manual_dir, force=args.force_bootstrap)
        print(f"Bootstrap: {len(created)} specs criados/atualizados")

    if args.repair_pt:
        from repair_livros_pt_from_snapshot import repair_file, SNAPSHOT_PT  # noqa: E402

        snap = SNAPSHOT_PT
        restored = 0
        for pt_path in sorted((wr / "pt").glob("*.txt")):
            if repair_file(pt_path, snap, dry_run=False):
                restored += 1
        print(f"PT restore snapshot: {restored} ficheiros")

    specs = sorted(manual_dir.glob("*.txt.json"))
    specs = [s for s in specs if s.name != "AUDIT_REPORT.json"]

    results = []
    qa_failures: dict[str, list[str]] = {}
    compare_fail: list[str] = []

    for sp in specs:
        fn = json.loads(sp.read_text(encoding="utf-8"))["filename"]
        if args.fix or args.repair_pt:
            r = audit_file(sp, wr, fix=args.fix, repair_pt=args.repair_pt)
            results.append(r)
            ok = sum(1 for a in r.articles if a.status == "ok")
            fixed = sum(1 for a in r.articles if a.status == "anchor_fixed")
            warn = len(r.articles) - ok - fixed
            print(f"{r.filename}: {ok} ok, {fixed} fixed, {warn} warn/err")
        qa_issues = verify_file_qa(sp, wr)
        if qa_issues:
            qa_failures[fn] = qa_issues

        if args.compare:
            if not run_compare(fn):
                compare_fail.append(fn)

    if results:
        report = write_audit_report(manual_dir, results)
        print(report)

    summary = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "specs_total": len(specs),
        "qa_failures": {k: v for k, v in qa_failures.items()},
        "compare_failures": compare_fail,
        "qa_ok": len(specs) - len(qa_failures),
    }
    summary_path = manual_dir / "BATCH_SEGMENTACAO_REPORT.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(summary_path)
    print(f"Q/A OK: {summary['qa_ok']}/{len(specs)} · Q/A FAIL: {len(qa_failures)}")
    return 1 if qa_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
