#!/usr/bin/env python3
"""Substitui 本教→nossa Igreja e 本療法/本医術→nossa terapia em todo o acervo PT."""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = PROJECT_ROOT / "reports" / "translation_review"

ARTICLE_SEP = "=== ARTIGO ==="

JP_MAKYO_ORG = re.compile(r"(?<!大)本教")
JP_KYUSEIKYO_ORG = re.compile(r"救世教|世界救世教")
JP_MAKYO_THERAPY = re.compile(r"本療法|本医術|日本医術")
JP_OSHIE_THERAPY = re.compile(r"御教え")

PT_ORG_PATTERNS = (
    (re.compile(r"\bDoutrina Absoluta\b"), "nossa Igreja"),
    (re.compile(r"\ba Doutrina Absoluta\b", re.I), "a nossa Igreja"),
    (re.compile(r"\bda Doutrina Absoluta\b", re.I), "da nossa Igreja"),
    (re.compile(r"\bna Doutrina Absoluta\b", re.I), "na nossa Igreja"),
    (re.compile(r"\bpela Doutrina Absoluta\b", re.I), "pela nossa Igreja"),
    (re.compile(r"\bpelo Doutrina Absoluta\b", re.I), "pela nossa Igreja"),
)

PT_THERAPY_PATTERNS = (
    (re.compile(r"\bTerapia Absoluta\b"), "nossa terapia"),
    (re.compile(r"\bterapia absoluta\b"), "nossa terapia"),
    (re.compile(r"\bTerapia absoluta\b"), "nossa terapia"),
    (re.compile(r"\ba Terapia Absoluta\b"), "nossa terapia"),
    (re.compile(r"\ba terapia absoluta\b"), "nossa terapia"),
    (re.compile(r"\bda Terapia Absoluta\b", re.I), "da nossa terapia"),
    (re.compile(r"\bda terapia absoluta\b", re.I), "da nossa terapia"),
    (re.compile(r"\bna Terapia Absoluta\b", re.I), "na nossa terapia"),
    (re.compile(r"\bna terapia absoluta\b", re.I), "na nossa terapia"),
    (re.compile(r"\bpela Terapia Absoluta\b", re.I), "pela nossa terapia"),
    (re.compile(r"\bpela terapia absoluta\b", re.I), "pela nossa terapia"),
    (re.compile(r"\bPrincípio da Terapia Absoluta\b"), "Princípio da nossa terapia"),
    (re.compile(r"\bprincípio da terapia absoluta\b"), "princípio da nossa terapia"),
)

PT_DA_AS_THERAPY_PATTERNS = (
    (re.compile(r"\bDoutrina Absoluta\b"), "nossa terapia"),
    (re.compile(r"\ba Doutrina Absoluta\b", re.I), "a nossa terapia"),
    (re.compile(r"\bda Doutrina Absoluta\b", re.I), "da nossa terapia"),
    (re.compile(r"\bna Doutrina Absoluta\b", re.I), "na nossa terapia"),
    (re.compile(r"\bpela Doutrina Absoluta\b", re.I), "pela nossa terapia"),
    (re.compile(r"\bpelo Doutrina Absoluta\b", re.I), "pela nossa terapia"),
)

PT_ROOTS = (
    PROJECT_ROOT / "textos_portugues",
    PROJECT_ROOT / "data" / "publication_sources" / "pt",
    PROJECT_ROOT / "reports" / "periodicos_trabalho" / "pt",
)


def slug_key(path: Path) -> str:
    name = path.name
    return re.sub(r"-publication-(?:jp|pt)-\d+\.txt$", "", name)


def apply_patterns(text: str, patterns: tuple) -> tuple[str, list[dict]]:
    findings: list[dict] = []
    for pattern, repl in patterns:
        text, n = pattern.subn(repl, text)
        if n:
            findings.append({"pattern": pattern.pattern, "replacement": repl, "count": n})
    return text, findings


def transform_pt(pt: str, jp: str) -> tuple[str, list[dict]]:
    findings: list[dict] = []
    new = pt
    has_makyo_org = bool(JP_MAKYO_ORG.search(jp))
    has_kyuseikyo = bool(JP_KYUSEIKYO_ORG.search(jp))
    has_makyo_therapy = bool(JP_MAKYO_THERAPY.search(jp))
    has_oshie = bool(JP_OSHIE_THERAPY.search(jp))
    has_org = has_makyo_org or has_kyuseikyo

    if has_makyo_therapy or has_oshie:
        new, f = apply_patterns(new, PT_THERAPY_PATTERNS)
        findings.extend({"rule": "makyo_therapy", **x} for x in f)
    if has_makyo_therapy and not has_org:
        new, f = apply_patterns(new, PT_DA_AS_THERAPY_PATTERNS)
        findings.extend({"rule": "makyo_da_as_therapy", **x} for x in f)
    if has_makyo_org:
        new, f = apply_patterns(new, PT_ORG_PATTERNS)
        findings.extend({"rule": "makyo_org", **x} for x in f)
    elif has_kyuseikyo:
        new, f = apply_patterns(new, PT_ORG_PATTERNS)
        findings.extend({"rule": "kyuseikyo_org", **x} for x in f)
    return new, findings


def jp_for_textos_portugues(pt_path: Path) -> Path | None:
    jp = PROJECT_ROOT / "textos_japones" / pt_path.name
    return jp if jp.exists() else None


def jp_for_publication_pt(pt_path: Path) -> Path | None:
    rel = pt_path.relative_to(PROJECT_ROOT / "data" / "publication_sources" / "pt")
    slug = slug_key(pt_path)
    jp_dir = PROJECT_ROOT / "data" / "publication_sources" / "jp" / rel.parent
    if not jp_dir.exists():
        return None
    for candidate in jp_dir.glob("*.txt"):
        if slug_key(candidate) == slug:
            return candidate
    return None


def jp_for_periodicos_pt(pt_path: Path) -> Path | None:
    jp = PROJECT_ROOT / "reports" / "periodicos_trabalho" / "jp" / pt_path.name
    return jp if jp.exists() else None


def resolve_jp(pt_path: Path) -> Path | None:
    parts = pt_path.as_posix()
    if "/textos_portugues/" in parts:
        return jp_for_textos_portugues(pt_path)
    if "/publication_sources/pt/" in parts:
        return jp_for_publication_pt(pt_path)
    if "/periodicos_trabalho/pt/" in parts:
        return jp_for_periodicos_pt(pt_path)
    return None


def process_simple_file(pt_path: Path) -> dict | None:
    jp_path = resolve_jp(pt_path)
    if not jp_path:
        return None
    pt_text = pt_path.read_text(encoding="utf-8")
    jp_text = jp_path.read_text(encoding="utf-8")
    new_text, findings = transform_pt(pt_text, jp_text)
    if not findings or new_text == pt_text:
        return None
    return {"pt_path": str(pt_path.relative_to(PROJECT_ROOT)), "findings": findings, "_new": new_text}


def process_periodicos_consolidated(pt_path: Path, jp_path: Path) -> dict | None:
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
            new_post, findings = transform_pt(post, jp_body)
            if findings:
                changed = True
                all_findings.extend(findings)
            out_blocks.append(pre + "---" + new_post)
        else:
            new_b, findings = transform_pt(pt_b, jp_body)
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


def collect_pt_files() -> list[Path]:
    files: list[Path] = []
    for root in PT_ROOTS:
        if root.exists():
            files.extend(sorted(root.rglob("*.txt")))
    return files


def update_glossary_files(apply: bool) -> dict:
    changes = {
        "末教": "nossa Igreja",
        "末療法": "nossa terapia",
        "末医術": "nossa terapia",
    }
    updated = []
    for name in ("glossario.json", "glossario_traducao.json"):
        path = PROJECT_ROOT / name
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        file_changes = {}
        for jp, pt in changes.items():
            if data.get(jp) != pt:
                file_changes[jp] = {"old": data.get(jp), "new": pt}
                if apply:
                    data[jp] = pt
        if file_changes and apply:
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if file_changes:
            updated.append({"file": name, "changes": file_changes})
    return {"glossary": updated}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Apply 末教/末療法 terminology across acervo PT.")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return p.parse_args()


def main() -> int:
    args = parse_args()
    glossary_result = update_glossary_files(args.apply)

    planned: list[dict] = []
    skipped_no_jp = 0
    for pt_path in collect_pt_files():
        jp_path = resolve_jp(pt_path)
        if not jp_path:
            skipped_no_jp += 1
            continue
        if "/periodicos_trabalho/pt/" in pt_path.as_posix():
            row = process_periodicos_consolidated(pt_path, jp_path)
        else:
            row = process_simple_file(pt_path)
        if row:
            planned.append(row)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "makyo_terminology_fixes.jsonl"
    with report_path.open("w", encoding="utf-8") as f:
        for row in planned:
            public = {k: v for k, v in row.items() if not k.startswith("_")}
            f.write(json.dumps(public, ensure_ascii=False) + "\n")

    backup_path = None
    if args.apply and planned:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"makyo_terminology_{ts}_before.tar.gz"
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
        "glossary": glossary_result,
        "report": str(report_path),
        "backup": str(backup_path) if backup_path else None,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
