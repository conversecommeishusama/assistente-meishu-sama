#!/usr/bin/env python3
"""Portuguese fluency pass: reduce calques and tighten prose without changing meaning."""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from apply_portuguese_grammar_pass import normalize_whitespace
from apply_safe_glossary_fixes import load_entries, pair_entries, permanent_pt_path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review"

# Conservative replacements: shorter or more natural PT, same denotation.
FLUENCY_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    # --- redundância factual ---
    ("redundancy", re.compile(r"\bvolta a retornar\b", flags=re.IGNORECASE), "volta"),
    ("redundancy", re.compile(r"\bretorna de volta\b", flags=re.IGNORECASE), "retorna"),
    ("redundancy", re.compile(r"\bsai para fora\b", flags=re.IGNORECASE), "sai"),
    ("redundancy", re.compile(r"\bentra para dentro\b", flags=re.IGNORECASE), "entra"),
    ("redundancy", re.compile(r"\bsubir para cima\b", flags=re.IGNORECASE), "subir"),
    ("redundancy", re.compile(r"\bdescer para baixo\b", flags=re.IGNORECASE), "descer"),
    ("redundancy", re.compile(r"\bantecipadamente antes\b", flags=re.IGNORECASE), "antes"),
    ("redundancy", re.compile(r"\bpreviamente antes\b", flags=re.IGNORECASE), "antes"),
    ("redundancy", re.compile(r"\batualmente hoje em dia\b", flags=re.IGNORECASE), "atualmente"),
    ("redundancy", re.compile(r"\bhoje em dia atualmente\b", flags=re.IGNORECASE), "hoje em dia"),
    ("redundancy", re.compile(r"\babsolutamente essencial\b", flags=re.IGNORECASE), "essencial"),
    ("redundancy", re.compile(r"\bcompletamente total\b", flags=re.IGNORECASE), "totalmente"),
    ("redundancy", re.compile(r"\btotalmente completo\b", flags=re.IGNORECASE), "completo"),
    ("redundancy", re.compile(r"\bé capaz de poder\b", flags=re.IGNORECASE), "pode"),
    ("redundancy", re.compile(r"\bpode ser capaz de\b", flags=re.IGNORECASE), "pode"),
    ("redundancy", re.compile(r"\brealiza a realização\b", flags=re.IGNORECASE), "realiza"),
    ("redundancy", re.compile(r"\bno entanto, no entanto\b", flags=re.IGNORECASE), "no entanto"),
    ("redundancy", re.compile(r"\bportanto, portanto\b", flags=re.IGNORECASE), "portanto"),
    ("redundancy", re.compile(r"\bou seja, ou seja\b", flags=re.IGNORECASE), "ou seja"),
    ("redundancy", re.compile(r"\bisto é, isto é\b", flags=re.IGNORECASE), "isto é"),
    ("redundancy", re.compile(r"\bmuito muito\b", flags=re.IGNORECASE), "muito"),
    ("redundancy", re.compile(r"\bmais mais\b", flags=re.IGNORECASE), "mais"),
    ("redundancy", re.compile(r"\btambém também\b", flags=re.IGNORECASE), "também"),
    # --- calques de construção ---
    ("calque", re.compile(r"\bdevido ao fato de que\b", flags=re.IGNORECASE), "porque"),
    ("calque", re.compile(r"\bem virtude do fato de que\b", flags=re.IGNORECASE), "porque"),
    ("calque", re.compile(r"\bpor causa do fato de que\b", flags=re.IGNORECASE), "porque"),
    ("calque", re.compile(r"\bpor motivo do fato de que\b", flags=re.IGNORECASE), "porque"),
    ("calque", re.compile(r"\bpor razão do fato de que\b", flags=re.IGNORECASE), "porque"),
    ("calque", re.compile(r"\bdevido ao fato de\b", flags=re.IGNORECASE), "devido a"),
    ("calque", re.compile(r"\bem virtude do fato de\b", flags=re.IGNORECASE), "em virtude de"),
    ("calque", re.compile(r"\bpor causa do fato de\b", flags=re.IGNORECASE), "por causa de"),
    ("calque", re.compile(r"\bExiste a possibilidade de\b"), "É possível"),
    ("calque", re.compile(r"\bHá a possibilidade de\b"), "É possível"),
    ("calque", re.compile(r"\bno instante em que\b", flags=re.IGNORECASE), "quando"),
    ("calque", re.compile(r"\bno momento em que\b", flags=re.IGNORECASE), "quando"),
    ("calque", re.compile(r"\bna ocasião em que\b", flags=re.IGNORECASE), "quando"),
    ("calque", re.compile(r"\bno que diz respeito a\b", flags=re.IGNORECASE), "quanto a"),
    ("calque", re.compile(r"\bno que se refere a\b", flags=re.IGNORECASE), "quanto a"),
    ("calque", re.compile(r"\bcom o objetivo de\b", flags=re.IGNORECASE), "para"),
    ("calque", re.compile(r"\bcom a finalidade de\b", flags=re.IGNORECASE), "para"),
    ("calque", re.compile(r"\bcom o propósito de\b", flags=re.IGNORECASE), "para"),
    ("calque", re.compile(r"\bde uma forma ou de outra\b", flags=re.IGNORECASE), "de um modo ou de outro"),
    ("calque", re.compile(r"\bde forma a a\b", flags=re.IGNORECASE), "de forma a"),
    ("calque", re.compile(r"\bde maneira a a\b", flags=re.IGNORECASE), "de maneira a"),
    ("calque", re.compile(r"\bem relação a a\b", flags=re.IGNORECASE), "em relação a"),
    # --- conectores pesados (mesmo sentido, leitura mais leve) ---
    ("connector", re.compile(r"\bé por essa razão que\b", flags=re.IGNORECASE), "por isso"),
    ("connector", re.compile(r"\bé por esse motivo que\b", flags=re.IGNORECASE), "por isso"),
    ("connector", re.compile(r"\bé por causa disso que\b", flags=re.IGNORECASE), "por isso"),
    ("connector", re.compile(r"\bé devido a isso que\b", flags=re.IGNORECASE), "por isso"),
    # --- artigos/pronomes soltos por calque (contextos fixos) ---
    ("article", re.compile(r"\bno estado de transe\b", flags=re.IGNORECASE), "em transe"),
    ("article", re.compile(r"\bno estado de vigília\b", flags=re.IGNORECASE), "em vigília"),
    ("article", re.compile(r"\bno estado de choque\b", flags=re.IGNORECASE), "em choque"),
    ("article", re.compile(r"\bno estado de sono\b", flags=re.IGNORECASE), "em sono"),
    ("article", re.compile(r"\bna direção de\b", flags=re.IGNORECASE), "em direção a"),
    # --- pontuação e espaços em travessões de diálogo ---
    ("punct", re.compile(r"([—–])\s{2,}"), r"\1 "),
)


@dataclass(frozen=True)
class Change:
    rule: str
    pattern: str
    replacement: str
    count: int


def apply_fluency(pt_text: str) -> tuple[str, list[Change]]:
    findings: list[Change] = []
    new_text = pt_text

    for rule_name, pattern, replacement in FLUENCY_RULES:
        updated, count = pattern.subn(replacement, new_text)
        if count:
            findings.append(Change(rule_name, pattern.pattern, replacement, count))
            new_text = updated

    new_text, ws_count = normalize_whitespace(new_text)
    if ws_count:
        findings.append(Change("whitespace", "[ \\t]{2,}", "single space", ws_count))

    return new_text, findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply Portuguese fluency fixes to all PT sources.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    planned = []
    for pair in pair_entries(load_entries()):
        pt_path = permanent_pt_path(pair.pt)
        pt_text = pt_path.read_text(encoding="utf-8")
        new_text, findings = apply_fluency(pt_text)
        if not findings or new_text == pt_text:
            continue
        planned.append({
            "pt_path": str(pt_path.relative_to(PROJECT_ROOT)),
            "title": pair.pt.get("title"),
            "findings": [{"rule": c.rule, "pattern": c.pattern, "replacement": c.replacement, "count": c.count} for c in findings],
            "_new_text": new_text,
        })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "portuguese_fluency_pass_batch.jsonl"
    with report_path.open("w", encoding="utf-8") as f:
        for row in planned:
            f.write(json.dumps({k: v for k, v in row.items() if not k.startswith("_")}, ensure_ascii=False) + "\n")

    backup_path = None
    if args.apply and planned:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"portuguese_fluency_pass_{ts}_before.tar.gz"
        with tarfile.open(backup_path, "w:gz") as tar:
            for row in planned:
                tar.add(PROJECT_ROOT / row["pt_path"], arcname=row["pt_path"])
        for row in planned:
            (PROJECT_ROOT / row["pt_path"]).write_text(row["_new_text"], encoding="utf-8")

    counts = Counter()
    for row in planned:
        for f in row["findings"]:
            counts[f["rule"]] += f["count"]
    print(f"mode={'apply' if args.apply else 'dry-run'} texts={len(planned)} replacements={sum(counts.values())}")
    print("rules=" + json.dumps(dict(counts), ensure_ascii=False, sort_keys=True))
    print(f"report={report_path}")
    if backup_path:
        print(f"backup={backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
