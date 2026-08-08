#!/usr/bin/env python3
"""Portuguese grammar and fluency pass on permanent translated sources.

Fixes agreement, articles, prepositions, and obvious calque errors without
changing meaning. Literal sense is preserved; only grammatical correctness
and readability are adjusted.
"""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from apply_safe_glossary_fixes import load_entries, pair_entries, permanent_pt_path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review"

GRAMMAR_RULES: tuple[tuple[str, re.Pattern[str], str], ...] = (
    # --- Duplicações acidentais de lotes anteriores ---
    ("dup", re.compile(r"\bKotodama \(espírito da palavra\) \(espírito da palavra\)"), "Kotodama (espírito da palavra)"),
    ("dup", re.compile(r"\bKotodama \(espírito da palavra\) \(Kotodama"), "Kotodama (espírito da palavra)"),
    ("dup", re.compile(r"\btoxina medicamentosa medicamentosa\b", flags=re.IGNORECASE), "toxina medicamentosa"),
    ("dup", re.compile(r"\btoxinas medicamentosas medicamentosas\b", flags=re.IGNORECASE), "toxinas medicamentosas"),
    ("dup", re.compile(r"\bnuvens espirituais espirituais\b", flags=re.IGNORECASE), "nuvens espirituais"),
    ("dup", re.compile(r"\bPlano Divino Divino\b", flags=re.IGNORECASE), "Plano Divino"),
    ("dup", re.compile(r"\bMeishu-Sama-Sama\b"), "Meishu-Sama"),
    ("dup", re.compile(r"\bmétodo de método da agricultura natural\b", flags=re.IGNORECASE), "método da agricultura natural"),
    ("dup", re.compile(r"\bministrar Johrei ao ao\b", flags=re.IGNORECASE), "ministrar Johrei ao"),
    ("dup", re.compile(r"\bministrar Johrei ao a\b", flags=re.IGNORECASE), "ministrar Johrei ao"),
    ("dup", re.compile(r"\bde de\b"), "de"),
    ("dup", re.compile(r"\bda da\b"), "da"),
    ("dup", re.compile(r"\bdo do\b"), "do"),
    ("dup", re.compile(r"\bpara para\b"), "para"),
    ("dup", re.compile(r"\bque que\b"), "que"),
    ("dup", re.compile(r"\bproteção divina divina\b", flags=re.IGNORECASE), "proteção divina"),
    ("dup", re.compile(r"\bé é\b"), "é"),
    ("dup", re.compile(r"\bum um\b"), "um"),
    ("dup", re.compile(r"\buma uma\b"), "uma"),
    ("dup", re.compile(r"\bno no\b"), "no"),
    ("dup", re.compile(r"\bna na\b"), "na"),
    ("dup", re.compile(r",\s*,"), ","),
    ("dup", re.compile(r"\b!!+"), "!"),
    ("dup", re.compile(r"\?\?+"), "?"),
    ("dup", re.compile(r"\bPor favor, por favor\b", flags=re.IGNORECASE), "Por favor"),
    # --- Plano Divino ---
    ("plano_divino", re.compile(r"\bda Plano Divino\b", flags=re.IGNORECASE), "do Plano Divino"),
    ("plano_divino", re.compile(r"\bna Plano Divino\b", flags=re.IGNORECASE), "no Plano Divino"),
    ("plano_divino", re.compile(r"\ba Plano Divino\b", flags=re.IGNORECASE), "o Plano Divino"),
    ("plano_divino", re.compile(r"\bà Plano Divino\b", flags=re.IGNORECASE), "ao Plano Divino"),
    ("plano_divino", re.compile(r"\bpela Plano Divino\b", flags=re.IGNORECASE), "pelo Plano Divino"),
    ("plano_divino", re.compile(r"\bum Plano Divino\b", flags=re.IGNORECASE), "um Plano Divino"),
    ("plano_divino", re.compile(r"\buma Plano Divino\b", flags=re.IGNORECASE), "um Plano Divino"),
    # --- Johrei ---
    ("johrei", re.compile(r"\bà Johrei\b", flags=re.IGNORECASE), "ao Johrei"),
    ("johrei", re.compile(r"\bda Johrei\b", flags=re.IGNORECASE), "do Johrei"),
    ("johrei", re.compile(r"\bna Johrei\b", flags=re.IGNORECASE), "no Johrei"),
    ("johrei", re.compile(r"\bA Johrei\b"), "O Johrei"),
    ("johrei", re.compile(r"\ba Johrei\b", flags=re.IGNORECASE), "o Johrei"),
    ("johrei", re.compile(r"\bministrar Johrei o\b", flags=re.IGNORECASE), "ministrar Johrei ao"),
    ("johrei", re.compile(r"\bministrar Johrei a sangue\b", flags=re.IGNORECASE), "ministrar Johrei ao sangue"),
    ("johrei", re.compile(r"\bministrar Johrei o corpo\b", flags=re.IGNORECASE), "ministrar Johrei ao corpo"),
    ("johrei", re.compile(r"\bministrar Johrei a olhos\b", flags=re.IGNORECASE), "ministrar Johrei aos olhos"),
    ("johrei", re.compile(r"\bministrar Johrei a cabeça\b", flags=re.IGNORECASE), "ministrar Johrei à cabeça"),
    # --- toxina medicamentosa ---
    ("yakudoku", re.compile(r"\bo toxina medicamentosa\b", flags=re.IGNORECASE), "a toxina medicamentosa"),
    ("yakudoku", re.compile(r"\bdo toxina medicamentosa\b", flags=re.IGNORECASE), "da toxina medicamentosa"),
    ("yakudoku", re.compile(r"\bno toxina medicamentosa\b", flags=re.IGNORECASE), "na toxina medicamentosa"),
    ("yakudoku", re.compile(r"\bum toxina medicamentosa\b", flags=re.IGNORECASE), "uma toxina medicamentosa"),
    ("yakudoku", re.compile(r"\bos toxinas medicamentosas\b", flags=re.IGNORECASE), "as toxinas medicamentosas"),
    ("yakudoku", re.compile(r"\bdos toxinas medicamentosas\b", flags=re.IGNORECASE), "das toxinas medicamentosas"),
    ("yakudoku", re.compile(r"\bnos toxinas medicamentosas\b", flags=re.IGNORECASE), "nas toxinas medicamentosas"),
    ("yakudoku", re.compile(r"\buns toxinas medicamentosas\b", flags=re.IGNORECASE), "umas toxinas medicamentosas"),
    ("yakudoku", re.compile(r"\btoxina medicamentosa comuns\b", flags=re.IGNORECASE), "toxinas medicamentosas comuns"),
    ("yakudoku", re.compile(r"\btoxina medicamentosa dispersos\b", flags=re.IGNORECASE), "toxinas medicamentosas dispersas"),
    # --- nuvens espirituais: artigos ---
    ("nuvens", re.compile(r"\ba nuvens espirituais\b", flags=re.IGNORECASE), "as nuvens espirituais"),
    ("nuvens", re.compile(r"\bo nuvens espirituais\b", flags=re.IGNORECASE), "as nuvens espirituais"),
    ("nuvens", re.compile(r"\bum nuvens espirituais\b", flags=re.IGNORECASE), "as nuvens espirituais"),
    ("nuvens", re.compile(r"\buma nuvens espirituais\b", flags=re.IGNORECASE), "as nuvens espirituais"),
    ("nuvens", re.compile(r"\bda nuvens espirituais\b", flags=re.IGNORECASE), "das nuvens espirituais"),
    ("nuvens", re.compile(r"\bdo nuvens espirituais\b", flags=re.IGNORECASE), "das nuvens espirituais"),
    ("nuvens", re.compile(r"\bna nuvens espirituais\b", flags=re.IGNORECASE), "nas nuvens espirituais"),
    ("nuvens", re.compile(r"\bno nuvens espirituais\b", flags=re.IGNORECASE), "nas nuvens espirituais"),
    ("nuvens", re.compile(r"\bessa nuvens espirituais\b", flags=re.IGNORECASE), "essas nuvens espirituais"),
    ("nuvens", re.compile(r"\besta nuvens espirituais\b", flags=re.IGNORECASE), "estas nuvens espirituais"),
    ("nuvens", re.compile(r"\bessa nuvens\b", flags=re.IGNORECASE), "essas nuvens espirituais"),
    ("nuvens", re.compile(r"\besta nuvens\b", flags=re.IGNORECASE), "estas nuvens espirituais"),
    ("nuvens", re.compile(r"\bqual é a essência da nuvens espirituais\b", flags=re.IGNORECASE),
     "qual é a essência das nuvens espirituais"),
    ("nuvens", re.compile(r"\belimina a nuvens espirituais\b", flags=re.IGNORECASE), "elimina as nuvens espirituais"),
    ("nuvens", re.compile(r"\beliminar a nuvens espirituais\b", flags=re.IGNORECASE), "eliminar as nuvens espirituais"),
    ("nuvens", re.compile(r"\bexcreta a nuvens espirituais\b", flags=re.IGNORECASE), "excreta as nuvens espirituais"),
    ("nuvens", re.compile(r"\bexcretar a nuvens espirituais\b", flags=re.IGNORECASE), "excretar as nuvens espirituais"),
    # --- nuvens espirituais: concordância verbal (sujeito plural) ---
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais é removida\b", flags=re.IGNORECASE), "as nuvens espirituais são removidas"),
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais foi removida\b", flags=re.IGNORECASE), "as nuvens espirituais foram removidas"),
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais era intensa\b", flags=re.IGNORECASE), "as nuvens espirituais eram intensas"),
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais é\b", flags=re.IGNORECASE), "as nuvens espirituais são"),
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais foi\b", flags=re.IGNORECASE), "as nuvens espirituais foram"),
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais era\b", flags=re.IGNORECASE), "as nuvens espirituais eram"),
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais vai\b", flags=re.IGNORECASE), "as nuvens espirituais vão"),
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais se torna\b", flags=re.IGNORECASE), "as nuvens espirituais se tornam"),
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais se dissipa\b", flags=re.IGNORECASE), "as nuvens espirituais se dissipam"),
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais desaparece\b", flags=re.IGNORECASE), "as nuvens espirituais desaparecem"),
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais aparece\b", flags=re.IGNORECASE), "as nuvens espirituais aparecem"),
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais tem\b", flags=re.IGNORECASE), "as nuvens espirituais têm"),
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais pode\b", flags=re.IGNORECASE), "as nuvens espirituais podem"),
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais deve\b", flags=re.IGNORECASE), "as nuvens espirituais devem"),
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais permanece\b", flags=re.IGNORECASE), "as nuvens espirituais permanecem"),
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais continua\b", flags=re.IGNORECASE), "as nuvens espirituais continuam"),
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais se forma\b", flags=re.IGNORECASE), "as nuvens espirituais se formam"),
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais se acumula\b", flags=re.IGNORECASE), "as nuvens espirituais se acumulam"),
    # --- Imagem da Luz Divina ---
    ("goshintai", re.compile(r"\bao Imagem da Luz Divina\b", flags=re.IGNORECASE), "à Imagem da Luz Divina"),
    ("goshintai", re.compile(r"\bo Imagem da Luz Divina\b", flags=re.IGNORECASE), "a Imagem da Luz Divina"),
    ("goshintai", re.compile(r"\bum Imagem da Luz Divina\b", flags=re.IGNORECASE), "uma Imagem da Luz Divina"),
    ("goshintai", re.compile(r"\bna Imagem da Luz Divina\b", flags=re.IGNORECASE), "na Imagem da Luz Divina"),
    ("goshintai", re.compile(r"\bno Imagem da Luz Divina\b", flags=re.IGNORECASE), "na Imagem da Luz Divina"),
    # --- espíritos de divindades ---
    ("shinrei", re.compile(r"\bum espíritos de divindades\b", flags=re.IGNORECASE), "um espírito de divindades"),
    ("shinrei", re.compile(r"\buma espíritos de divindades\b", flags=re.IGNORECASE), "uma manifestação de espíritos de divindades"),
    ("shinrei", re.compile(r"\bo espíritos de divindades\b", flags=re.IGNORECASE), "os espíritos de divindades"),
    ("shinrei", re.compile(r"\ba espíritos de divindades\b", flags=re.IGNORECASE), "os espíritos de divindades"),
    # --- concentração / solidificação ---
    ("misc", re.compile(r"\bno concentração de toxinas\b", flags=re.IGNORECASE), "na concentração de toxinas"),
    ("misc", re.compile(r"\bo concentração de toxinas\b", flags=re.IGNORECASE), "a concentração de toxinas"),
    ("misc", re.compile(r"\bum concentração de toxinas\b", flags=re.IGNORECASE), "uma concentração de toxinas"),
    ("misc", re.compile(r"\buma solidificação de toxina\b", flags=re.IGNORECASE), "uma solidificação de toxina"),
    ("misc", re.compile(r"\bo solidificação\b", flags=re.IGNORECASE), "a solidificação"),
    ("misc", re.compile(r"\bum solidificação\b", flags=re.IGNORECASE), "uma solidificação"),
    # --- micróbio ---
    ("misc", re.compile(r"\buma micróbio venenosa\b", flags=re.IGNORECASE), "um micróbio venenoso"),
    ("misc", re.compile(r"\buma micróbio\b", flags=re.IGNORECASE), "um micróbio"),
    ("misc", re.compile(r"\bessa micróbio\b", flags=re.IGNORECASE), "esse micróbio"),
    ("misc", re.compile(r"\besta micróbio\b", flags=re.IGNORECASE), "este micróbio"),
    # --- innen ---
    ("innen", re.compile(r"\bo innen \(afinidade espiritual\)\b", flags=re.IGNORECASE), "o innen (afinidade espiritual)"),
    ("innen", re.compile(r"\bum innen \(afinidade espiritual\)\b", flags=re.IGNORECASE), "um innen (afinidade espiritual)"),
    # --- pequenas correções de fluência literal ---
    ("fluency", re.compile(r"\bHá um total de (\d+) volumes\b"), r"Existem \1 volumes"),
    ("fluency", re.compile(r"\bHá um total de\b"), "Existem"),
    # --- concordância residual ---
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais está\b", flags=re.IGNORECASE), "as nuvens espirituais estão"),
    ("nuvens_verb", re.compile(r"\bas nuvens espirituais havia\b", flags=re.IGNORECASE), "as nuvens espirituais haviam"),
    ("shinrei", re.compile(r"\bos espíritos de divindades é\b", flags=re.IGNORECASE), "os espíritos de divindades são"),
    ("shinrei", re.compile(r"\bos espíritos de divindades foi\b", flags=re.IGNORECASE), "os espíritos de divindades foram"),
    ("misc", re.compile(r"\bantepassado\(s\)\b", flags=re.IGNORECASE), "antepassados"),
)


@dataclass(frozen=True)
class Change:
    rule: str
    pattern: str
    replacement: str
    count: int


def normalize_whitespace(text: str) -> tuple[str, int]:
    """Collapse runs of spaces/tabs within lines; preserve paragraph breaks."""
    changes = 0
    lines = text.split("\n")
    normalized: list[str] = []
    for line in lines:
        updated = re.sub(r"[ \t]{2,}", " ", line)
        if updated != line:
            changes += 1
        normalized.append(updated.rstrip())
    result = "\n".join(normalized)
    # Remove space before punctuation
    updated, n = re.subn(r" +([,.;:!?])", r"\1", result)
    changes += n
    return updated, changes


def apply_grammar(pt_text: str) -> tuple[str, list[Change]]:
    findings: list[Change] = []
    new_text = pt_text

    for rule_name, pattern, replacement in GRAMMAR_RULES:
        if replacement == pattern.pattern:
            continue
        updated, count = pattern.subn(replacement, new_text)
        if count:
            findings.append(Change(rule_name, pattern.pattern, replacement, count))
            new_text = updated

    new_text, ws_count = normalize_whitespace(new_text)
    if ws_count:
        findings.append(Change("whitespace", "[ \\t]{2,}", "single space", ws_count))

    return new_text, findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply Portuguese grammar and fluency fixes to all PT sources.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    planned = []
    for pair in pair_entries(load_entries()):
        pt_path = permanent_pt_path(pair.pt)
        pt_text = pt_path.read_text(encoding="utf-8")
        new_text, findings = apply_grammar(pt_text)
        if not findings or new_text == pt_text:
            continue
        planned.append({
            "pt_path": str(pt_path.relative_to(PROJECT_ROOT)),
            "title": pair.pt.get("title"),
            "findings": [{"rule": c.rule, "pattern": c.pattern, "replacement": c.replacement, "count": c.count} for c in findings],
            "_new_text": new_text,
        })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "portuguese_grammar_pass_batch.jsonl"
    with report_path.open("w", encoding="utf-8") as f:
        for row in planned:
            f.write(json.dumps({k: v for k, v in row.items() if not k.startswith("_")}, ensure_ascii=False) + "\n")

    backup_path = None
    if args.apply and planned:
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"portuguese_grammar_pass_{ts}_before.tar.gz"
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
