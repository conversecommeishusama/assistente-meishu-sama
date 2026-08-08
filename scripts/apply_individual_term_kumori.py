#!/usr/bin/env python3
"""Individual glossary pass for 曇り (spiritual) -> nuvens espirituais."""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from apply_safe_glossary_fixes import load_entries, pair_entries, permanent_pt_path, read_entry_text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review"

SPIRITUAL_GATES = (
    "霊の曇り",
    "魂の曇り",
    "霊が曇",
    "霊界が曇",
    "霊体の曇",
    "曇りを取",
    "曇りを除",
    "曇りをなく",
    "曇りが",
    "曇っている",
    "曇らせ",
    "曇りの解消",
    "不純水素",
    "霊衣",
    "曇り相",
    "曇りで",
    "曇りです",
    "曇りな",
)

WEATHER_EXCLUDE = ("曇天", "天気が曇", "晴れたり曇", "レントゲン", "肺が大分曇", "肺.*曇")


@dataclass(frozen=True)
class Rule:
    name: str
    replacements: tuple[tuple[re.Pattern[str], str], ...]


def is_spiritual_kumori(jp: str) -> bool:
    if "曇り" not in jp:
        return False
    if any(x in jp for x in ("曇天", "天気が曇", "晴れたり曇")):
        if not any(g in jp for g in SPIRITUAL_GATES):
            return False
    if "レントゲン" in jp and "霊" not in jp.split("レントゲン")[0][-20:]:
        return False
    return any(g in jp for g in SPIRITUAL_GATES) or (
        "曇り" in jp and "霊" in jp and "曇天" not in jp
    )


RULES: tuple[Rule, ...] = (
    Rule(
        name="kumori_nevoa",
        replacements=(
            (re.compile(r"\bnévoa espiritual\b", flags=re.IGNORECASE), "nuvens espirituais"),
            (re.compile(r"\bnebulosidade espiritual\b", flags=re.IGNORECASE), "nuvens espirituais"),
            (re.compile(r"\bnebulosidade\b", flags=re.IGNORECASE), "nuvens espirituais"),
            (re.compile(r"\bturvação espiritual\b", flags=re.IGNORECASE), "nuvens espirituais"),
            (re.compile(r"\bobscuridade espiritual\b", flags=re.IGNORECASE), "nuvens espirituais"),
            (re.compile(r"\ba névoa espiritual\b", flags=re.IGNORECASE), "as nuvens espirituais"),
            (re.compile(r"\bo névoa espiritual\b", flags=re.IGNORECASE), "as nuvens espirituais"),
        ),
    ),
    Rule(
        name="kumori_grammar",
        replacements=(
            (re.compile(r"\ba nuvens espirituais\b", flags=re.IGNORECASE), "as nuvens espirituais"),
            (re.compile(r"\bo nuvens espirituais\b", flags=re.IGNORECASE), "as nuvens espirituais"),
            (re.compile(r"\bda nuvens espirituais\b", flags=re.IGNORECASE), "das nuvens espirituais"),
            (re.compile(r"\bdo nuvens espirituais\b", flags=re.IGNORECASE), "das nuvens espirituais"),
            (re.compile(r"\bna nuvens espirituais\b", flags=re.IGNORECASE), "nas nuvens espirituais"),
            (re.compile(r"\bno nuvens espirituais\b", flags=re.IGNORECASE), "nas nuvens espirituais"),
            (re.compile(r"\bessa nuvens espirituais\b", flags=re.IGNORECASE), "essas nuvens espirituais"),
            (re.compile(r"\besta nuvens espirituais\b", flags=re.IGNORECASE), "estas nuvens espirituais"),
            (re.compile(r"\bqual é a essência da nuvens espirituais\b", flags=re.IGNORECASE),
             "qual é a essência das nuvens espirituais"),
            (re.compile(r"\ba nuvens espirituais se torna\b", flags=re.IGNORECASE),
             "as nuvens espirituais se tornam"),
            (re.compile(r"\belimina a nuvem\b", flags=re.IGNORECASE), "elimina as nuvens espirituais"),
            (re.compile(r"\beliminar a nuvem\b", flags=re.IGNORECASE), "eliminar as nuvens espirituais"),
            (re.compile(r"\belimina a névoa\b", flags=re.IGNORECASE), "elimina as nuvens espirituais"),
            (re.compile(r"\beliminar a névoa\b", flags=re.IGNORECASE), "eliminar as nuvens espirituais"),
        ),
    ),
)


@dataclass(frozen=True)
class Change:
    rule: str
    pattern: str
    replacement: str
    count: int


def apply_kumori(pt_text: str, jp_text: str) -> tuple[str, list[Change]]:
    if not is_spiritual_kumori(jp_text):
        return pt_text, []
    findings: list[Change] = []
    new_text = pt_text
    for rule in RULES:
        for pattern, replacement in rule.replacements:
            updated, count = pattern.subn(replacement, new_text)
            if count:
                findings.append(Change(rule.name, pattern.pattern, replacement, count))
                new_text = updated
    return new_text, findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply individualized 曇り glossary fixes.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    planned = []
    for pair in pair_entries(load_entries()):
        jp = read_entry_text(pair.jp)
        pt_path = permanent_pt_path(pair.pt)
        pt_text = pt_path.read_text(encoding="utf-8")
        new_text, findings = apply_kumori(pt_text, jp)
        if not findings or new_text == pt_text:
            continue
        planned.append({
            "pt_path": str(pt_path.relative_to(PROJECT_ROOT)),
            "title": pair.pt.get("title"),
            "findings": [{"rule": c.rule, "pattern": c.pattern, "replacement": c.replacement, "count": c.count} for c in findings],
            "_new_text": new_text,
        })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "individual_kumori_batch.jsonl"
    with report_path.open("w", encoding="utf-8") as f:
        for row in planned:
            f.write(json.dumps({k: v for k, v in row.items() if not k.startswith("_")}, ensure_ascii=False) + "\n")

    backup_path = None
    if args.apply and planned:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"individual_kumori_batch_{ts}_before.tar.gz"
        with tarfile.open(backup_path, "w:gz") as tar:
            for row in planned:
                tar.add(PROJECT_ROOT / row["pt_path"], arcname=row["pt_path"])
        for row in planned:
            (PROJECT_ROOT / row["pt_path"]).write_text(row["_new_text"], encoding="utf-8")

    counts = Counter()
    for row in planned:
        for finding in row["findings"]:
            counts[finding["rule"]] += finding["count"]
    print(f"mode={'apply' if args.apply else 'dry-run'} texts={len(planned)} replacements={sum(counts.values())}")
    print("rules=" + json.dumps(dict(counts), ensure_ascii=False))
    if backup_path:
        print(f"backup={backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
