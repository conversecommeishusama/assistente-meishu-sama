#!/usr/bin/env python3
"""Gated individual glossary passes for context-sensitive terms."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass

from glossary_apply_engine import DEFAULT_OUTPUT_DIR, run_glossary_pass


@dataclass(frozen=True)
class GatedRule:
    name: str
    japanese_gate: tuple[str, ...]
    replacements: tuple[tuple[re.Pattern[str], str], ...]
    japanese_any: bool = True
    exclude_jp: tuple[str, ...] = ()


def _gate(jp_text: str, rule: GatedRule) -> bool:
    if rule.exclude_jp and any(x in jp_text for x in rule.exclude_jp):
        return False
    if not rule.japanese_gate:
        return True
    if rule.japanese_any:
        return any(term in jp_text for term in rule.japanese_gate)
    return all(term in jp_text for term in rule.japanese_gate)


GATED_RULES = (
    # 固結 — toxin/medical solidification, not generic hardening
    GatedRule(
        name="kokei_toxin",
        japanese_gate=("固結", "薬毒", "毒素", "凝"),
        replacements=(
            (re.compile(r"\bendurecimentos\b", flags=re.IGNORECASE), "solidificações"),
            (re.compile(r"\bendurecimento\b", flags=re.IGNORECASE), "solidificação"),
            (re.compile(r"\bendurecer\b", flags=re.IGNORECASE), "solidificar"),
            (re.compile(r"\bendurece\b", flags=re.IGNORECASE), "solidifica"),
        ),
    ),
    # 医術 — spiritual healing art compounds
    GatedRule(
        name="ijutsu_reii",
        japanese_gate=("霊医術", "浄霊医術", "神医術"),
        replacements=(
            (re.compile(r"\barte de cura\b", flags=re.IGNORECASE), "terapia"),
            (re.compile(r"\barte da cura\b", flags=re.IGNORECASE), "terapia"),
            (re.compile(r"\bmedicina espiritual\b", flags=re.IGNORECASE), "terapia espiritual"),
        ),
    ),
    GatedRule(
        name="ijutsu_general",
        japanese_gate=("医術",),
        exclude_jp=("西洋医学", "俳優", "医者に"),
        replacements=((re.compile(r"\barte médica\b", flags=re.IGNORECASE), "terapia"),),
    ),
    # 修業 — exclude actor training
    GatedRule(
        name="shugyo_spirit",
        japanese_gate=("修業", "修行"),
        exclude_jp=("俳優", "仙人の修業", "団子"),
        replacements=(
            (re.compile(r"\bausteridades\b", flags=re.IGNORECASE), "treinos espirituais"),
            (re.compile(r"\bausteridade\b", flags=re.IGNORECASE), "treino espiritual"),
            (re.compile(r"\bdisciplina espiritual\b", flags=re.IGNORECASE), "treino espiritual"),
            (re.compile(r"\bprática espiritual\b", flags=re.IGNORECASE), "treino espiritual"),
        ),
    ),
    # 再生 — reincarnation / rebirth as human
    GatedRule(
        name="saisei_human",
        japanese_gate=("人間再生", "人が人に生", "転生", "龍神が人間に再生", "人間に再生"),
        replacements=(
            (re.compile(r"\brenasce\b", flags=re.IGNORECASE), "reencarna"),
            (re.compile(r"\brenascer\b", flags=re.IGNORECASE), "reencarnar"),
            (re.compile(r"\brenascimento\b", flags=re.IGNORECASE), "reencarnação"),
        ),
    ),
    # 言霊 — normalizar para forma consagrada (sem «Kotodama»)
    GatedRule(
        name="kotodama_expand",
        japanese_gate=("言霊",),
        replacements=(
            (re.compile(r"\bKotodama\s*\(\s*espírito da palavra\s*\)", flags=re.IGNORECASE), "espírito da palavra"),
            (re.compile(r"\bKotodama\b", flags=re.IGNORECASE), "espírito da palavra"),
            (re.compile(r"\b\(kotodama\)\b", flags=re.IGNORECASE), "espírito da palavra"),
            (re.compile(r"\bpoder da palavra\b", flags=re.IGNORECASE), "espírito da palavra"),
            (re.compile(r"\bciência da palavra espiritual\b", flags=re.IGNORECASE), "espírito da palavra"),
            (re.compile(r"\bciência da palavra\b", flags=re.IGNORECASE), "espírito da palavra"),
        ),
    ),
    # 邪神 — adjectival / nominal uses, exclude Okada-as-name lines
    GatedRule(
        name="jashin_noun",
        japanese_gate=("邪神",),
        exclude_jp=("岡田は邪神", "岡田が邪神"),
        replacements=(
            (re.compile(r"\bé um deus mau\b", flags=re.IGNORECASE), "é uma Divindade maligna"),
            (re.compile(r"\bé um mau deus\b", flags=re.IGNORECASE), "é uma Divindade maligna"),
            (re.compile(r"\bos deuses maus\b", flags=re.IGNORECASE), "as Divindades malignas"),
            (re.compile(r"\bo deus mau\b", flags=re.IGNORECASE), "a Divindade maligna"),
        ),
    ),
    # 御論文 — Meishu-Sama articles in publication context
    GatedRule(
        name="goronbun_context",
        japanese_gate=("御論文",),
        replacements=(
            (re.compile(r"\bmeu ensaio\b", flags=re.IGNORECASE), "meu artigo (de Meishu-Sama)"),
            (re.compile(r"\beste ensaio\b", flags=re.IGNORECASE), "este artigo (de Meishu-Sama)"),
            (re.compile(r"\bnos ensaios\b", flags=re.IGNORECASE), "nos artigos (de Meishu-Sama)"),
            (re.compile(r"\bnos meus ensaios\b", flags=re.IGNORECASE), "nos meus artigos (de Meishu-Sama)"),
        ),
    ),
    # 体的 — physical viewpoint when JP has 体的
    GatedRule(
        name="taiteki_gated",
        japanese_gate=("体的",),
        replacements=(
            (re.compile(r"\bfisicamente\b", flags=re.IGNORECASE), "materialmente"),
            (re.compile(r"\bcorporalmente\b", flags=re.IGNORECASE), "materialmente"),
            (re.compile(r"\baspecto físico\b", flags=re.IGNORECASE), "aspecto material"),
            (re.compile(r"\bponto de vista físico\b", flags=re.IGNORECASE), "ponto de vista material"),
        ),
    ),
    # 曇り — spiritual cloud gate
    GatedRule(
        name="kumori_spirit",
        japanese_gate=("霊の曇り", "魂の曇り", "心の曇り", "曇り", "霊体の曇り"),
        exclude_jp=("曇天", "天気", "気象"),
        replacements=(
            (re.compile(r"\bnuvem espiritual\b", flags=re.IGNORECASE), "nuvens espirituais"),
            (re.compile(r"\bnévoa espiritual\b", flags=re.IGNORECASE), "nuvens espirituais"),
            (re.compile(r"\bobscuridade espiritual\b", flags=re.IGNORECASE), "nuvens espirituais"),
        ),
    ),
    # 天国 — non-biblical paradise
    GatedRule(
        name="tengoku_paraiso",
        japanese_gate=("天国",),
        exclude_jp=("福音", "マタイ", "御言葉"),
        replacements=(
            (re.compile(r"\bvida no céu\b", flags=re.IGNORECASE), "vida no Paraíso"),
            (re.compile(r"\bcéu celestial\b", flags=re.IGNORECASE), "Paraíso"),
            (re.compile(r"\bparaíso celestial\b", flags=re.IGNORECASE), "Paraíso"),
        ),
    ),
)


def apply_gated(pt_text: str, jp_text: str) -> tuple[str, list[dict]]:
    findings: list[dict] = []
    new_text = pt_text
    for rule in GATED_RULES:
        if not _gate(jp_text, rule):
            continue
        for pattern, replacement in rule.replacements:
            new_text, count = pattern.subn(replacement, new_text)
            if count:
                findings.append(
                    {
                        "rule": rule.name,
                        "pattern": pattern.pattern,
                        "replacement": replacement,
                        "count": count,
                    }
                )
    return new_text, findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply gated individual glossary rules.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=DEFAULT_OUTPUT_DIR.__class__, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_glossary_pass(
        apply_fn=apply_gated,
        report_name="individual_glossary_gated.jsonl",
        apply=args.apply,
        output_dir=args.output_dir,
    )
    print(f"mode={'apply' if args.apply else 'dry-run'} texts={result['texts']} replacements={result['replacements']}")
    print("rules=" + __import__("json").dumps(result["rules"], ensure_ascii=False, sort_keys=True))
    print(f"report={result['report']}")
    if result["backup"]:
        print(f"backup={result['backup']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
