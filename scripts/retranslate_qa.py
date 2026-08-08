#!/usr/bin/env python3
"""QA and post-processing for JP→PT retranslation output."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

CJK = r"[\u3040-\u30ff\u3400-\u9fff]"
CJK_RE = re.compile(CJK)
CJK_ONLY_RE = re.compile(rf"^{CJK}+$")
KOTODAMA_RE = re.compile(r"\bKotodama\b", re.I)
LINHA_ESPIRITUAL = re.compile(r"\blinha espiritual\b", re.I)

# 附 (forma alternativa de 憑) colada a sufixo verbal português
CJK_GLUED_VERB_RE = re.compile(
    rf"{CJK}+(ando|indo|endo|ado|ada|idos|idas|ar|ação|ações)\b",
    re.I,
)

# CJK colado a palavra latina: "do御守" -> "do omamori"
CJK_GLUED_LATIN_RE = re.compile(
    rf"(?<=[a-záàâãéêíóôõúçA-Z])({CJK}+)(?=\s|[,.;:!?)]|$)",
)
CJK_EMBEDDED_IN_WORD_RE = re.compile(
    rf"(?<=[a-záàâãéêíóôõúç])({CJK}+)(?=[a-záàâãéêíóôõúç])",
)
KNOWN_EMBEDDED_CJK = {
    "开拓": "coloniz",
    "開拓": "coloniz",
}

# "妙" (maravilhoso) -> "maravilhoso"
QUOTED_KANJI_GLOSS_RE = re.compile(
    rf'"({CJK}+)"\s*\(([^)]{{1,120}})\)',
)

# "示" (, shimesu-hen) -> shimesu-hen
QUOTED_KANJI_COMMA_GLOSS_RE = re.compile(
    rf'"({CJK}+)"\s*\(\s*,\s*([^)]+)\)',
)

# "玉" é -> é  (kanji solto entre aspas)
QUOTED_KANJI_ONLY_RE = re.compile(rf'"({CJK}+)"')

KNOWN_CJK_GLOSS = {
    "御守": "omamori",
    "御": "",
    "守": "",
}

SYMBOL_REPLACEMENTS = {
    "○丶": "círculo com ponto",
    "○": "círculo",
    "丶": "traço",
}

# Kanji/hiragana/katakana isolados entre parênteses
PAREN_JP_RE = re.compile(rf"\(([^)]*)\)")

# Sequência longa de japonês = trecho não traduzido
CJK_RUN_RE = re.compile(rf"{CJK}{{3,}}")

# Nomes próprios / termos do glossário permitidos na saída
ALLOWED_LATIN_TERMS = {
    "johrei",
    "meishu-sama",
    "kannon",
    "kannon-sama",
    "ohikari",
    "shojo",
    "daijo",
    "norito",
    "haiku",
    "senryu",
    "kanku",
    "tenrikyo",
    "ushitora",
    "chinkon",
    "oomoto",
    "kunitokotachi-no-mikoto",
    "amaterasu",
    "susanoo",
    "banko",
    "shakyamuni",
    "inari",
    "ebisu",
    "daikoku",
    "kyoshu",
    "omamori",
    "kagura",
    "omikuji",
    "hikari",
    "sunsei",
    "hakkosei",
    "reishutai",
}


@dataclass
class SanitizeReport:
    text: str
    fixes: list[str] = field(default_factory=list)


@dataclass
class QAResult:
    ok: bool
    issues: list[str] = field(default_factory=list)
    sanitized: bool = False
    sanitize_fixes: list[str] = field(default_factory=list)


def _fix_cjk_glued_verb(match: re.Match[str]) -> str:
    cjk = match.group(0)
    suffix = match.group(1).lower()
    if "附" in cjk or "憑" in cjk:
        return {"ando": "possuindo", "indo": "possuindo", "endo": "possuindo"}.get(
            suffix, "possuindo"
        )
    return suffix


def _clean_parenthetical_japanese(text: str, fixes: list[str]) -> str:
    def repl(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        if not inner:
            return match.group(0)
        if CJK_ONLY_RE.fullmatch(inner):
            fixes.append(f"removeu_parentese_jp:({inner})")
            return ""
        if CJK_RE.search(inner):
            cleaned = CJK_RE.sub("", inner).strip(" ·-–—")
            if not cleaned:
                fixes.append(f"removeu_parentese_jp:({inner})")
                return ""
            if cleaned != inner:
                fixes.append(f"limpou_parentese:({inner})->({cleaned})")
            return f"({cleaned})"
        return match.group(0)

    return PAREN_JP_RE.sub(repl, text)


def _clean_quoted_kanji_with_gloss(text: str, fixes: list[str]) -> str:
    def repl(match: re.Match[str]) -> str:
        kanji, gloss = match.group(1), match.group(2).strip()
        if CJK_RE.search(gloss):
            return match.group(0)
        fixes.append(f'kanji_aspas:"{kanji}"->"({gloss})"')
        return f'"{gloss}"'

    return QUOTED_KANJI_GLOSS_RE.sub(repl, text)


def _clean_orphan_quoted_kanji(text: str, fixes: list[str]) -> str:
    out = text

    def comma_gloss(match: re.Match[str]) -> str:
        gloss = match.group(2).strip()
        fixes.append(f'kanji_aspas_virgula:"{match.group(1)}"->{gloss}')
        return gloss

    out = QUOTED_KANJI_COMMA_GLOSS_RE.sub(comma_gloss, out)

    def orphan(match: re.Match[str]) -> str:
        kanji = match.group(1)
        fixes.append(f'kanji_aspas_solta:"{kanji}"')
        return ""

    out = QUOTED_KANJI_ONLY_RE.sub(orphan, out)
    out = re.sub(r"[ \t]+é\b", " é", out)
    out = re.sub(r"radical[ \t]+é", "é", out)
    out = re.sub(r"[ \t]{2,}", " ", out)
    return out


def _clean_glued_cjk_tokens(text: str, fixes: list[str]) -> str:
    def repl(match: re.Match[str]) -> str:
        token = match.group(1)
        if token in KNOWN_CJK_GLOSS:
            replacement = KNOWN_CJK_GLOSS[token]
            fixes.append(f"cjk_colado:{token}->{replacement or 'removido'}")
            return replacement
        fixes.append(f"cjk_colado_removido:{token}")
        return ""

    return CJK_GLUED_LATIN_RE.sub(repl, text)


def _clean_cjk_embedded_in_words(text: str, fixes: list[str]) -> str:
    def repl(match: re.Match[str]) -> str:
        cjk = match.group(1)
        if cjk in KNOWN_EMBEDDED_CJK:
            fixes.append(f"cjk_embutido:{cjk}->{KNOWN_EMBEDDED_CJK[cjk]}")
            return KNOWN_EMBEDDED_CJK[cjk]
        fixes.append(f"cjk_embutido_removido:{cjk}")
        return ""

    return CJK_EMBEDDED_IN_WORD_RE.sub(repl, text)


def _replace_teaching_symbols(text: str, fixes: list[str]) -> str:
    out = text
    for src, dst in SYMBOL_REPLACEMENTS.items():
        if src in out:
            out = out.replace(src, dst)
            fixes.append(f"simbolo:{src}->{dst}")
    return out


def sanitize_pt_translation(text: str) -> SanitizeReport:
    """Remove japonês residual comum sem alterar o sentido."""
    fixes: list[str] = []
    out = text

    out = _replace_teaching_symbols(out, fixes)

    new_out, n = CJK_GLUED_VERB_RE.subn(_fix_cjk_glued_verb, out)
    if n:
        fixes.append(f"corrigiu_verbo_colado:{n}")
    out = new_out

    out = _clean_glued_cjk_tokens(out, fixes)
    out = re.sub(r"\ba开拓ram\b", "a colonizaram", out)
    out = re.sub(r"\ba開拓ram\b", "a colonizaram", out)
    out = _clean_cjk_embedded_in_words(out, fixes)
    out = re.sub(r"\ba\s+colonizram\b", "a colonizaram", out)
    out = re.sub(r"\bacolonizram\b", "a colonizaram", out)
    out = _clean_quoted_kanji_with_gloss(out, fixes)
    out = _clean_orphan_quoted_kanji(out, fixes)
    out = _clean_parenthetical_japanese(out, fixes)

    # Kanji solto imediatamente após aspas: "cinco" (五) -> "cinco"
    new_out, n = re.subn(rf'(["\'])({CJK}+)\1\s*\({CJK}+\)', r"\1", out)
    if n:
        fixes.append(f"removeu_kanji_duplicado_aspas:{n}")
    out = new_out

    new_out, n = re.subn(rf'\s*\({CJK}+\)', "", out)
    if n:
        fixes.append(f"removeu_kanji_parentese_sobra:{n}")
    out = new_out

    # Espaços duplos gerados pela limpeza
    out = re.sub(r"  +", " ", out)
    out = re.sub(r" ([,.;:!?])", r"\1", out)

    return SanitizeReport(text=out, fixes=fixes)


def find_japanese_residuals(text: str) -> list[str]:
    """Lista trechos japoneses que permanecem após sanitização."""
    residuals: list[str] = []
    for match in CJK_RUN_RE.finditer(text):
        residuals.append(match.group(0))
    for match in CJK_RE.finditer(text):
        ch = match.group(0)
        if ch in residuals or any(ch in run for run in residuals):
            continue
        residuals.append(ch)
    return residuals


def pt_text_for_ratio(pt_body: str) -> str:
    """Corpo PT para ratio — exclui cabeçalho editorial A4."""
    parts = [p.strip() for p in re.split(r"\n\s*\n+", pt_body or "") if p.strip()]
    if not parts:
        return pt_body or ""
    start = 0
    for i, para in enumerate(parts):
        if re.search(r"publicado em", para, flags=re.IGNORECASE):
            start = i + 1
            break
    else:
        start = 1 if len(parts) > 1 and len(parts[0]) < 120 else 0
    body = "\n\n".join(parts[start:])
    return body or pt_body


def validate_translation(
    jp_body: str,
    pt_body: str,
    *,
    sanitize: bool = True,
    min_jp_for_ratio: int = 50,
) -> tuple[str, QAResult]:
    issues: list[str] = []
    sanitize_fixes: list[str] = []
    out = pt_body

    if sanitize:
        report = sanitize_pt_translation(pt_body)
        out = report.text
        sanitize_fixes = report.fixes

    if not out.strip():
        issues.append("saida_vazia")

    residuals = find_japanese_residuals(out)
    if residuals:
        issues.append(f"japones_residual_{len(residuals)}")
        if len(residuals) <= 5:
            issues.append("residual:" + "|".join(residuals[:5]))

    if LINHA_ESPIRITUAL.search(out):
        issues.append("linha_espiritual")
    if KOTODAMA_RE.search(out):
        issues.append("kotodama_proibido")

    if len(jp_body) >= min_jp_for_ratio:
        pt_ratio_src = pt_text_for_ratio(out)
        ratio = len(pt_ratio_src) / len(jp_body)
        short_jp = len(jp_body) < 800
        expansion_threshold = 5.5 if short_jp else 4.0
        severe_threshold = 8.0
        if ratio < 0.45:
            issues.append(f"truncamento_suspeito_ratio={ratio:.2f}")
        elif ratio > severe_threshold:
            issues.append(f"expansao_suspeita_ratio={ratio:.2f}")
        elif ratio > expansion_threshold:
            issues.append(f"expansao_suspeita_ratio={ratio:.2f}")

    qa = QAResult(
        ok=not issues,
        issues=issues,
        sanitized=bool(sanitize_fixes),
        sanitize_fixes=sanitize_fixes,
    )
    return out, qa
