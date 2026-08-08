#!/usr/bin/env python3
"""Passes de glossário alinhados a glossario_traducao.json para periodicos_trabalho."""

from __future__ import annotations

import re

from apply_individual_term_haisetsu import apply_haisetsu
from apply_individual_term_keirin import apply_keirin
from apply_individual_term_kumori import apply_kumori
from apply_individual_term_shinrei import apply_shinrei
from apply_individual_term_sorei import apply_sorei
from apply_individual_term_tengoku import CHIJOU_RULES, TENGOKU_RULES, apply_rules
from glossary_apply_engine import SimpleRule, apply_simple_rules

# Regras que revertem substituições do comprehensive incompatíveis com glossario_traducao.
TRADUCAO_REVERT_RULES: tuple[SimpleRule, ...] = (
    SimpleRule(
        name="dokketsu_traducao",
        japanese_term="毒血",
        replacements=((re.compile(r"\bsangue toxêmico\b", re.I), "sangue tóxico"),),
    ),
    SimpleRule(
        name="kamigakari_traducao",
        japanese_term="神憑り",
        replacements=(
            (re.compile(r"\binspiração divina \(kami-gakari\)", re.I), "possessão por divindades"),
            (re.compile(r"\bpossessão divina\b", re.I), "possessão por divindades"),
            (re.compile(r"\bpossessão espiritual por divindades\b", re.I), "possessão por divindades"),
        ),
    ),
    SimpleRule(
        name="reikai_traducao",
        japanese_term="霊界",
        replacements=(
            (re.compile(r"\bmundos espirituais\b", re.I), "mundo espiritual"),
            (re.compile(r"\breinos espirituais\b", re.I), "mundo espiritual"),
            (re.compile(r"\breino espiritual\b", re.I), "mundo espiritual"),
        ),
    ),
)

TRADUCAO_ALIGN_RULES: tuple[SimpleRule, ...] = (
    SimpleRule(
        name="jigoku_inferno",
        japanese_term="地獄",
        replacements=(
            (re.compile(r"\breligi(?:ão|ões) infernais?\b", re.I), "religião do Inferno"),
            (re.compile(r"\bsociedade infernal\b", re.I), "sociedade do Inferno"),
            (re.compile(r"\bcrenças infernais\b", re.I), "crenças do Inferno"),
            (re.compile(r"\bmundo infernal\b", re.I), "Inferno"),
            (re.compile(r"\bno inferno\b", re.I), "no Inferno"),
        ),
    ),
    SimpleRule(
        name="kumoru_nublar",
        japanese_term="曇る",
        replacements=(
            (re.compile(r"\bo espírito se nubla\b", re.I), "o espírito nubla-se"),
            (re.compile(r"\ba névoa se nubla\b", re.I), "a névoa nubla-se"),
            (re.compile(r"\bturva o espírito\b", re.I), "faz o espírito nublar-se"),
            (re.compile(r"\bturva o sangue\b", re.I), "turva o sangue"),
        ),
    ),
    SimpleRule(
        name="oomoto_ofudesaki",
        japanese_term="大本教のお筆先",
        replacements=(
            (re.compile(r"\bOfudesaki da Grande nossa Igreja\b", re.I), "Ofudesaki da religião Oomoto"),
            (re.compile(r"\bOfudesaki da nossa Igreja\b", re.I), "Ofudesaki da religião Oomoto"),
            (re.compile(r"\bno Ofudesaki da nossa Igreja\b", re.I), "no Ofudesaki da religião Oomoto"),
            (re.compile(r"\bno Ofudesaki do grande fundador da nossa Igreja\b", re.I), "no Ofudesaki do fundador da religião Oomoto"),
        ),
    ),
    SimpleRule(
        name="oomoto_nyuso",
        japanese_term="大本教入",
        replacements=(
            (re.compile(r"\bentrei na grande nossa Igreja\b", re.I), "entrei na religião Oomoto"),
            (re.compile(r"\bentrei para a grande nossa Igreja\b", re.I), "entrei na religião Oomoto"),
        ),
    ),
    SimpleRule(
        name="oomoto_kyoso",
        japanese_term="大本教祖",
        replacements=(
            (re.compile(r"\bgrande fundador da nossa Igreja\b", re.I), "fundador da religião Oomoto"),
            (re.compile(r"\bdo grande fundador da nossa Igreja\b", re.I), "do fundador da religião Oomoto"),
        ),
    ),
    SimpleRule(
        name="oomoto_names",
        japanese_term="大本教",
        replacements=(
            (re.compile(r"\bDaihonkyo\b", re.I), "religião Oomoto"),
            (re.compile(r"\bDaimatsukyo\b", re.I), "religião Oomoto"),
            (re.compile(r"\bIgreja Daikyō\b", re.I), "religião Oomoto"),
            (re.compile(r"\bIgreja Daikyo\b", re.I), "religião Oomoto"),
            (re.compile(r"\bOomoto adverte\b", re.I), "religião Oomoto adverte"),
        ),
    ),
    SimpleRule(
        name="oomoto_shinja",
        japanese_term="大本教信者",
        replacements=(
            (re.compile(r"\bera um grande seguidor\b", re.I), "era seguidor da religião Oomoto"),
            (re.compile(r"\bquando eu era um grande seguidor\b", re.I), "quando eu era seguidor da religião Oomoto"),
        ),
    ),
    SimpleRule(
        name="beikoku",
        japanese_term="米国",
        replacements=((re.compile(r"\bnos EUA\b", re.I), "nos Estados Unidos"),),
    ),
    SimpleRule(
        name="eikoku",
        japanese_term="英国",
        replacements=((re.compile(r"\bReino Unido\b", re.I), "Inglaterra"),),
    ),
    SimpleRule(
        name="dori_caminho",
        japanese_term="道理",
        replacements=(
            (re.compile(r"\bo Caminho da Verdade\b", re.I), "Caminho Perfeito"),
            (re.compile(r"\bo caminho da verdade\b", re.I), "Caminho Perfeito"),
        ),
    ),
    SimpleRule(
        name="kyoshu",
        japanese_term="教修",
        replacements=(
            (re.compile(r"\binstrução religiosa\b", re.I), "Kyoshu"),
            (re.compile(r"\baulas de instrução\b", re.I), "Kyoshu"),
            (re.compile(r"\b(\d+)\s+dias de treinamento\b", re.I), r"\1 dias de Kyoshu"),
            (re.compile(r"\bdias de treinamento\b", re.I), "dias de Kyoshu"),
            (re.compile(r"\b(\d+)\s+dias de prática\b", re.I), r"\1 dias de Kyoshu"),
            (re.compile(r"\bapenas alguns dias de treinamento\b", re.I), "apenas alguns dias de Kyoshu"),
            (re.compile(r"\bapenas alguns dias de prática\b", re.I), "apenas alguns dias de Kyoshu"),
            (re.compile(r"\btrês dias de treinamento\b", re.I), "três dias de Kyoshu"),
            (re.compile(r"\btrês dias de prática\b", re.I), "três dias de Kyoshu"),
            (re.compile(r"\bcurso de instrução\b", re.I), "Kyoshu"),
            (re.compile(r"\breceber treinamento\b", re.I), "receber Kyoshu"),
            (re.compile(r"\bqueria receber instrução\b", re.I), "queria receber Kyoshu"),
        ),
    ),
    SimpleRule(
        name="haisetsu_fallback",
        japanese_term="排泄物",
        replacements=((re.compile(r"\beliminações\b", re.I), "excreções"),),
    ),
    SimpleRule(
        name="yakudoku_traducao",
        japanese_term="薬毒",
        replacements=(
            (re.compile(r"\bveneno de medicamentos\b", re.I), "toxina medicamentosa"),
            (re.compile(r"\bvenenos de medicamentos\b", re.I), "toxinas medicamentosas"),
            (re.compile(r"\btoxinas dos medicamentos\b", re.I), "toxinas medicamentosas"),
        ),
    ),
    SimpleRule(
        name="houi",
        japanese_term="憑依",
        replacements=(
            (re.compile(r"\bse apossou\b", re.I), "houve possessão espiritual"),
            (re.compile(r"\bse apossaram\b", re.I), "houve possessão espiritual"),
        ),
    ),
    SimpleRule(
        name="kokei",
        japanese_term="固結",
        replacements=((re.compile(r"\bendurecimento local\b", re.I), "solidificação local"),),
    ),
)


def _changes_to_findings(scope: str, changes) -> list[dict]:
    out: list[dict] = []
    for c in changes:
        out.append(
            {
                "scope": scope,
                "rule": getattr(c, "rule", scope),
                "pattern": getattr(c, "pattern", ""),
                "replacement": getattr(c, "replacement", ""),
                "count": getattr(c, "count", 1),
            }
        )
    return out


def apply_periodicos_traducao_pass(pt_text: str, jp_text: str) -> tuple[str, list[dict]]:
    findings: list[dict] = []
    text = pt_text

    for label, fn in (
        ("revert", lambda t, j: apply_simple_rules(t, j, TRADUCAO_REVERT_RULES)),
        ("align", lambda t, j: apply_simple_rules(t, j, TRADUCAO_ALIGN_RULES)),
    ):
        text, f = fn(text, jp_text)
        findings.extend({"scope": f"traducao_{label}", **x} for x in f)

    text, f = apply_kumori(text, jp_text)
    findings.extend(_changes_to_findings("kumori", f))

    text, f = apply_shinrei(text, jp_text)
    findings.extend(_changes_to_findings("shinrei", f))

    text, f = apply_haisetsu(text, jp_text)
    findings.extend(_changes_to_findings("haisetsu", f))

    text, f = apply_sorei(text, jp_text)
    findings.extend(_changes_to_findings("sorei", f))

    text, f = apply_keirin(text, jp_text)
    findings.extend(_changes_to_findings("keirin", f))

    text, f2 = apply_rules(text, jp_text, TENGOKU_RULES)
    text, f3 = apply_rules(text, jp_text, CHIJOU_RULES)
    findings.extend(_changes_to_findings("tengoku", f2 + f3))

    return text, findings
