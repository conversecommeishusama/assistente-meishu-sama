#!/usr/bin/env python3
"""Fases C/D: Omoto (大本教) e substituição global do restante DA/TA."""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from apply_makyo_terminology_fixes import (
    ARTICLE_SEP,
    PT_ROOTS,
    PT_THERAPY_PATTERNS,
    apply_patterns,
    collect_pt_files,
    resolve_jp,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "translation_review"

JP_OMOTO = re.compile(r"大本教")

PT_GLOBAL_ORG_PATTERNS = (
    (re.compile(r"(?<!antiga )\bDoutrina Absoluta\b"), "nossa Igreja"),
    (re.compile(r"\ba Doutrina Absoluta\b", re.I), "a nossa Igreja"),
    (re.compile(r"\bda Doutrina Absoluta\b", re.I), "da nossa Igreja"),
    (re.compile(r"\bna Doutrina Absoluta\b", re.I), "na nossa Igreja"),
    (re.compile(r"\bpela Doutrina Absoluta\b", re.I), "pela nossa Igreja"),
    (re.compile(r"\bpelo Doutrina Absoluta\b", re.I), "pela nossa Igreja"),
)

PT_OMOTO_ANTIGA_PATTERNS = (
    (re.compile(r"\bantiga Doutrina Absoluta\b", re.I), "antiga Omoto"),
    (re.compile(r"\ba antiga Doutrina Absoluta\b", re.I), "a antiga Omoto"),
    (re.compile(r"\bda antiga Doutrina Absoluta\b", re.I), "da antiga Omoto"),
)

PT_REPAIR_OMOTO_PATTERNS = (
    (re.compile(r"\bantiga nossa Igreja\b", re.I), "antiga Omoto"),
    (re.compile(r"\ba antiga nossa Igreja\b", re.I), "a antiga Omoto"),
    (re.compile(r"\bda antiga nossa Igreja\b", re.I), "da antiga Omoto"),
)

PT_OMOTO_REST_PATTERNS = (
    (re.compile(r"\bDoutrina Absoluta\b"), "Omoto"),
    (re.compile(r"\ba Doutrina Absoluta\b", re.I), "a Omoto"),
    (re.compile(r"\bda Doutrina Absoluta\b", re.I), "da Omoto"),
    (re.compile(r"\bna Doutrina Absoluta\b", re.I), "na Omoto"),
    (re.compile(r"\bpela Doutrina Absoluta\b", re.I), "pela Omoto"),
    (re.compile(r"\bpelo Doutrina Absoluta\b", re.I), "pela Omoto"),
    (re.compile(r"\bdoutrina absoluta\b"), "Omoto"),
)

PT_OMOTO_THERAPY_PATTERNS = (
    (re.compile(r"\bTerapia Absoluta\b"), "nossa terapia"),
    (re.compile(r"\bterapia absoluta\b"), "nossa terapia"),
    (re.compile(r"\bPrincípio da Terapia Absoluta\b"), "Princípio da nossa terapia"),
)


def transform_phase_d(pt: str, jp: str, *, full: bool) -> tuple[str, list[dict]]:
    """Fase D: 大本教 → Omoto (completo se só Omoto; senão «antiga …»)."""
    if not JP_OMOTO.search(jp):
        return pt, []
    findings: list[dict] = []
    new, f = apply_patterns(pt, PT_OMOTO_ANTIGA_PATTERNS)
    findings.extend({"rule": "omoto_org", **x} for x in f)
    if full:
        new, f = apply_patterns(new, PT_OMOTO_REST_PATTERNS)
        findings.extend({"rule": "omoto_org", **x} for x in f)
        new, f = apply_patterns(new, PT_OMOTO_THERAPY_PATTERNS)
        findings.extend({"rule": "omoto_therapy", **x} for x in f)
    return new, findings


def transform_phase_c(pt: str) -> tuple[str, list[dict]]:
    """Fase C: substituição global do restante DA/TA."""
    findings: list[dict] = []
    new = pt
    new, f = apply_patterns(new, PT_REPAIR_OMOTO_PATTERNS)
    findings.extend({"rule": "omoto_repair", **x} for x in f)
    new, f = apply_patterns(new, PT_THERAPY_PATTERNS)
    findings.extend({"rule": "global_therapy", **x} for x in f)
    new, f = apply_patterns(new, PT_GLOBAL_ORG_PATTERNS)
    findings.extend({"rule": "global_org", **x} for x in f)
    return new, findings


def transform_pt_cd(pt: str, jp: str = "") -> tuple[str, list[dict]]:
    findings: list[dict] = []
    new = pt
    has_omoto = bool(jp and JP_OMOTO.search(jp))
    has_makyo = bool(jp and re.search(r"(?<!大)本教", jp))
    if has_omoto:
        new, f = transform_phase_d(new, jp, full=not has_makyo)
        findings.extend(f)
    new, f = transform_phase_c(new)
    findings.extend(f)
    return new, findings


def process_simple_file(pt_path: Path) -> dict | None:
    jp_path = resolve_jp(pt_path)
    pt_text = pt_path.read_text(encoding="utf-8")
    jp_text = jp_path.read_text(encoding="utf-8") if jp_path else ""
    new_text, findings = transform_pt_cd(pt_text, jp_text)
    if not findings or new_text == pt_text:
        return None
    return {
        "pt_path": str(pt_path.relative_to(PROJECT_ROOT)),
        "findings": findings,
        "_new": new_text,
    }


def process_periodicos_file(pt_path: Path, jp_path: Path) -> dict | None:
    pt_text = pt_path.read_text(encoding="utf-8")
    jp_text = jp_path.read_text(encoding="utf-8")
    if ARTICLE_SEP not in pt_text:
        return process_simple_file(pt_path)

    pt_parts = pt_text.split(ARTICLE_SEP)
    jp_parts = jp_text.split(ARTICLE_SEP)
    header = pt_parts[0]
    pt_blocks = pt_parts[1:]
    jp_blocks = jp_parts[1:] if len(jp_parts) > 1 else []
    if len(pt_blocks) != len(jp_blocks):
        return process_simple_file(pt_path)

    out_blocks: list[str] = []
    all_findings: list[dict] = []
    changed = False
    for pt_b, jp_b in zip(pt_blocks, jp_blocks):
        jp_body = jp_b.split("---", 1)[-1] if "---" in jp_b else jp_b
        if "---" in pt_b:
            pre, post = pt_b.split("---", 1)
            new_pre, findings_pre = transform_pt_cd(pre, jp_body)
            new_post, findings_post = transform_pt_cd(post, jp_body)
            if findings_pre or findings_post:
                changed = True
                all_findings.extend(findings_pre)
                all_findings.extend(findings_post)
            out_blocks.append((new_pre if findings_pre else pre) + "---" + new_post)
        else:
            new_b, findings = transform_pt_cd(pt_b, jp_body)
            if findings:
                changed = True
                all_findings.extend(findings)
            out_blocks.append(new_b)

    if not changed:
        return None
    new_text = header + ARTICLE_SEP + ARTICLE_SEP.join(out_blocks)
    return {
        "pt_path": str(pt_path.relative_to(PROJECT_ROOT)),
        "findings": all_findings,
        "_new": new_text,
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apply makyo terminology phases C and D.")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    planned: list[dict] = []
    skipped_no_jp = 0

    for pt_path in collect_pt_files():
        jp_path = resolve_jp(pt_path)
        if not jp_path:
            skipped_no_jp += 1
            row = process_simple_file(pt_path)
        elif "/periodicos_trabalho/pt/" in pt_path.as_posix():
            row = process_periodicos_file(pt_path, jp_path)
        else:
            row = process_simple_file(pt_path)
        if row:
            planned.append(row)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "makyo_terminology_phase_cd.jsonl"
    with report_path.open("w", encoding="utf-8") as f:
        for row in planned:
            public = {k: v for k, v in row.items() if not k.startswith("_")}
            f.write(json.dumps(public, ensure_ascii=False) + "\n")

    backup_path = None
    if args.apply and planned:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"makyo_terminology_phase_cd_{ts}_before.tar.gz"
        with tarfile.open(backup_path, "w:gz") as tar:
            for row in planned:
                tar.add(PROJECT_ROOT / row["pt_path"], arcname=row["pt_path"])
        for row in planned:
            (PROJECT_ROOT / row["pt_path"]).write_text(row["_new"], encoding="utf-8")

    rule_counts = Counter()
    for row in planned:
        for finding in row["findings"]:
            rule_counts[finding["rule"]] += finding["count"]

    summary = {
        "mode": "apply" if args.apply else "dry-run",
        "files_scanned": len(collect_pt_files()),
        "files_changed": len(planned),
        "skipped_no_jp": skipped_no_jp,
        "replacements": sum(rule_counts.values()),
        "rules": dict(rule_counts),
        "report": str(report_path),
        "backup": str(backup_path) if backup_path else None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
