#!/usr/bin/env python3
"""Third/final glossary round — remaining high-impact terms with JP gates."""

from __future__ import annotations

import argparse
import re

from apply_individual_term_haisetsu import KEEP_ELIMINATION_PATTERNS, should_keep_match
from apply_individual_term_kumori import is_spiritual_kumori
from apply_safe_glossary_fixes import RULES as SAFE_RULES
from glossary_apply_engine import DEFAULT_OUTPUT_DIR, run_glossary_pass

Rule = type(SAFE_RULES[0])

VACCINE_EXCLUDE = ("予防接種", "種痘", "ジェンナー", "天然痘", "BCG", "ワクチン")


def _jp_has(jp: str, term: str, exclude: tuple[str, ...] = ()) -> bool:
    if term not in jp:
        return False
    return not any(x in jp for x in exclude)


def _haisetsu_sub(text: str, pattern: re.Pattern[str], replacement: str) -> tuple[str, int]:
    count = 0

    def repl(match: re.Match[str]) -> str:
        nonlocal count
        if should_keep_match(text, match.start(), match.end()):
            return match.group(0)
        count += 1
        return replacement

    new_text = pattern.sub(repl, text)
    return new_text, count


def apply_round3(pt_text: str, jp_text: str) -> tuple[str, list[dict]]:
    findings: list[dict] = []
    new_text = pt_text

    simple_rules = (
        Rule(
            name="yakudoku_toxina",
            japanese_term="薬毒",
            replacements=(
                (re.compile(r"\bveneno dos remédios\b", flags=re.IGNORECASE), "toxina medicamentosa"),
                (re.compile(r"\bvenenos dos remédios\b", flags=re.IGNORECASE), "toxinas medicamentosas"),
                (re.compile(r"\bveneno medicinal\b", flags=re.IGNORECASE), "toxina medicamentosa"),
                (re.compile(r"\bvenenos medicinais\b", flags=re.IGNORECASE), "toxinas medicamentosas"),
                (re.compile(r"\btoxina dos remédios\b", flags=re.IGNORECASE), "toxina medicamentosa"),
                (re.compile(r"\btoxinas dos remédios\b", flags=re.IGNORECASE), "toxinas medicamentosas"),
                (re.compile(r"\btoxina do remédio\b", flags=re.IGNORECASE), "toxina medicamentosa"),
                (re.compile(r"\btoxinas do remédio\b", flags=re.IGNORECASE), "toxinas medicamentosas"),
                (re.compile(r"\btoxina de remédio\b", flags=re.IGNORECASE), "toxina medicamentosa"),
                (re.compile(r"\btoxinas de remédios\b", flags=re.IGNORECASE), "toxinas medicamentosas"),
            ),
        ),
        Rule(
            name="dokketsu_venenoso",
            japanese_term="毒血",
            replacements=(
                (re.compile(r"\bsangue venenoso\b", flags=re.IGNORECASE), "sangue toxêmico (estado sanguíneo impuro)"),
                (re.compile(r"\bsangue impuro\b", flags=re.IGNORECASE), "sangue toxêmico (estado sanguíneo impuro)"),
            ),
        ),
        Rule(
            name="taitai_broad",
            japanese_term="体的",
            replacements=(
                (re.compile(r"\bfisicamente\b", flags=re.IGNORECASE), "materialmente"),
                (re.compile(r"\bcorporalmente\b", flags=re.IGNORECASE), "materialmente"),
                (re.compile(r"\baspecto físico\b", flags=re.IGNORECASE), "aspecto material"),
                (re.compile(r"\baspectos físicos\b", flags=re.IGNORECASE), "aspectos materiais"),
                (re.compile(r"\bponto de vista físico\b", flags=re.IGNORECASE), "ponto de vista material"),
                (re.compile(r"\bdo ponto de vista físico\b", flags=re.IGNORECASE), "materialmente"),
                (re.compile(r"\bno ponto de vista físico\b", flags=re.IGNORECASE), "materialmente"),
                (re.compile(r"\bcausa física\b", flags=re.IGNORECASE), "causa material"),
                (re.compile(r"\bcausas físicas\b", flags=re.IGNORECASE), "causas materiais"),
                (re.compile(r"\bmundo físico\b", flags=re.IGNORECASE), "mundo material"),
            ),
        ),
        Rule(
            name="kokei_solid",
            japanese_term="固結",
            replacements=(
                (re.compile(r"\bendurecimento de toxinas\b", flags=re.IGNORECASE), "solidificação de toxinas"),
                (re.compile(r"\bendurecimentos de toxinas\b", flags=re.IGNORECASE), "solidificações de toxinas"),
                (re.compile(r"\bcoagulação de toxinas\b", flags=re.IGNORECASE), "solidificação de toxinas"),
                (re.compile(r"\bnódulo de toxina\b", flags=re.IGNORECASE), "solidificação de toxina"),
                (re.compile(r"\bnódulos de toxina\b", flags=re.IGNORECASE), "solidificações de toxina"),
            ),
        ),
        Rule(
            name="meishin",
            japanese_term="迷信",
            replacements=(
                (re.compile(r"\bcrendices\b", flags=re.IGNORECASE), "superstições"),
                (re.compile(r"\bcrendice\b", flags=re.IGNORECASE), "superstição"),
            ),
        ),
        Rule(
            name="jakyo",
            japanese_term="邪教",
            replacements=(
                (re.compile(r"\bseitas malignas\b", flags=re.IGNORECASE), "cultos malignos"),
                (re.compile(r"\bseita maligna\b", flags=re.IGNORECASE), "culto maligno"),
            ),
        ),
        Rule(
            name="innen",
            japanese_term="因縁",
            replacements=(
                (re.compile(r"\bkarma\b", flags=re.IGNORECASE), "innen (afinidade espiritual)"),
                (re.compile(r"\bafinidade espiritual\b(?!\s*\(innen)", flags=re.IGNORECASE), "innen (afinidade espiritual)"),
            ),
        ),
        Rule(
            name="eiko_pub",
            japanese_term="栄光",
            replacements=(
                (re.compile(r"\brevista Glória\b", flags=re.IGNORECASE), "revista Eikō"),
                (re.compile(r"\bpublicação Glória\b", flags=re.IGNORECASE), "publicação Eikō"),
                (re.compile(r"\(\s*Glória\s+n[ºo]", flags=re.IGNORECASE), "(Eikō nº"),
                (re.compile(r"\bEiko\b(?!\w)"), "Eikō"),
            ),
        ),
        Rule(
            name="reikai",
            japanese_term="霊界",
            replacements=(
                (re.compile(r"\breino espiritual\b", flags=re.IGNORECASE), "mundo espiritual"),
                (re.compile(r"\breinos espirituais\b", flags=re.IGNORECASE), "mundos espirituais"),
            ),
        ),
        Rule(
            name="shinji",
            japanese_term="神示",
            replacements=(
                (re.compile(r"\boráculo divino\b", flags=re.IGNORECASE), "revelação divina"),
                (re.compile(r"\boráculos divinos\b", flags=re.IGNORECASE), "revelações divinas"),
            ),
        ),
        Rule(
            name="haibyo",
            japanese_term="肺病",
            replacements=(
                (re.compile(r"\btuberculose pulmonar\b", flags=re.IGNORECASE), "doença pulmonar"),
                (re.compile(r"\bdoença pulmonar tuberculosa\b", flags=re.IGNORECASE), "doença pulmonar"),
            ),
        ),
        Rule(
            name="johrei_remaining",
            japanese_term="浄霊",
            replacements=(
                (re.compile(r"\bpurificação espiritual\b", flags=re.IGNORECASE), "Johrei"),
                (re.compile(r"\bPurificação Espiritual\b"), "Johrei"),
                (re.compile(r"\bJorei\b", flags=re.IGNORECASE), "Johrei"),
            ),
        ),
        Rule(
            name="keirin_remaining",
            japanese_term="経綸",
            replacements=(
                (re.compile(r"\badministração divina\b", flags=re.IGNORECASE), "Plano Divino"),
                (re.compile(r"\bprovidência divina\b", flags=re.IGNORECASE), "Plano Divino"),
                (re.compile(r"\bplano de Deus\b", flags=re.IGNORECASE), "Plano Divino"),
            ),
        ),
        Rule(
            name="tengoku_sky",
            japanese_term="天国",
            replacements=(
                (re.compile(r"\bvida no céu\b", flags=re.IGNORECASE), "vida no Paraíso"),
                (re.compile(r"\bcéu celestial\b", flags=re.IGNORECASE), "Paraíso"),
                (re.compile(r"\bparaíso celestial\b", flags=re.IGNORECASE), "Paraíso"),
            ),
        ),
        Rule(
            name="chijo_tengoku",
            japanese_term="地上天国",
            replacements=(
                (re.compile(r"\bParaíso Terrestre\b", flags=re.IGNORECASE), "Paraíso na Terra"),
                (re.compile(r"\bReino dos Céus na Terra\b", flags=re.IGNORECASE), "Paraíso na Terra"),
            ),
        ),
        Rule(
            name="shinrei_rem",
            japanese_term="神霊",
            replacements=(
                (re.compile(r"\bespíritos divinos\b", flags=re.IGNORECASE), "espíritos de divindades"),
                (re.compile(r"\bespírito divino\b", flags=re.IGNORECASE), "espíritos de divindades"),
            ),
        ),
        Rule(
            name="goriyaku_rem",
            japanese_term="御利益",
            replacements=(
                (re.compile(r"\bgraças materiais\b", flags=re.IGNORECASE), "benefícios materiais"),
                (re.compile(r"\bgraça material\b", flags=re.IGNORECASE), "benefício material"),
            ),
        ),
        Rule(
            name="shizen_noho",
            japanese_term="自然農法",
            replacements=(
                (re.compile(r"\bAgricultura Natural\b"), "método da agricultura natural"),
                (re.compile(r"\bMétodo de Agricultura Natural\b"), "método da agricultura natural"),
                (re.compile(r"\bmétodo de agricultura natural\b", flags=re.IGNORECASE), "método da agricultura natural"),
            ),
        ),
    )

    for rule in simple_rules:
        if rule.japanese_term not in jp_text:
            continue
        if rule.name == "tengoku_sky" and any(x in jp_text for x in ("福音", "マタイ", "御言葉")):
            continue
        for pattern, replacement in rule.replacements:
            updated, count = pattern.subn(replacement, new_text)
            if count:
                findings.append({"rule": rule.name, "pattern": pattern.pattern, "replacement": replacement, "count": count})
                new_text = updated

    # 排泄 — gated biological elimination
    if "排泄" in jp_text:
        haisetsu_pairs = (
            (re.compile(r"\beliminação de catarro\b", flags=re.IGNORECASE), "excreção de catarro"),
            (re.compile(r"\beliminação de expectoração\b", flags=re.IGNORECASE), "excreção de expectoração"),
            (re.compile(r"\beliminação de urina\b", flags=re.IGNORECASE), "excreção de urina"),
            (re.compile(r"\beliminação de fezes\b", flags=re.IGNORECASE), "excreção de fezes"),
            (re.compile(r"\beliminação de muco\b", flags=re.IGNORECASE), "excreção de muco"),
            (re.compile(r"\beliminações de catarro\b", flags=re.IGNORECASE), "excreções de catarro"),
            (re.compile(r"\bsão eliminadas para o exterior\b", flags=re.IGNORECASE), "são excretadas para o exterior"),
            (re.compile(r"\beliminadas para o exterior\b", flags=re.IGNORECASE), "excretadas para o exterior"),
            (re.compile(r"\beliminar para o exterior\b", flags=re.IGNORECASE), "excretar para o exterior"),
            (re.compile(r"\beliminação para o exterior\b", flags=re.IGNORECASE), "excreção para o exterior"),
            (re.compile(r"\bevacuação\b", flags=re.IGNORECASE), "excreção"),
            (re.compile(r"\bevacuações\b", flags=re.IGNORECASE), "excreções"),
            (re.compile(r"\beliminação\b", flags=re.IGNORECASE), "excreção"),
            (re.compile(r"\beliminações\b", flags=re.IGNORECASE), "excreções"),
            (re.compile(r"\beliminar\b", flags=re.IGNORECASE), "excretar"),
            (re.compile(r"\belimina\b", flags=re.IGNORECASE), "excreta"),
            (re.compile(r"\beliminado\b", flags=re.IGNORECASE), "excretado"),
            (re.compile(r"\beliminada\b", flags=re.IGNORECASE), "excretada"),
            (re.compile(r"\beliminados\b", flags=re.IGNORECASE), "excretados"),
            (re.compile(r"\beliminadas\b", flags=re.IGNORECASE), "excretadas"),
        )
        for pattern, replacement in haisetsu_pairs:
            updated, count = _haisetsu_sub(new_text, pattern, replacement)
            if count:
                findings.append({"rule": "haisetsu_broad", "pattern": pattern.pattern, "replacement": replacement, "count": count})
                new_text = updated

    # 曇り spiritual
    if is_spiritual_kumori(jp_text):
        kumori_pairs = (
            (re.compile(r"\bnévoa espiritual\b", flags=re.IGNORECASE), "nuvens espirituais"),
            (re.compile(r"\ba névoa\b", flags=re.IGNORECASE), "as nuvens espirituais"),
            (re.compile(r"\bo névoa\b", flags=re.IGNORECASE), "as nuvens espirituais"),
            (re.compile(r"\bnévoa\b", flags=re.IGNORECASE), "nuvens espirituais"),
            (re.compile(r"\bturvação\b", flags=re.IGNORECASE), "nuvens espirituais"),
            (re.compile(r"\bturvações\b", flags=re.IGNORECASE), "nuvens espirituais"),
        )
        for pattern, replacement in kumori_pairs:
            updated, count = pattern.subn(replacement, new_text)
            if count:
                findings.append({"rule": "kumori_broad", "pattern": pattern.pattern, "replacement": replacement, "count": count})
                new_text = updated

    # 注射 — exclude vaccination context
    if _jp_has(jp_text, "注射", VACCINE_EXCLUDE):
        for pattern, replacement in (
            (re.compile(r"\binjeções de vacina\b", flags=re.IGNORECASE), "injeções"),
            (re.compile(r"\binjeção de vacina\b", flags=re.IGNORECASE), "injeção"),
        ):
            updated, count = pattern.subn(replacement, new_text)
            if count:
                findings.append({"rule": "chusha", "pattern": pattern.pattern, "replacement": replacement, "count": count})
                new_text = updated

    # 医術 — spiritual healing compounds
    if "医術" in jp_text and "西洋医学" not in jp_text:
        for pattern, replacement in (
            (re.compile(r"\bArte da Cura Espiritual\b"), "terapia espiritual"),
            (re.compile(r"\barte de cura espiritual\b", flags=re.IGNORECASE), "terapia espiritual"),
            (re.compile(r"\bmedicina espiritual\b", flags=re.IGNORECASE), "terapia espiritual"),
            (re.compile(r"\bArte da Cura\b"), "terapia"),
            (re.compile(r"\barte da cura\b", flags=re.IGNORECASE), "terapia"),
        ):
            updated, count = pattern.subn(replacement, new_text)
            if count:
                findings.append({"rule": "ijutsu", "pattern": pattern.pattern, "replacement": replacement, "count": count})
                new_text = updated

    # 御論文 — title-like only
    if "御論文" in jp_text:
        for pattern, replacement in (
            (re.compile(r"\bmeus ensaios\b", flags=re.IGNORECASE), "meus artigos (de Meishu-Sama)"),
            (re.compile(r"\bnos meus ensaios\b", flags=re.IGNORECASE), "nos meus artigos (de Meishu-Sama)"),
            (re.compile(r"\beste ensaio de Meishu\b", flags=re.IGNORECASE), "este artigo (de Meishu-Sama)"),
            (re.compile(r"\bEnsaio de Meishu-Sama\b"), "artigo (de Meishu-Sama)"),
        ):
            updated, count = pattern.subn(replacement, new_text)
            if count:
                findings.append({"rule": "goronbun", "pattern": pattern.pattern, "replacement": replacement, "count": count})
                new_text = updated

    # 修業 spiritual
    if "修業" in jp_text and not any(x in jp_text for x in ("俳優", "団子", "仙人の修業")):
        for pattern, replacement in (
            (re.compile(r"\bausteridades\b", flags=re.IGNORECASE), "treinos espirituais"),
            (re.compile(r"\bausteridade\b", flags=re.IGNORECASE), "treino espiritual"),
            (re.compile(r"\bprática espiritual\b", flags=re.IGNORECASE), "treino espiritual"),
            (re.compile(r"\bdisciplina espiritual\b", flags=re.IGNORECASE), "treino espiritual"),
        ):
            updated, count = pattern.subn(replacement, new_text)
            if count:
                findings.append({"rule": "shugyo", "pattern": pattern.pattern, "replacement": replacement, "count": count})
                new_text = updated

    # 言霊
    if "言霊" in jp_text:
        for pattern, replacement in (
            (re.compile(r"\bKotodama\s*\(\s*espírito da palavra\s*\)", flags=re.IGNORECASE), "espírito da palavra"),
            (re.compile(r"\bKotodama\b", flags=re.IGNORECASE), "espírito da palavra"),
            (re.compile(r"\bkotodama\b", flags=re.IGNORECASE), "espírito da palavra"),
        ):
            updated, count = pattern.subn(replacement, new_text)
            if count:
                findings.append({"rule": "kotodama", "pattern": pattern.pattern, "replacement": replacement, "count": count})
                new_text = updated

    return new_text, findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply final glossary round 3.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=DEFAULT_OUTPUT_DIR.__class__, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_glossary_pass(
        apply_fn=apply_round3,
        report_name="glossary_round3_final.jsonl",
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
