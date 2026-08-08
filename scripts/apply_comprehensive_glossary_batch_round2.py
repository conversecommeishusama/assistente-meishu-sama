#!/usr/bin/env python3
"""Second comprehensive glossary batch — remaining high-frequency terms."""

from __future__ import annotations

import argparse
import re

from apply_safe_glossary_fixes import RULES as SAFE_RULES
from glossary_apply_engine import DEFAULT_OUTPUT_DIR, apply_simple_rules, run_glossary_pass

Rule = type(SAFE_RULES[0])

ROUND2_RULES = (
    Rule(
        name="jorei_ho",
        japanese_term="浄霊法",
        replacements=(
            (re.compile(r"\bmétodos de purificação\b", flags=re.IGNORECASE), "métodos do Johrei"),
            (re.compile(r"\bmétodo de purificação\b", flags=re.IGNORECASE), "método do Johrei"),
            (re.compile(r"\bMétodo de Purificação\b"), "método do Johrei"),
        ),
    ),
    Rule(
        name="goriyaku",
        japanese_term="御利益",
        replacements=(
            (re.compile(r"\bgraças materiais\b", flags=re.IGNORECASE), "benefícios materiais"),
            (re.compile(r"\bgraça material\b", flags=re.IGNORECASE), "benefício material"),
            (re.compile(r"\bbenefícios mundanos\b", flags=re.IGNORECASE), "benefícios materiais"),
        ),
    ),
    Rule(
        name="keirin_more",
        japanese_term="経綸",
        replacements=(
            (re.compile(r"\bprovidência de Deus\b", flags=re.IGNORECASE), "Plano Divino"),
            (re.compile(r"\bProvidência de Deus\b"), "Plano Divino"),
            (re.compile(r"\bDivina Providência\b"), "Plano Divino"),
            (re.compile(r"\bdivina providência\b", flags=re.IGNORECASE), "Plano Divino"),
            (re.compile(r"\bplano divino\b", flags=re.IGNORECASE), "Plano Divino"),
            (re.compile(r"\bgrande plano divino\b", flags=re.IGNORECASE), "grande Plano Divino"),
        ),
    ),
    Rule(
        name="sorei_ancestral",
        japanese_term="祖霊",
        replacements=(
            (re.compile(r"\bespíritos dos antepassados\b", flags=re.IGNORECASE), "espíritos ancestrais"),
            (re.compile(r"\bespírito dos antepassados\b", flags=re.IGNORECASE), "espírito ancestral"),
            (re.compile(r"\bespíritos dos ancestrais\b", flags=re.IGNORECASE), "espíritos ancestrais"),
        ),
    ),
    Rule(
        name="senzo_more",
        japanese_term="先祖",
        replacements=(
            (re.compile(r"\bos ancestrais\b", flags=re.IGNORECASE), "os antepassados"),
            (re.compile(r"\bdos ancestrais\b", flags=re.IGNORECASE), "dos antepassados"),
            (re.compile(r"\baos ancestrais\b", flags=re.IGNORECASE), "aos antepassados"),
            (re.compile(r"\bpelos ancestrais\b", flags=re.IGNORECASE), "pelos antepassados"),
            (re.compile(r"\bseus ancestrais\b", flags=re.IGNORECASE), "seus antepassados"),
            (re.compile(r"\bnossos ancestrais\b", flags=re.IGNORECASE), "nossos antepassados"),
            (re.compile(r"\bmeus ancestrais\b", flags=re.IGNORECASE), "meus antepassados"),
            (re.compile(r"\bantepassados ancestrais\b", flags=re.IGNORECASE), "antepassados"),
        ),
    ),
    Rule(
        name="dokketsu_full",
        japanese_term="毒血",
        replacements=(
            (re.compile(r"\bsangue toxêmico\b(?!\s*\(estado)", flags=re.IGNORECASE), "sangue toxêmico (estado sanguíneo impuro)"),
            (re.compile(r"\bsangue tóxico\b", flags=re.IGNORECASE), "sangue toxêmico (estado sanguíneo impuro)"),
            (re.compile(r"\bsangue impuro\b", flags=re.IGNORECASE), "sangue toxêmico (estado sanguíneo impuro)"),
        ),
    ),
    Rule(
        name="kotodama_full",
        japanese_term="言霊",
        replacements=(
            (re.compile(r"\bKotodama\s*\(\s*espírito da palavra\s*\)", flags=re.IGNORECASE), "espírito da palavra"),
            (re.compile(r"\bKotodama\b", flags=re.IGNORECASE), "espírito da palavra"),
            (re.compile(r"\bkotodama\b", flags=re.IGNORECASE), "espírito da palavra"),
        ),
    ),
    Rule(
        name="zengen_more",
        japanese_term="善言讃詞",
        replacements=(
            (re.compile(r"\bOração de Zengen\b", flags=re.IGNORECASE), "Oração Zengen-Sandji"),
            (re.compile(r"\bZengen Sandji\b"), "Zengen-Sandji"),
            (re.compile(r"\bOração Zengen\b"), "Oração Zengen-Sandji"),
            (re.compile(r"\bprece Zengen\b", flags=re.IGNORECASE), "Oração Zengen-Sandji"),
        ),
    ),
    Rule(
        name="goshugo_more",
        japanese_term="御守護",
        replacements=(
            (re.compile(r"\bproteção dos deuses\b", flags=re.IGNORECASE), "proteção divina"),
            (re.compile(r"\bproteção dos budas\b", flags=re.IGNORECASE), "proteção divina"),
            (re.compile(r"\bproteção dos deuses e budas\b", flags=re.IGNORECASE), "proteção divina"),
        ),
    ),
    Rule(
        name="oomoto_more",
        japanese_term="大本教",
        replacements=(
            (re.compile(r"\breligião Omoto\b", flags=re.IGNORECASE), "religião Oomoto"),
            (re.compile(r"\bIgreja Omoto\b", flags=re.IGNORECASE), "religião Oomoto"),
            (re.compile(r"\bseita Omoto\b", flags=re.IGNORECASE), "religião Oomoto"),
        ),
    ),
    Rule(
        name="meishin_more",
        japanese_term="迷信",
        replacements=(
            (re.compile(r"\bcrendices supersticiosas\b", flags=re.IGNORECASE), "superstições"),
            (re.compile(r"\bcrendice supersticiosa\b", flags=re.IGNORECASE), "superstição"),
            (re.compile(r"\bcrendices\b", flags=re.IGNORECASE), "superstições"),
            (re.compile(r"\bcrendice\b", flags=re.IGNORECASE), "superstição"),
        ),
    ),
    Rule(
        name="jakyo_more",
        japanese_term="邪教",
        replacements=(
            (re.compile(r"\bseitas malignas\b", flags=re.IGNORECASE), "cultos malignos"),
            (re.compile(r"\bseita maligna\b", flags=re.IGNORECASE), "culto maligno"),
            (re.compile(r"\breligiões malignas\b", flags=re.IGNORECASE), "cultos malignos"),
            (re.compile(r"\breligião maligna\b", flags=re.IGNORECASE), "culto maligno"),
        ),
    ),
    Rule(
        name="innen_more",
        japanese_term="因縁",
        replacements=(
            (re.compile(r"\bafinidade espiritual\b(?!\s*\(innen)"), "innen (afinidade espiritual)"),
            (re.compile(r"\bkarma espiritual\b", flags=re.IGNORECASE), "innen (afinidade espiritual)"),
            (re.compile(r"\bkarma\b", flags=re.IGNORECASE), "innen (afinidade espiritual)"),
        ),
    ),
    Rule(
        name="kokei_more",
        japanese_term="固結",
        replacements=(
            (re.compile(r"\bsolidificações de toxinas\b", flags=re.IGNORECASE), "solidificações"),
            (re.compile(r"\bsolidificação de toxinas\b", flags=re.IGNORECASE), "solidificação"),
            (re.compile(r"\bnódulo de toxina\b", flags=re.IGNORECASE), "solidificação de toxina"),
            (re.compile(r"\bnódulos de toxina\b", flags=re.IGNORECASE), "solidificações de toxina"),
        ),
    ),
    Rule(
        name="haibyo_more",
        japanese_term="肺病",
        replacements=(
            (re.compile(r"\btuberculose pulmonar\b", flags=re.IGNORECASE), "doença pulmonar"),
            (re.compile(r"\bdoença dos pulmões\b", flags=re.IGNORECASE), "doença pulmonar"),
        ),
    ),
    Rule(
        name="shinrei_more",
        japanese_term="神霊",
        replacements=(
            (re.compile(r"\bespíritos divinos\b", flags=re.IGNORECASE), "espíritos de divindades"),
            (re.compile(r"\bespírito divino\b", flags=re.IGNORECASE), "espíritos de divindades"),
            (re.compile(r"\bespíritos dos deuses\b", flags=re.IGNORECASE), "espíritos de divindades"),
        ),
    ),
    Rule(
        name="yakudoku_more",
        japanese_term="薬毒",
        replacements=(
            (re.compile(r"\bveneno medicinal\b", flags=re.IGNORECASE), "toxina medicamentosa"),
            (re.compile(r"\bvenenos medicinais\b", flags=re.IGNORECASE), "toxinas medicamentosas"),
            (re.compile(r"\btoxina de remédio\b", flags=re.IGNORECASE), "toxina medicamentosa"),
            (re.compile(r"\btoxinas de remédios\b", flags=re.IGNORECASE), "toxinas medicamentosas"),
        ),
    ),
    Rule(
        name="kumori_more",
        japanese_term="曇り",
        replacements=(
            (re.compile(r"\bturvação espiritual\b", flags=re.IGNORECASE), "nuvens espirituais"),
            (re.compile(r"\bturvações espirituais\b", flags=re.IGNORECASE), "nuvens espirituais"),
            (re.compile(r"\bobscuridade espiritual\b", flags=re.IGNORECASE), "nuvens espirituais"),
        ),
    ),
    Rule(
        name="eiko_more",
        japanese_term="栄光",
        replacements=(
            (re.compile(r"\brevista Glória\b", flags=re.IGNORECASE), "revista Eikō"),
            (re.compile(r"\bna Glória\b"), "na Eikō"),
            (re.compile(r"\bda Glória\b"), "da Eikō"),
            (re.compile(r"\bpublicação Glória\b", flags=re.IGNORECASE), "publicação Eikō"),
        ),
    ),
    Rule(
        name="chijo_more",
        japanese_term="地上天国",
        replacements=(
            (re.compile(r"\bmodelo do Paraíso Terrestre\b", flags=re.IGNORECASE), "modelo do Paraíso na Terra"),
            (re.compile(r"\bconstrução do Paraíso Terrestre\b", flags=re.IGNORECASE), "construção do Paraíso na Terra"),
            (re.compile(r"\brealização do Paraíso Terrestre\b", flags=re.IGNORECASE), "realização do Paraíso na Terra"),
        ),
    ),
    Rule(
        name="matsuru_more",
        japanese_term="祀る",
        replacements=(
            (re.compile(r"\bcultuar os espíritos ancestrais\b", flags=re.IGNORECASE), "sufragar os espíritos ancestrais"),
            (re.compile(r"\bcultuar os antepassados\b", flags=re.IGNORECASE), "sufragar os antepassados"),
        ),
    ),
)


def apply_round2(pt_text: str, jp_text: str) -> tuple[str, list[dict]]:
    return apply_simple_rules(pt_text, jp_text, ROUND2_RULES)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply round-2 comprehensive glossary batch.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=DEFAULT_OUTPUT_DIR.__class__, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_glossary_pass(
        apply_fn=apply_round2,
        report_name="comprehensive_glossary_batch_round2.jsonl",
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
