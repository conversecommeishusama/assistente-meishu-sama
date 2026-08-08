#!/usr/bin/env python3
"""Avaliação editorial de pares JP/PT (linha a linha) — não só heurística de agulhas."""

from __future__ import annotations

import re
from dataclasses import dataclass

from livros_segmentacao_pairing import jp_session_needles  # noqa: E402
from protocol_line_revision import has_blocking_cjk, sanitize_turn_text  # noqa: E402
from retranslate_qa import validate_translation  # noqa: E402
from revisao_paralela_livros import _needle_hits  # noqa: E402
from semantic_pair_assessment import assess_glossary_coverage, assess_semantic_coverage  # noqa: E402
from a4b_assessment import (  # noqa: E402
    assess_a4b_label,
    profile_requires_a4b,
    pt_body_for_semantic,
)

PT_TRUNC_MARKER_RE = re.compile(r"\[truncado\]|\[incomplete\]", re.I)
_PT_DATE_RE = re.compile(
    r"\d{1,2}\s+de\s+|"
    r"\b(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b|"
    r"Showa|Era Showa|昭和|\*\*",
    re.I,
)

# Lixo típico de corrupção de revisão local (não linhas vazias nem datas normais)
_GARBAGE_PT_RE = re.compile(
    r"\[[0-9]{1,2}\s+de\s+"
    r"|\]\s*\d{1,2}\s+de\s+"
    r"|\[28\s+\[28"
    r"|publica\["
    r"|Gosuiji-roku,\s*publica\["
    r"|\]\d{1,2}\s+de\s+",
    re.I,
)
_META_POLLUTION_RE = re.compile(
    r"Publication source:|Paired JP entry:|Collection ID:|Original publication reference:",
    re.I,
)

_QUESTION_JP_RE = re.compile(r"[？?]|（お伺）|お伺")
_QUESTION_PT_RE = re.compile(r"\?\s*$|^\s*—", re.M)


@dataclass
class PairAssessment:
    ok: bool
    issues: list[str]
    editorial_note: str
    blocking: bool = True
    needs_human: bool = False
    human_doubt: str = ""
    missing_concepts: list[str] | None = None
    semantic_coverage: float | None = None


def _pt_looks_like_session_header(pt: str) -> bool:
    return bool(_PT_DATE_RE.search(pt))


def prefilter_unit_pair(unit_kind: str, pt_text: str) -> PairAssessment | None:
    """Filtro rápido — retorna avaliação se falha óbvia; None se deve continuar."""
    pt = sanitize_turn_text(pt_text)
    issues: list[str] = []

    if not pt:
        return PairAssessment(
            ok=False,
            issues=["pt_ausente"],
            editorial_note="Sem texto PT para esta unidade JP.",
        )
    if len(pt) < 3 and unit_kind not in ("blank",):
        return PairAssessment(
            ok=False,
            issues=["pt_ausente"],
            editorial_note="PT residual demasiado curto para ser tradução.",
        )
    if has_blocking_cjk(pt):
        return PairAssessment(
            ok=False,
            issues=["cjk_residual"],
            editorial_note="CJK bloqueante no parágrafo PT.",
        )
    if PT_TRUNC_MARKER_RE.search(pt):
        return PairAssessment(
            ok=False,
            issues=["pt_incompleto"],
            editorial_note="Marcador de truncamento no PT.",
        )
    if _GARBAGE_PT_RE.search(pt):
        return PairAssessment(
            ok=False,
            issues=["desalinhamento"],
            editorial_note="Texto PT parece lixo de metadata ou corrupção de revisão, não tradução.",
        )
    if _META_POLLUTION_RE.search(pt):
        return PairAssessment(
            ok=False,
            issues=["desalinhamento"],
            editorial_note="Metadata de ficheiro PT no par — trecho mal delimitado ou desalinhado.",
        )
    if unit_kind == "session_header" and not _pt_looks_like_session_header(pt):
        return PairAssessment(
            ok=False,
            issues=["desalinhamento"],
            editorial_note="Cabeçalho de sessão sem data reconhecível em português.",
        )
    return None


def assess_unit_pair(
    unit,
    pt_text: str,
    *,
    title: str = "",
    require_a4b: bool = False,
) -> PairAssessment:
    """Julgamento editorial JP↔PT para uma unidade (substitui unit_needs_fix)."""
    kind = unit.kind if hasattr(unit, "kind") else str(unit)
    jp = (unit.jp_text if hasattr(unit, "jp_text") else str(unit)).strip()
    pt = sanitize_turn_text(pt_text)
    pt_semantic = pt_body_for_semantic(pt) if require_a4b and kind in ("interlocutor", "meishu") else pt

    fast = prefilter_unit_pair(kind, pt_semantic or pt)
    if fast is not None:
        return fast

    issues: list[str] = []
    notes: list[str] = []

    # Papel / etiqueta
    if kind == "interlocutor":
        if pt.lower().startswith("meishu-sama:"):
            issues.append("desalinhamento")
            notes.append("Unidade JP é interlocutor, mas o PT começa como Meishu-Sama.")
        if _QUESTION_JP_RE.search(jp) and not _QUESTION_PT_RE.search(pt) and len(jp) > 20:
            notes.append("JP parece pergunta; PT não tem forma interrogativa (pode ser reformulação).")
    elif kind == "meishu":
        if pt.lower().startswith("interlocutor:"):
            issues.append("desalinhamento")
            notes.append("Unidade JP é Meishu-Sama, mas o PT está rotulado como Interlocutor.")

    # §4.4-B — rótulos Interlocutor: / Meishu-Sama:
    if require_a4b and kind in ("interlocutor", "meishu"):
        a4b_ok, a4b_note = assess_a4b_label(kind, pt)
        if not a4b_ok:
            issues.append("label_mismatch")
            notes.append(a4b_note)

    # Qualidade semântica — diálogo: glossário + sentido; prosa longa mantém cobertura
    use_semantic = kind in ("interlocutor", "meishu") or (kind == "prose" and len(jp) >= 200) or kind == "poem_line"
    if use_semantic and len(jp) >= 12:
        gloss_ok, gloss_hit, gloss_total, gloss_missing = assess_glossary_coverage(jp, pt_semantic or pt)
        sem = assess_semantic_coverage(jp, pt_semantic, kind=kind)
        pt_substantive = len(pt_semantic or pt) >= max(12, int(len(jp) * 0.07))

        # Bloqueantes objetivos além de estrutura: CJK, termos proibidos.
        # sanitize=True: aplica a mesma normalização usada no QA de tradução
        # (retranslate_qa.sanitize_pt_translation), que exclui a exceção
        # pedagógica do protocolo (§5.1b) — glosa curta de kanji entre
        # parênteses, ex. "kyō" (教). Sem isso, esse estilo sancionado era
        # sinalizado como resíduo japonês e travava o trecho em autofix.
        _out, qa = validate_translation(jp, pt, sanitize=True, min_jp_for_ratio=9999)
        for q in qa.issues:
            if q.startswith(("japones_residual", "saida_vazia")):
                issues.append("cjk_residual" if "japones" in q else "desalinhamento")
                notes.append(f"QA tradução: {q}")
            elif q.startswith(("linha_espiritual", "kotodama")):
                issues.append("desalinhamento")
                notes.append(f"QA tradução: {q}")

        # Cobertura literal — só bloqueia se glossário falha E texto claramente incompleto
        if kind in ("interlocutor", "meishu"):
            if not pt_substantive:
                issues.append("pt_ausente" if not pt else "traducao_incompleta")
                notes.append("PT demasiado curto para a réplica JP.")
            elif not gloss_ok and gloss_total >= 2 and gloss_hit == 0 and sem.coverage < 0.08:
                issues.append("desalinhamento")
                notes.append(
                    f"Termos do glossário ausentes no PT ({gloss_missing[:4]}) "
                    f"e cobertura muito baixa ({sem.coverage:.0%})."
                )
            elif not sem.ok and not gloss_ok and sem.coverage < 0.08 and not pt_substantive:
                issues.append("desalinhamento")
                notes.append(sem.doubt or f"Cobertura {sem.coverage:.0%}.")
            elif sem.uncertain and not gloss_ok:
                notes.append(sem.doubt or f"Cobertura intermédia ({sem.coverage:.0%}).")
        else:
            if not sem.ok:
                issues.append("desalinhamento" if sem.coverage < 0.15 else "traducao_incompleta")
                notes.append(sem.doubt or f"Cobertura semântica {sem.coverage:.0%} ({sem.anchors_hit}/{sem.anchors_total}).")
            elif sem.uncertain:
                notes.append(sem.doubt or f"Cobertura semântica intermédia ({sem.coverage:.0%}).")

        needs_human = any(q.startswith(("linha_espiritual", "kotodama")) for q in qa.issues)
        if not needs_human and sem.uncertain and not gloss_ok and kind not in ("interlocutor", "meishu"):
            needs_human = True
        human_doubt = sem.doubt if needs_human else ""
        missing = sem.missing or gloss_missing
        sem_cov = sem.coverage

        unique_issues = list(dict.fromkeys(issues))
        ok = not unique_issues and not needs_human
        editorial = "; ".join(notes) if notes else ("Par aceitável." if ok else "Par inválido.")
        return PairAssessment(
            ok=ok,
            issues=unique_issues or (["pt_ausente"] if not pt else []),
            editorial_note=editorial,
            blocking=not ok,
            needs_human=needs_human,
            human_doubt=human_doubt,
            missing_concepts=missing,
            semantic_coverage=sem_cov,
        )

    # session_header, performance_note, etc. — residual CJK / termos proibidos
    # (sanitize=True — ver nota acima sobre a exceção pedagógica §5.1b)
    if len(jp) >= 12:
        _out, qa = validate_translation(jp, pt, sanitize=True, min_jp_for_ratio=9999)
        for q in qa.issues:
            if q.startswith(("japones_residual", "saida_vazia", "linha_espiritual", "kotodama")):
                issues.append("cjk_residual" if "japones" in q else "desalinhamento")
                notes.append(f"QA tradução: {q}")

    # Coerência lexical — só prosa; diálogo já passou por glossário
    needles = [n for n in jp_session_needles(jp) if len(n.strip()) >= 10][:6]
    if needles and kind == "prose":
        hits, total = _needle_hits(pt, needles)
        if total >= 2 and hits == 0 and len(jp) > 40:
            issues.append("desalinhamento")
            notes.append(
                f"Nenhuma correspondência lexical entre JP e PT ({total} referências JP no texto)."
            )
        elif total >= 3 and hits < max(1, total // 3):
            issues.append("desalinhamento")
            notes.append(f"Pouca correspondência lexical ({hits}/{total}) — provável turno errado.")

    # Poema muito curto (fora do bloco semântico longo)
    if kind == "poem_line" and jp and len(jp) < 12 and len(pt) < max(8, len(jp) // 8):
        issues.append("desalinhamento")
        notes.append("Verso PT suspeitamente curto para o verso JP.")

    unique_issues = list(dict.fromkeys(issues))
    ok = not unique_issues
    editorial = "; ".join(notes) if notes else ("Par aceitável." if ok else "Par inválido.")
    return PairAssessment(
        ok=ok,
        issues=unique_issues or (["pt_ausente"] if not pt else []),
        editorial_note=editorial,
        blocking=not ok,
    )


def assessment_acceptable_for_autofix(assessment: PairAssessment) -> bool:
    """Tradução aplicável sem confirmação humana (inconsistências mecânicas)."""
    return assessment.ok or not assessment.needs_human


def assessment_needs_autofix(assessment: PairAssessment) -> bool:
    """Problema corrigível pelo agente — não é dúvida de significado."""
    return not assessment.ok and not assessment.needs_human


def unit_needs_fix(unit, pt_text: str, *, title: str = "", require_a4b: bool = False) -> tuple[bool, list[str]]:
    """Compat — delega a assess_unit_pair."""
    a = assess_unit_pair(unit, pt_text, title=title, require_a4b=require_a4b)
    if a.ok:
        return False, []
    labels = a.issues or ["desalinhamento"]
    human = [a.editorial_note] if a.editorial_note and not a.ok else []
    return True, labels + human
