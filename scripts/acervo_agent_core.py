#!/usr/bin/env python3
"""Núcleo do agente Acervo Studio — mapa JP linha a linha, reconciliação PT, rotulagem A→C."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parent

# ――三十五… (dois traços + CJK sem espaço) também é interlocutor
JP_Q = re.compile(r"^(?:[—―–\-]{2}|[—―–\-]\s+)|^（お伺）")
JP_DATE = re.compile(
    r"^昭和(?:元|[一二三四五六七八九十百\d]+)年[一二三四五六七八九十百\d]+月"
    r"|[一二三四五六七八九十百\d]+月[一二三四五六七八九十百\d]+日"
)
JP_POEM_INTRO = re.compile(r"（[^）]*(?:御歌|和歌|短歌|詩)[^）]*）")
JP_PERF_NOTE = re.compile(r"（[^）]*(?:伴奏|朗読|独唱|演奏)[^）]*）")
JP_PAREN_STAGE = re.compile(r"^（[^）]+）$")
CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")


@dataclass
class JpLineUnit:
    line_no: int
    raw: str
    kind: str  # session_header, poem_intro, poem_line, performance_note, interlocutor, meishu, prose, blank
    marker: str = ""


@dataclass
class JpTurnUnit:
    kind: str  # interlocutor, meishu, header, narration, poem_block
    text: str
    line_start: int
    line_end: int
    label_pt: str = ""
    subkind: str = ""

    def __post_init__(self) -> None:
        if not self.label_pt:
            if self.kind == "interlocutor":
                self.label_pt = "Interlocutor"
            elif self.kind in ("meishu", "poem_block"):
                self.label_pt = "Meishu-Sama"
            elif self.kind == "header":
                self.label_pt = ""
            else:
                self.label_pt = ""


def map_jp_lines(text: str) -> list[JpLineUnit]:
    """Etapa A — leitura linha a linha com poemas e notas de cena."""
    rows: list[JpLineUnit] = []
    in_poem = False

    for i, raw in enumerate(text.splitlines(), start=1):
        s = raw.strip()
        if not s:
            rows.append(JpLineUnit(i, raw, "blank"))
            continue

        if JP_DATE.match(s) or (s.startswith("［") and s.endswith("］")):
            in_poem = False
            rows.append(JpLineUnit(i, raw, "session_header", "data/sessão"))
            continue

        if JP_PERF_NOTE.search(s) and JP_PAREN_STAGE.match(s):
            in_poem = False
            rows.append(JpLineUnit(i, raw, "performance_note", "伴奏/朗読"))
            continue

        if JP_POEM_INTRO.search(s):
            in_poem = True
            rows.append(JpLineUnit(i, raw, "poem_intro", "御歌/詩"))
            continue

        if JP_Q.match(s):
            in_poem = False
            body = re.sub(r"^[—―–\-]{1,2}\s*", "", s)
            rows.append(JpLineUnit(i, raw, "interlocutor", "――"))
            continue

        if raw.startswith("　") or raw.startswith("\u3000"):
            kind = "poem_line" if in_poem else "meishu"
            rows.append(JpLineUnit(i, raw, kind, "indent" if kind == "meishu" else "waka"))
            continue

        in_poem = False
        rows.append(JpLineUnit(i, raw, "prose", "texto"))

    return rows


def build_jp_turn_units(text: str, *, profile: str = "gokowa_roku_qa") -> list[JpTurnUnit]:
    """Unidades estruturais JP para o agente (poema = um bloco Meishu-Sama, não diálogo)."""
    import sys

    sys.path.insert(0, str(SCRIPTS))
    from qa_dialogue_annotation import parse_qa_turns  # noqa: WPS433

    lines = text.splitlines()
    line_map = map_jp_lines(text)
    kind_by_line = {r.line_no: r for r in line_map if r.kind != "blank"}

    turns = parse_qa_turns(text, lang="jp", profile=profile)
    units: list[JpTurnUnit] = []

    for t in turns:
        if t.kind == "header":
            units.append(JpTurnUnit("header", t.text, 0, 0, subkind="session_header"))
            continue
        if t.kind == "narration":
            units.append(JpTurnUnit("narration", t.text, 0, 0, subkind="prose"))
            continue
        if t.kind == "interlocutor":
            units.append(JpTurnUnit("interlocutor", t.text, 0, 0))
            continue
        if t.kind == "meishu":
            subkind = "prose"
            if JP_POEM_INTRO.search(t.text) or any(
                k in t.text for k in ("いたつき", "あらたまの", "ぬばたま", "弥勒")
            ):
                subkind = "poem_block"
            units.append(JpTurnUnit("poem_block" if subkind == "poem_block" else "meishu", t.text, 0, 0, subkind=subkind))
            continue

    # Enriquecer com números de linha aproximados
    cursor = 0
    for u in units:
        snippet = u.text[:40].splitlines()[0] if u.text else ""
        for i in range(cursor, len(lines)):
            if snippet and snippet in lines[i]:
                u.line_start = i + 1
                u.line_end = u.line_start + u.text.count("\n")
                cursor = i
                break

    return units


def _split_pt_paragraphs(body: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", body.strip()) if p.strip()]


def _strip_label(para: str) -> tuple[str, str]:
    if para.startswith("Interlocutor:"):
        return "Interlocutor", para[len("Interlocutor:") :].strip()
    if para.startswith("Meishu-Sama:"):
        return "Meishu-Sama", para[len("Meishu-Sama:") :].strip()
    return "", para


def _is_dialogue_para(para: str) -> bool:
    return para.startswith("Interlocutor:") or para.startswith("Meishu-Sama:")


def reconcile_pt_paragraphs_to_jp(jp_body: str, pt_body: str, *, profile: str = "gokowa_roku_qa") -> tuple[str, dict]:
    """Funde parágrafos PT errados (estrofes de poema como Interlocutor) até coincidir com turnos JP."""
    import sys

    sys.path.insert(0, str(SCRIPTS))
    from qa_dialogue_annotation import parse_qa_turns  # noqa: WPS433

    jp_turns = [t for t in parse_qa_turns(jp_body, lang="jp", profile=profile) if t.kind in ("interlocutor", "meishu")]
    paras = _split_pt_paragraphs(pt_body)
    pt_idx = [i for i, p in enumerate(paras) if _is_dialogue_para(p)]
    merged = 0

    # Atribuir parágrafos PT a cada turno JP
    groups: list[tuple[Any, list[int]]] = []
    pi = 0
    for jt in jp_turns:
        indices: list[int] = []
        if pi >= len(pt_idx):
            groups.append((jt, indices))
            continue
        indices.append(pt_idx[pi])
        pi += 1
        is_poem = bool(JP_POEM_INTRO.search(jt.text) or "御歌" in jt.text or "いたつき" in jt.text)
        if jt.kind == "meishu" and is_poem:
            while pi < len(pt_idx):
                remaining_jp = len(jp_turns) - len(groups) - 1
                remaining_pt = len(pt_idx) - pi
                if remaining_pt <= remaining_jp:
                    break
                indices.append(pt_idx[pi])
                pi += 1
                merged += 1
        groups.append((jt, indices))

    # Reconstruir corpo
    used = set()
    out: list[str] = []
    gi = 0
    for i, para in enumerate(paras):
        if not _is_dialogue_para(para):
            out.append(para)
            continue
        if gi < len(groups):
            jt, indices = groups[gi]
            if indices and i == indices[0]:
                texts = []
                for idx in indices:
                    used.add(idx)
                    _, t = _strip_label(paras[idx])
                    texts.append(t)
                label = "Interlocutor" if jt.kind == "interlocutor" else "Meishu-Sama"
                out.append(f"{label}: " + "\n".join(texts))
                gi += 1
            elif i in used:
                continue
            else:
                out.append(para)
        else:
            out.append(para)

    meta = {
        "jp_dialogue": len(jp_turns),
        "pt_dialogue_before": len(pt_idx),
        "pt_dialogue_after": sum(1 for p in out if _is_dialogue_para(p)),
        "merged_paragraphs": merged,
    }
    return "\n\n".join(out).strip() + "\n", meta


def relabel_pt_from_jp(jp_body: str, pt_body: str, *, profile: str = "gokowa_roku_qa") -> tuple[str, dict]:
    """Reconcilia + rotula PT conforme mapa JP (Etapa B→C)."""
    import sys

    sys.path.insert(0, str(SCRIPTS))
    from label_gokowa_a4b_from_jp import relabel_body_jp_guided  # noqa: WPS433

    merged, merge_meta = reconcile_pt_paragraphs_to_jp(jp_body, pt_body, profile=profile)
    relabeled, rel_meta = relabel_body_jp_guided(jp_body, merged)
    return relabeled, {**merge_meta, **rel_meta}


def find_line_range_by_anchor(jp_lines: list[str], anchor: str, next_anchor: str | None = None) -> dict[str, int]:
    """Resolve line_range_jp a partir de jp_anchor."""
    anchor = anchor.strip()
    start = None
    for i, ln in enumerate(jp_lines, start=1):
        if anchor in ln or (len(anchor) >= 8 and anchor[:40] in ln):
            start = i
            break
    if start is None:
        pos = "\n".join(jp_lines).find(anchor)
        if pos >= 0:
            start = "\n".join(jp_lines[: pos // max(1, len(jp_lines[0]) + 1)]).count("\n") + 1
    if start is None:
        raise ValueError(f"anchor não encontrado: {anchor[:60]!r}")

    end = len(jp_lines)
    if next_anchor:
        na = next_anchor.strip()
        for i in range(start, len(jp_lines) + 1):
            ln = jp_lines[i - 1] if i <= len(jp_lines) else ""
            if i > start and (na in ln or (len(na) >= 8 and na[:40] in ln)):
                end = i - 1
                break
    return {"start": start, "end": end}


def extract_segment_jp_pt(
    jp_full: str,
    pt_full: str,
    art: dict,
    next_art: dict | None,
    *,
    jp_lines: list[str] | None = None,
    articles: list[dict] | None = None,
    segment_index: int | None = None,
) -> tuple[str, str, dict[str, int]]:
    """Extrai fatia JP/PT de um trecho; corrige line_range e limites PT sequenciais."""
    if jp_lines is None:
        jp_lines = jp_full.splitlines()

    lr = art.get("line_range_jp")
    if not lr or not lr.get("start"):
        na = (next_art or {}).get("jp_anchor")
        lr = find_line_range_by_anchor(jp_lines, art.get("jp_anchor", ""), na)

    start, end = int(lr["start"]), int(lr["end"])
    jp_slice = "\n".join(jp_lines[start - 1 : end])

    pt_body = pt_full
    if "---" in pt_full:
        pt_body = pt_full.split("---", 1)[-1]

    pt_slice = pt_body
    if articles is not None and segment_index is not None:
        p0, p1 = compute_pt_bounds_for_segment(pt_body, articles, segment_index, jp_lines=jp_lines)
        pt_slice = pt_body[p0:p1].strip()
    elif art.get("pt_anchor") or art.get("jp_anchor") or art.get("pt_prefix"):
        anchor = (art.get("pt_anchor") or art.get("pt_prefix") or art.get("jp_anchor") or "").strip()
        anc_norm = _normalize_anchor(anchor)
        pos = pt_body.find(anc_norm) if anc_norm else -1
        if pos < 0 and anchor:
            pos = pt_body.find(anchor)
        if pos >= 0:
            end_pos = len(pt_body)
            if next_art:
                for key in ("pt_anchor", "pt_prefix", "title_pt", "jp_anchor"):
                    na = _normalize_anchor(str(next_art.get(key) or ""))
                    if na and na in pt_body[pos + 1 :]:
                        end_pos = min(end_pos, pt_body.find(na, pos + 1))
            pt_slice = pt_body[pos:end_pos].strip()

    return jp_slice, pt_slice, lr


def needs_translation(text: str) -> bool:
    return bool(text and CJK_RE.search(text))


def needs_pt_work(text: str) -> bool:
    """Turno PT vazio ou com CJK residual."""
    return not (text or "").strip() or needs_translation(text)


def _normalize_anchor(anchor: str) -> str:
    return re.sub(r"\*+", "", (anchor or "").strip())


def _session_start_candidates(art: dict) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for key in ("pt_anchor", "pt_prefix", "title_pt", "jp_anchor"):
        val = _normalize_anchor(str(art.get(key) or ""))
        if val and val not in seen:
            seen.add(val)
            out.append(val)
    return out


def _find_pt_session_start(pt_body: str, art: dict, *, after: int = 0) -> int:
    """Primeira ocorrência útil do início de sessão PT após `after`."""
    candidates = _session_start_candidates(art)
    hits: list[tuple[int, int]] = []
    for anc in candidates:
        pos = pt_body.find(anc, after)
        if pos >= 0:
            hits.append((pos, len(anc)))
    if not hits:
        for anc in candidates:
            # tentar só prefixo curto (ex. "8 de maio")
            short = anc.split("(")[0].strip()
            if len(short) >= 6:
                pos = pt_body.find(short, after)
                if pos >= 0:
                    hits.append((pos, len(short)))
    if not hits:
        return -1
    hits.sort(key=lambda x: x[0])
    # Preferir ocorrência com mais conteúdo depois (evita índice no fim do livro)
    best_pos = hits[0][0]
    best_score = -1
    for pos, _alen in hits:
        tail = pt_body[pos : pos + 8000]
        nxt = re.search(
            r"\n\n(?:\d{1,2} de [a-z]+|\*\*\d|Interlocutor:|Meishu-Sama:)",
            tail[80:],
            re.I,
        )
        content_len = (nxt.start() + 80) if nxt else len(tail)
        if content_len > best_score:
            best_score = content_len
            best_pos = pos
    return best_pos


def _is_toc_region(pt_body: str, pos: int) -> bool:
    """Detecta listagem de datas no fim do volume (índice, não sessão)."""
    window = pt_body[pos : pos + 3000]
    lines = [ln.strip() for ln in window.splitlines() if ln.strip()]
    if len(lines) < 4:
        return False
    date_lines = sum(
        1
        for ln in lines[:20]
        if re.match(r"^\d{1,2} de [a-záéíóúãõç]+", ln, re.I) or re.match(r"^[A-Z][a-záéíóúãõç]+ e Lua", ln)
    )
    short = sum(1 for ln in lines[:20] if len(ln) < 55)
    return date_lines >= 4 and short >= max(3, len(lines[:20]) // 2)


def _find_pt_toc_start(pt_body: str, *, after: int = 0) -> int:
    for m in re.finditer(r"(?:perguntar sobre:|gostaria de perguntar)", pt_body[after:], re.I):
        pos = after + m.start()
        if _is_toc_region(pt_body, pos + 20):
            return pos
    for m in re.finditer(r"\n\n18 de fevereiro \(quarta", pt_body[after:], re.I):
        pos = after + m.start()
        if _is_toc_region(pt_body, pos):
            return pos
    return len(pt_body)


def _jp_line_range(art: dict, next_art: dict | None, jp_lines: list[str]) -> dict[str, int]:
    lr = art.get("line_range_jp")
    if not lr or not lr.get("start"):
        na = (next_art or {}).get("jp_anchor")
        lr = find_line_range_by_anchor(jp_lines, art.get("jp_anchor", ""), na)
    return {"start": int(lr["start"]), "end": int(lr["end"])}


def compute_pt_bounds_for_segment(
    pt_body: str,
    articles: list[dict],
    segment_index: int,
    *,
    jp_lines: list[str] | None = None,
) -> tuple[int, int]:
    """Limites [start, end) do trecho PT — âncoras + fallback proporcional JP."""
    if segment_index < 0 or segment_index >= len(articles):
        raise IndexError(segment_index)

    art = articles[segment_index]
    next_art = articles[segment_index + 1] if segment_index + 1 < len(articles) else None

    # Preface / primeira sessão: âncora directa
    if segment_index <= 1:
        cursor = 0
        for i in range(segment_index + 1):
            a = articles[i]
            na = articles[i + 1] if i + 1 < len(articles) else None
            start = _find_pt_session_start(pt_body, a, after=cursor if i else 0)
            if start < 0:
                start = cursor
            if na:
                end = _find_pt_session_start(pt_body, na, after=start + 1)
                if end < 0 or _is_toc_region(pt_body, end):
                    end = _find_pt_toc_start(pt_body, after=start + 500)
            else:
                end = len(pt_body)
            if i == segment_index:
                return start, end
            cursor = max(end, start + 1)

    if not jp_lines:
        raise ValueError("jp_lines necessário para segmentos proporcionais")

    # Região PT contínua (sem cabeçalhos de data) entre sessão 1 e índice final
    region_start = _find_pt_session_start(pt_body, articles[1], after=0)
    if region_start < 0:
        region_start = 0
    region_end = _find_pt_toc_start(pt_body, after=region_start + 1000)
    total_jp = max(len(jp_lines), 1)

    lr = _jp_line_range(art, next_art, jp_lines)
    p0 = region_start + int((lr["start"] - 1) / total_jp * (region_end - region_start))
    if next_art:
        lr_next = _jp_line_range(next_art, articles[segment_index + 2] if segment_index + 2 < len(articles) else None, jp_lines)
        p1 = region_start + int((lr_next["start"] - 1) / total_jp * (region_end - region_start))
    else:
        p1 = region_end
    p0 = max(region_start, min(p0, region_end))
    p1 = max(p0 + 1, min(p1, region_end))
    return p0, p1


def restructure_unlabeled_pt_from_jp(
    jp_body: str,
    pt_body: str,
    *,
    translate_fn,
    profile: str = "gokowa_roku_qa",
) -> tuple[str, dict]:
    """PT sem rótulos A4B → turnos alinhados ao JP (usa contexto PT existente + tradução)."""
    import sys

    sys.path.insert(0, str(SCRIPTS))
    from qa_dialogue_annotation import parse_qa_turns  # noqa: WPS433

    turns = parse_qa_turns(jp_body, lang="jp", profile=profile)
    out_blocks: list[str] = []
    dialogue_n = 0
    structured_n = 0
    ctx = pt_body.strip()

    for t in turns:
        if t.kind == "header":
            out_blocks.append(t.text.strip())
            continue
        if t.kind == "narration":
            out_blocks.append(t.text.strip())
            continue
        if t.kind not in ("interlocutor", "meishu"):
            continue
        dialogue_n += 1
        label = "Interlocutor" if t.kind == "interlocutor" else "Meishu-Sama"
        pt_text = (translate_fn(t.text, label=label, pt_context=ctx) or "").strip()
        if pt_text:
            structured_n += 1
            out_blocks.append(f"{label}: {pt_text}")
        else:
            out_blocks.append(f"{label}: ")

    return "\n\n".join(out_blocks).strip() + "\n", {
        "jp_dialogue": dialogue_n,
        "structured_turns": structured_n,
        "bootstrap": "unlabeled_monolith",
    }


def segment_has_blocking_issues(jp_slice: str, pt_slice: str, *, profile: str = "gokowa_roku_qa") -> bool:
    """True se ainda há turnos vazios, CJK ou rótulo errado."""
    import sys

    sys.path.insert(0, str(SCRIPTS))
    from qa_dialogue_annotation import parse_qa_turns  # noqa: WPS433

    jp_turns = [t for t in parse_qa_turns(jp_slice, lang="jp", profile=profile) if t.kind in ("interlocutor", "meishu")]
    dlg: list[tuple[str, str]] = []
    for p in re.split(r"\n\s*\n", pt_slice.strip()):
        p = p.strip()
        if p.startswith("Interlocutor:"):
            dlg.append(("Interlocutor", p[len("Interlocutor:") :].strip()))
        elif p.startswith("Meishu-Sama:"):
            dlg.append(("Meishu-Sama", p[len("Meishu-Sama:") :].strip()))

    for i, jt in enumerate(jp_turns):
        expected = "Interlocutor" if jt.kind == "interlocutor" else "Meishu-Sama"
        if i >= len(dlg):
            return True
        label, text = dlg[i]
        if label != expected:
            return True
        if needs_pt_work(text):
            return True
    return len(dlg) < len(jp_turns)


def patch_pt_body_region(pt_body: str, old_region: str, new_region: str) -> str:
    """Substitui uma fatia PT (trecho) no corpo completo."""
    old = old_region.strip()
    new = new_region.strip()
    if old and old in pt_body:
        return pt_body.replace(old, new, 1)
    if new and not old:
        return pt_body.rstrip() + "\n\n" + new + "\n"
    return pt_body

