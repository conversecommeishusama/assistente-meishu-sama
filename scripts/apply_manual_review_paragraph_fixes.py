#!/usr/bin/env python3
"""Paragraph-gated fixes for terms flagged in manual glossary review."""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from apply_individual_term_keirin import GRAMMAR_PATTERNS, PLANO_DIVINO_PATTERNS, SHUSHIN_PATTERNS
from apply_individual_term_kumori import RULES as KUMORI_RULES, is_spiritual_kumori
from apply_individual_term_taitai import RULES as TAITAI_RULES
from apply_safe_glossary_fixes import load_entries, pair_entries, permanent_pt_path, read_entry_text
from paragraph_glossary import apply_paragraph_gated


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review"

TERM_REPLACEMENTS: dict[str, tuple[tuple[re.Pattern[str], str], ...]] = {
    "御守護": (
        (re.compile(r"\bagradeça pela proteção divina até então\b", re.I), "agradeça pela proteção divina até então"),
        (re.compile(r"\bagradeça pela proteção até então\b", re.I), "agradeça pela proteção divina até então"),
        (re.compile(r"\bagradeça pela proteção\b(?! divina)", re.I), "agradeça pela proteção divina"),
        (re.compile(r"\bpeço sua proteção\b(?! divina)", re.I), "peço sua proteção divina"),
        (re.compile(r"\bpeço a sua proteção\b(?! divina)", re.I), "peço a sua proteção divina"),
        (re.compile(r"\breceber a proteção\b(?! divina)(?= de Meishu-Sama)", re.I), "receber a proteção divina"),
        (re.compile(r"\ba proteção\b(?! divina)(?= de Meishu-Sama)", re.I), "a proteção divina"),
        (re.compile(r"\bproteção dos deuses\b", re.I), "proteção divina"),
        (re.compile(r"\bproteção dos budas\b", re.I), "proteção divina"),
    ),
    "因縁": (
        (re.compile(r"\bconexão cármica profunda\b", re.I), "profunda inen (afinidade espiritual)"),
        (re.compile(r"\bconexão cármica\b", re.I), "innen (afinidade espiritual)"),
        (re.compile(r"\bcom quem tem afinidade come\b", re.I), "com quem tem inen (afinidade espiritual) come"),
    ),
    "毒血": (
        (re.compile(r"\bsangue venenoso\b", re.I), "sangue toxêmico (estado sanguíneo impuro)"),
        (re.compile(r"\bsangues venenosos\b", re.I), "sangue toxêmico (estado sanguíneo impuro)"),
    ),
    "光明如来": (
        (re.compile(r"\bDaikoumyou Nyorai\b"), "Komyo-Nyorai"),
        (re.compile(r"\bDaikōmyō Nyorai\b"), "Komyo-Nyorai"),
        (re.compile(r"\bBuda da Luz\b", re.I), "Komyo-Nyorai"),
    ),
    "光明如来様": (
        (re.compile(r"\bDaikoumyou Nyorai\b"), "Komyo-Nyorai"),
        (re.compile(r"\bDaikōmyō Nyorai\b"), "Komyo-Nyorai"),
    ),
    "実相": (
        (re.compile(r"\bA realidade é a verdade\b"), "A verdadeira forma é a verdade"),
        (re.compile(r"\ba realidade é a verdade\b", re.I), "a verdadeira forma é a verdade"),
    ),
    "言霊": (
        (re.compile(r"\bKotodama \(Kotodama \(espírito da palavra\)\)\b", re.I), "Kotodama (espírito da palavra)"),
        (re.compile(r"\bpalavra-espírito \(kotodama\)\b", re.I), "Kotodama (espírito da palavra)"),
        (re.compile(r"(?<!Kotodama \()\bespírito da palavra\b", re.I), "Kotodama (espírito da palavra)"),
        (re.compile(r"\bpalavras-espírito\b", re.I), "Kotodama (espírito da palavra)"),
    ),
    "御利益": (
        (re.compile(r"\bbenefício espiritual\b", re.I), "benefício material"),
        (re.compile(r"\bbenefícios espirituais\b", re.I), "benefícios materiais"),
    ),
    "霊体の曇": (
        (re.compile(r"\bnévoa do corpo espiritual\b", re.I), "nuvens do corpo espiritual"),
    ),
    "大本教": (
        (re.compile(r"\breligião Omoto\b", re.I), "religião Oomoto"),
        (re.compile(r"\bIgreja Omoto\b", re.I), "religião Oomoto"),
        (re.compile(r"\bseita Omoto\b", re.I), "religião Oomoto"),
    ),
}


def apply_term_rules(pt_para: str, jp_para: str, term: str) -> tuple[str, list[dict]]:
    findings: list[dict] = []
    new_para = pt_para

    for pattern, replacement in TERM_REPLACEMENTS.get(term, ()):
        updated, count = pattern.subn(replacement, new_para)
        if count:
            findings.append({"term": term, "pattern": pattern.pattern, "count": count})
            new_para = updated

    if term in ("経綸", "大経綸") and "経綸" in jp_para:
        for pattern, replacement in PLANO_DIVINO_PATTERNS + SHUSHIN_PATTERNS + GRAMMAR_PATTERNS:
            updated, count = pattern.subn(replacement, new_para)
            if count:
                findings.append({"term": "経綸", "pattern": pattern.pattern, "count": count})
                new_para = updated

    if term in ("体的", "体的に", "体的な", "体的文化") and "体的" in jp_para:
        for rule in TAITAI_RULES:
            if not any(g in jp_para for g in rule.japanese_gate):
                continue
            for pattern, replacement in rule.replacements:
                updated, count = pattern.subn(replacement, new_para)
                if count:
                    findings.append({"term": term, "rule": rule.name, "count": count})
                    new_para = updated

    if term in ("曇り", "曇る", "霊体の曇") and (
        is_spiritual_kumori(jp_para) or "霊体の曇" in jp_para
    ):
        for rule in KUMORI_RULES:
            for pattern, replacement in rule.replacements:
                updated, count = pattern.subn(replacement, new_para)
                if count:
                    findings.append({"term": term, "rule": rule.name, "count": count})
                    new_para = updated

    return new_para, findings


def run(*, apply: bool) -> dict[str, object]:
    pairs = pair_entries(load_entries())
    changed_files: dict[str, str] = {}
    findings: list[dict] = []
    term_counts: Counter[str] = Counter()

    for pair in pairs:
        pt_rel = str(permanent_pt_path(pair.pt).relative_to(PROJECT_ROOT))
        jp_text = read_entry_text(pair.jp)
        pt_path = PROJECT_ROOT / pt_rel
        pt_text = pt_path.read_text(encoding="utf-8")
        new_text = pt_text

        for term in TERM_REPLACEMENTS:
            if term not in jp_text:
                continue

            def _fn(pt_para: str, jp_para: str, t=term) -> tuple[str, list[dict]]:
                return apply_term_rules(pt_para, jp_para, t)

            updated, batch = apply_paragraph_gated(
                new_text, jp_text, japanese_term=term, apply_fn=_fn
            )
            if batch:
                new_text = updated
                findings.extend({"pt_path": pt_rel, **item} for item in batch)
                term_counts[term] += sum(item.get("count", 1) for item in batch)

        for term in ("経綸", "体的", "体的に", "体的な", "体的文化", "曇り", "曇る", "霊体の曇"):
            if term not in jp_text or term in TERM_REPLACEMENTS:
                continue

            def _fn(pt_para: str, jp_para: str, t=term) -> tuple[str, list[dict]]:
                return apply_term_rules(pt_para, jp_para, t)

            updated, batch = apply_paragraph_gated(
                new_text, jp_text, japanese_term=term, apply_fn=_fn
            )
            if batch:
                new_text = updated
                findings.extend({"pt_path": pt_rel, **item} for item in batch)
                term_counts[term] += sum(item.get("count", 1) for item in batch)

        if new_text != pt_text:
            changed_files[pt_rel] = new_text

    backup_path = None
    if apply and changed_files:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = DEFAULT_OUTPUT_DIR / f"manual_review_paragraph_fixes_{timestamp}_before.tar.gz"
        with tarfile.open(backup_path, "w:gz") as tar:
            for rel_path in changed_files:
                tar.add(PROJECT_ROOT / rel_path, arcname=rel_path)
        for rel_path, content in changed_files.items():
            (PROJECT_ROOT / rel_path).write_text(content, encoding="utf-8")

    return {
        "files_changed": len(changed_files),
        "substitutions": sum(term_counts.values()),
        "by_term": dict(term_counts),
        "backup": str(backup_path) if backup_path else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    result = run(apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
