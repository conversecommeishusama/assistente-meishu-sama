#!/usr/bin/env python3
"""Motor de revisão JP→PT linha a linha.

Protocolo A→D (fonte de verdade = map_jp_lines):

  A  dividir trecho JP linha a linha (map_jp_lines)
  B  dividir PT comparando com JP linha a linha + revisão editorial
  C  se falhar: buscar trecho completo no corpus → alinhar linha a linha;
     senão retraduzir trecho inteiro → ajustar linha a linha o que a API não resolveu
  D  validação final linha a linha
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass, field
from typing import Any, Callable

SCRIPTS = __import__("pathlib").Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_agent_core import JpLineUnit, map_jp_lines  # noqa: E402
from apply_manual_livros_segmentacao import Boundary  # noqa: E402
from line_by_line_slices import (  # noqa: E402
    find_pt_start,
    get_volume_slices,
    invalidate_slice_cache,
    trecho_pt_start_patterns,
    validate_segment_slice,
)
from line_pair_assessment import assess_unit_pair, unit_needs_fix  # noqa: E402
from protocol_line_revision import (  # noqa: E402
    ISSUE_ALIGN,
    ISSUE_CJK,
    ISSUE_NO_PT,
    SegmentProtocolResult,
    has_blocking_cjk,
    sanitize_turn_text,
    trim_pt_chunk_leakage,
)
from livros_segmentacao_pairing import jp_session_needles, jp_slice_date_pt, yamamizu_jp_date_to_pt  # noqa: E402

_MERGE_KINDS = frozenset({"meishu", "poem_line", "prose"})
_ATOMIC_KINDS = frozenset({"session_header", "poem_intro", "performance_note", "interlocutor", "blank"})

PT_TRUNC_MARKER_RE = re.compile(r"\[truncado\]|\[incomplete\]", re.I)
_PT_DATE_RE = re.compile(
    r"\d{1,2}\s+de\s+|"
    r"\b(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b|"
    r"Showa|Era Showa|昭和|\*\*",
    re.I,
)


@dataclass
class JpContentUnit:
    index: int
    kind: str
    jp_lines: list[JpLineUnit]
    jp_text: str
    line_start: int
    line_end: int


@dataclass
class LinePair:
    unit: JpContentUnit
    pt_text: str
    pt_start: int = -1
    pt_end: int = -1
    issues: list[str] = field(default_factory=list)


def build_jp_content_units(jp_slice: str) -> list[JpContentUnit]:
    rows = map_jp_lines(jp_slice)
    units: list[JpContentUnit] = []
    buf: list[JpLineUnit] = []
    buf_kind: str | None = None
    idx = 0

    def flush() -> None:
        nonlocal idx, buf, buf_kind
        if not buf:
            return
        text = "\n".join(ln.raw for ln in buf).strip()
        units.append(
            JpContentUnit(
                index=idx,
                kind=buf_kind or "prose",
                jp_lines=list(buf),
                jp_text=text,
                line_start=buf[0].line_no,
                line_end=buf[-1].line_no,
            )
        )
        idx += 1
        buf = []
        buf_kind = None

    for ln in rows:
        if ln.kind == "blank":
            continue
        if ln.kind in _ATOMIC_KINDS:
            flush()
            units.append(
                JpContentUnit(
                    index=idx,
                    kind=ln.kind,
                    jp_lines=[ln],
                    jp_text=ln.raw.strip(),
                    line_start=ln.line_no,
                    line_end=ln.line_no,
                )
            )
            idx += 1
            continue
        if ln.kind in _MERGE_KINDS:
            if buf and buf_kind == ln.kind:
                buf.append(ln)
            else:
                flush()
                buf = [ln]
                buf_kind = ln.kind
            continue
        flush()
        units.append(
            JpContentUnit(
                index=idx,
                kind=ln.kind,
                jp_lines=[ln],
                jp_text=ln.raw.strip(),
                line_start=ln.line_no,
                line_end=ln.line_no,
            )
        )
        idx += 1
    flush()
    return units


def unit_pt_start_patterns(unit: JpContentUnit) -> list[str]:
    """Como o JP «começa» — o que procurar no PT."""
    pats: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        s = (s or "").strip()
        if len(s) >= 4 and s not in seen:
            seen.add(s)
            pats.append(s)

    if unit.kind == "session_header":
        add(jp_slice_date_pt(unit.jp_text))
        add(yamamizu_jp_date_to_pt(unit.jp_text))
        ym = yamamizu_jp_date_to_pt(unit.jp_text)
        if ym:
            add(ym.strip("()"))
            m = re.search(
                r"(\d{1,2}\s+de\s+(?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro))",
                ym,
                re.I,
            )
            if m:
                add(m.group(1))
        m = re.search(
            r"(\d{1,2}\s+de\s+(?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro))",
            unit.jp_text,
            re.I,
        )
        if m:
            add(m.group(1))
    elif unit.kind == "interlocutor":
        body = re.sub(r"^[—―–\-]{1,2}\s*", "", unit.jp_text.strip())
        add(body[:48])
        if body:
            add(f"— {body[:40]}")
            add(f"Interlocutor: {body[:40]}")

    for n in jp_session_needles(unit.jp_text):
        if len(n.strip()) >= 6:
            add(n.strip())

    first = unit.jp_text.splitlines()[0].strip() if unit.jp_text else ""
    if unit.kind == "meishu":
        add(re.sub(r"^[　\s]+", "", first)[:48])

    return pats


def _default_unit_end(start: int, unit: JpContentUnit, pt_slice: str, slice_end: int) -> int:
    """Fim do PT para unidade sem âncora seguinte — nunca engole o trecho inteiro."""
    if start >= slice_end:
        return slice_end
    chunk = pt_slice[start:slice_end]
    # Cabeçalho / intro: até fim do bloco de parágrafo
    if unit.kind in ("session_header", "poem_intro", "performance_note"):
        m = re.search(r"\n\s*\n", chunk)
        if m:
            return min(start + m.start(), slice_end)
        return min(start + max(120, len(unit.jp_text) * 4), slice_end)
    # Diálogo / verso: até próximo parágrafo ou limite proporcional ao JP
    m = re.search(r"\n\s*\n", chunk)
    cap = max(len(unit.jp_text) * 12, 80)
    if m and m.start() > 0:
        return min(start + min(m.start(), cap), slice_end)
    return min(start + cap, slice_end)


def _unit_end(
    start: int,
    unit: JpContentUnit,
    pt_slice: str,
    slice_end: int,
    starts: list[int],
    index: int,
) -> int:
    """Calcula fim da unidade; cabeçalhos nunca estendem até ao próximo header distante."""
    default_end = _default_unit_end(start, unit, pt_slice, slice_end)
    next_start = slice_end
    for j in range(index + 1, len(starts)):
        if 0 <= starts[j] > start:
            next_start = starts[j]
            break
    if unit.kind == "session_header":
        return min(next_start, default_end)
    if next_start < slice_end:
        return min(next_start, default_end)
    return default_end


def _span_disproportionate(unit: JpContentUnit, pt_len: int) -> bool:
    jp_len = max(len(unit.jp_text.strip()), 1)
    if unit.kind == "session_header":
        return pt_len > max(jp_len * 8, 180)
    if unit.kind in ("poem_line", "poem_intro", "performance_note"):
        return pt_len > max(jp_len * 16, 400)
    return pt_len > max(jp_len * 18, 600)


def _resolve_pair_overlaps(pairs: list[LinePair], pt_slice: str) -> list[LinePair]:
    """Reatribui pares sobrepostos ou desproporcionais ao fallback sequencial de parágrafos."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", pt_slice.strip()) if p.strip()]
    occupied: list[tuple[int, int]] = []
    pi = 0
    resolved: list[LinePair] = []

    def _in_occupied(pos: int) -> bool:
        return any(s <= pos < e for s, e in occupied)

    for pair in pairs:
        if pair.unit.kind == "blank":
            resolved.append(pair)
            continue

        start, end, pt = pair.pt_start, pair.pt_end, pair.pt_text
        valid = (
            0 <= start < end <= len(pt_slice)
            and not any(not (end <= s or start >= e) for s, e in occupied)
            and not _span_disproportionate(pair.unit, len(pt.strip()))
        )
        if valid:
            occupied.append((start, end))
            resolved.append(pair)
            continue

        while pi < len(paras):
            pt = paras[pi]
            pi += 1
            pos = pt_slice.find(pt) if pt else -1
            if pos >= 0 and _in_occupied(pos):
                continue
            start = pos
            end = pos + len(pt) if pos >= 0 else -1
            break
        else:
            pt, start, end = "", -1, -1

        if pt and start >= 0 and end > start and not _in_occupied(start):
            occupied.append((start, end))
        resolved.append(
            LinePair(unit=pair.unit, pt_text=pt, pt_start=start, pt_end=end, issues=pair.issues)
        )
    return resolved


def format_session_header_pt(jp_text: str) -> str:
    """Cabeçalho de sessão PT a partir das datas JP — sem API."""
    for fn in (jp_slice_date_pt, yamamizu_jp_date_to_pt):
        pt = (fn(jp_text) or "").strip()
        if pt:
            return pt
    return ""


def _repair_session_header_pairs(
    pairs: list[LinePair],
    *,
    title: str = "",
) -> tuple[list[LinePair], bool]:
    """Substitui PT errado em session_header pela data determinística JP→PT."""
    changed = False
    out: list[LinePair] = []
    for p in pairs:
        if p.unit.kind != "session_header":
            out.append(p)
            continue
        if assess_unit_pair(p.unit, p.pt_text, title=title).ok:
            out.append(p)
            continue
        header = format_session_header_pt(p.unit.jp_text)
        if not header:
            out.append(p)
            continue
        changed = True
        out.append(
            LinePair(
                unit=p.unit,
                pt_text=header,
                pt_start=p.pt_start,
                pt_end=p.pt_start + len(header) if p.pt_start >= 0 else -1,
            )
        )
    return out, changed


def align_units_to_pt(
    units: list[JpContentUnit],
    pt_slice: str,
    *,
    pt_tail: str = "",
) -> list[LinePair]:
    """Alinha unidades JP→PT dentro do slice (sem absorver pt_tail no corpo dos pares)."""
    del pt_tail  # tail é só referência de fronteira; não entra no texto dos pares
    if not units:
        return []

    slice_end = len(pt_slice)
    paras = [p.strip() for p in re.split(r"\n\s*\n", pt_slice.strip()) if p.strip()]
    n = len(units)

    # PT partido 1:1 (saída estruturada de C ou ficheiro bem segmentado)
    if len(paras) == n:
        pairs: list[LinePair] = []
        for unit, para in zip(units, paras, strict=False):
            if unit.kind == "blank":
                pairs.append(LinePair(unit=unit, pt_text="", pt_start=-1, pt_end=-1))
                continue
            pos = pt_slice.find(para)
            start = pos if pos >= 0 else 0
            end = start + len(para)
            pairs.append(LinePair(unit=unit, pt_text=para, pt_start=start, pt_end=end))
        pairs, _ = _repair_session_header_pairs(pairs)
        return pairs

    starts: list[int] = [-1] * n
    cursor = 0

    # Passagem 1: cabeçalhos de sessão (datas)
    for i, unit in enumerate(units):
        if unit.kind != "session_header":
            continue
        pats = unit_pt_start_patterns(unit)
        pos = find_pt_start(pt_slice, pats, cursor)
        if 0 <= pos < slice_end:
            starts[i] = pos
            cursor = pos + 1

    # Passagem 2: demais unidades — só dentro do slice
    cursor = 0
    for i, unit in enumerate(units):
        if unit.kind in ("session_header", "blank"):
            continue
        pats = unit_pt_start_patterns(unit)
        pos = find_pt_start(pt_slice, pats, cursor)
        if 0 <= pos < slice_end:
            starts[i] = pos
            cursor = pos + 1

    pairs: list[LinePair] = []
    pi = 0
    for i, unit in enumerate(units):
        if unit.kind == "blank":
            pairs.append(LinePair(unit=unit, pt_text="", pt_start=-1, pt_end=-1))
            continue

        start = starts[i]
        pt = ""
        end = slice_end

        if 0 <= start < slice_end:
            end = _unit_end(start, unit, pt_slice, slice_end, starts, i)
            end = min(end, slice_end)
            pt = pt_slice[start:end].strip()
        elif pi < len(paras):
            pt = paras[pi]
            pi += 1
            start = pt_slice.find(pt) if pt else -1
            end = start + len(pt) if start >= 0 else -1

        pairs.append(LinePair(unit=unit, pt_text=pt, pt_start=start, pt_end=end))
    pairs = _resolve_pair_overlaps(pairs, pt_slice)
    pairs, _ = _repair_session_header_pairs(pairs)
    return pairs


# Compatibilidade com UI/serviços antigos
pair_units_to_pt = align_units_to_pt


STRUCTURED_BLOCK_SEP = "---BLOCK---"


def _structured_kind_hint(kind: str, *, preserve_a4b: bool) -> str:
    if kind == "session_header":
        return "cabeçalho de sessão (data/título em português, ex. «18 de abril de 1948»)"
    if kind == "interlocutor":
        base = "pergunta ou fala do interlocutor"
        return f"{base}; prefixo «Interlocutor:»" if preserve_a4b else base
    if kind == "meishu":
        base = "palavras do Meishu-Sama"
        return f"{base}; prefixo «Meishu-Sama:»" if preserve_a4b else base
    if kind == "poem_line":
        return "verso de poema (uma linha)"
    if kind == "poem_intro":
        return "introdução/nota do poema"
    if kind == "performance_note":
        return "nota de execução/leitura"
    if kind == "blank":
        return "linha vazia — responda com bloco vazio"
    return kind


def format_structured_translation_request(units: list[JpContentUnit], *, preserve_a4b: bool = False) -> str:
    """Serializa unidades JP para tradução 1:1 (map_jp_lines)."""
    n = len(units)
    chunks: list[str] = []
    for i, unit in enumerate(units, start=1):
        hint = _structured_kind_hint(unit.kind, preserve_a4b=preserve_a4b)
        body = (unit.jp_text or "").strip()
        if unit.kind == "blank":
            chunks.append(f"BLOCK {i}/{n} [blank — {hint}]")
        else:
            chunks.append(f"BLOCK {i}/{n} [{unit.kind} JP L{unit.line_start}; {hint}]\n{body}")
    return f"\n{STRUCTURED_BLOCK_SEP}\n".join(chunks)


def build_structured_translate_prompt(
    units: list[JpContentUnit],
    protocol: str,
    glossary_block: str,
    *,
    title: str,
    preserve_a4b: bool,
) -> str:
    n = len(units)
    a4b_rule = (
        "- interlocutor → prefixo «Interlocutor:»; meishu → prefixo «Meishu-Sama:».\n"
        if preserve_a4b
        else "- Não adicione rótulos Interlocutor/Meishu-Sama salvo se já existirem no BLOCK.\n"
    )
    return f"""Título da sessão: {title}

Traduza do japonês para português europeu (PT-PT) cada BLOCK abaixo.

REGRAS OBRIGATÓRIAS (map_jp_lines — um parágrafo PT por unidade JP):
- Responda com exactamente {n} blocos PT, na mesma ordem dos BLOCKS JP.
- Separe cada bloco PT com a linha exacta (sozinha numa linha): {STRUCTURED_BLOCK_SEP}
- Não funda, divida nem reordene blocos.
- BLOCK [blank]: bloco PT vazio (nada entre separadores).
- session_header: só cabeçalho/data; sem diálogo.
{a4b_rule}- Versos (poem_line): uma linha PT por BLOCK.
- Responda só com o texto traduzido e os separadores — sem JSON, comentários ou metadados.

Protocolo (resumo):
{protocol[:3500]}

{glossary_block}

{format_structured_translation_request(units, preserve_a4b=preserve_a4b)}
"""


def parse_structured_pt_blocks(raw: str, expected: int) -> list[str]:
    """Extrai blocos PT 1:1; aceita separador explícito ou parágrafos duplos."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:\w+)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    sep_pat = re.compile(rf"^\s*{re.escape(STRUCTURED_BLOCK_SEP)}\s*$", re.M)
    if STRUCTURED_BLOCK_SEP in text:
        parts = [p.strip() for p in sep_pat.split(text)]
    else:
        parts = [p.strip() for p in re.split(r"\n\s*\n", text)]

    if len(parts) == expected:
        return [sanitize_turn_text(p) for p in parts]

    if len(parts) > expected and expected > 0:
        head = [sanitize_turn_text(p) for p in parts[: expected - 1]]
        tail = sanitize_turn_text("\n\n".join(parts[expected - 1 :]))
        return head + [tail]

    if len(parts) < expected:
        parts = parts + [""] * (expected - len(parts))
        return [sanitize_turn_text(p) for p in parts]

    raise ValueError(f"blocos PT={len(parts)} ≠ unidades JP={expected}")


def _postprocess_structured_block(block: str, kind: str, *, preserve_a4b: bool, jp_text: str = "") -> str:
    if kind == "session_header" and jp_text.strip():
        header = format_session_header_pt(jp_text)
        if header:
            return header
    out = sanitize_turn_text(block)
    if not out:
        return ""
    if preserve_a4b and kind == "interlocutor":
        out = re.sub(r"^[—―–\-]{1,2}\s*", "", out)
        if not out.lower().startswith("interlocutor:"):
            out = re.sub(r"^Interlocutor:\s*", "", out, flags=re.I)
    elif preserve_a4b and kind == "meishu":
        if not out.lower().startswith("meishu-sama:"):
            out = re.sub(r"^Meishu-Sama:\s*", "", out, flags=re.I)
    return out.strip()


def build_pairs_and_slice_from_structured(
    units: list[JpContentUnit],
    blocks: list[str],
    *,
    preserve_a4b: bool,
) -> tuple[str, list[LinePair]]:
    """Monta pt_slice e pares posicionais 1:1 (PT já nasce partido como JP)."""
    slice_parts: list[str] = []
    pairs: list[LinePair] = []
    cursor = 0

    for unit, block in zip(units, blocks, strict=False):
        body = _postprocess_structured_block(block, unit.kind, preserve_a4b=preserve_a4b, jp_text=unit.jp_text)
        stub = LinePair(unit=unit, pt_text=body)
        formatted = _format_pair_pt(stub, body, preserve_a4b)

        if unit.kind == "blank" or not formatted:
            pairs.append(LinePair(unit=unit, pt_text="", pt_start=-1, pt_end=-1))
            continue

        if slice_parts:
            cursor += 2
        start = cursor
        slice_parts.append(formatted)
        cursor += len(formatted)
        pairs.append(
            LinePair(unit=unit, pt_text=formatted, pt_start=start, pt_end=cursor)
        )

    pt_slice = trim_pt_chunk_leakage("\n\n".join(slice_parts).strip()) + "\n"
    return pt_slice, pairs


def translate_segment_structured(
    units: list[JpContentUnit],
    *,
    title: str,
    preserve_a4b: bool,
) -> list[str]:
    """Retraduz o trecho inteiro com saída partida 1:1 por unidade map_jp_lines."""
    from run_deepseek_revision_pilot import (  # noqa: WPS433
        format_glossary_block,
        load_env_api_key,
        load_glossary,
    )
    from run_translation_warn_pilot import DeepSeekClient  # noqa: WPS433
    from retranslate_core import MAX_OUTPUT_TOKENS, call_deepseek  # noqa: WPS433
    from translation_protocol_core import (  # noqa: WPS433
        PROTOCOL_PATH,
        extract_prose_from_response,
        select_glossary_entries,
    )

    jp_all = "\n".join(u.jp_text for u in units if u.jp_text.strip())
    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    glossary = load_glossary()
    gloss = format_glossary_block(select_glossary_entries(jp_all, glossary))
    prompt = build_structured_translate_prompt(
        units, protocol, gloss, title=title, preserve_a4b=preserve_a4b
    )
    client = DeepSeekClient(api_key=load_env_api_key())
    raw, _usage = call_deepseek(client, prompt, max_tokens=MAX_OUTPUT_TOKENS)
    prose = extract_prose_from_response(raw)
    return parse_structured_pt_blocks(prose, len(units))


def _segment_candidate_to_pairs_and_slice(
    units: list[JpContentUnit],
    pt_text: str,
    *,
    preserve_a4b: bool,
) -> tuple[str, list[LinePair]]:
    """Converte PT de trecho inteiro em pares 1:1 — parágrafos ou alinhamento posicional."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", (pt_text or "").strip()) if p.strip()]
    if len(paras) == len(units):
        return build_pairs_and_slice_from_structured(units, paras, preserve_a4b=preserve_a4b)
    pairs = align_units_to_pt(units, pt_text.strip() + "\n")
    return pt_text.strip() + "\n", pairs


def _finalize_segment_blocks(
    units: list[JpContentUnit],
    blocks: list[str],
    jp_slice: str,
    *,
    title: str,
    preserve_a4b: bool,
    segment_index: int,
    bound: Boundary,
    original_pt_len: int,
    bad_before: int,
    log: Callable[[str], None],
    source: str,
) -> tuple[bool, str, list[LinePair], int]:
    """Valida blocos 1:1; ok só quando 0 unidades com problemas."""
    candidate, _struct_pairs = build_pairs_and_slice_from_structured(
        units, blocks, preserve_a4b=preserve_a4b
    )
    safe, why = pt_slice_safe_to_persist(
        jp_slice, candidate, segment_index, bound, original_pt_len=original_pt_len
    )
    if not safe:
        log(f"  [C] rejeitado ({source}) — {why[0] if why else 'slice inválido'}")
        return False, candidate, _struct_pairs, bad_before

    # Validar como no disco: realinhar posicionalmente o PT persistível
    pairs = align_units_to_pt(units, candidate)
    bad_after = sum(
        1
        for p in pairs
        if not assess_unit_pair(
            p.unit, p.pt_text, title=title, require_a4b=preserve_a4b
        ).ok
    )
    log(f"  [C] {source}: {len(units)} unidades | problemas {bad_before}→{bad_after}")
    if bad_after == 0:
        log(f"  [C] trecho OK ({source}) — PT alinhado 1:1 com JP")
        return True, candidate, pairs, 0
    if bad_after > bad_before:
        log(f"  [C] rejeitado ({source}) — piorou ({bad_before}→{bad_after})")
    return False, candidate, pairs, bad_after


def _fix_remaining_unit_blocks(
    filename: str,
    units: list[JpContentUnit],
    blocks: list[str],
    *,
    title: str,
    preserve_a4b: bool,
    profile: str,
    translate: bool,
    max_fixes: int,
    log: Callable[[str], None],
) -> tuple[list[str], int, int]:
    """Ajuste linha a linha das unidades que o trecho inteiro não resolveu."""
    from a4b_assessment import format_a4b_turn, profile_requires_a4b  # noqa: WPS433

    require_a4b = profile_requires_a4b(profile)
    api_n = corpus_n = 0
    blocks = list(blocks)
    while len(blocks) < len(units):
        blocks.append("")

    from line_pair_assessment import (  # noqa: WPS433
        assessment_acceptable_for_autofix,
        assessment_needs_autofix,
    )

    for _ in range(max_fixes):
        pairs = build_pairs_and_slice_from_structured(units, blocks, preserve_a4b=preserve_a4b)[1]
        bad_i = None
        for i, p in enumerate(pairs):
            if p.unit.kind == "blank":
                continue
            asm = assess_unit_pair(p.unit, p.pt_text, title=title, require_a4b=require_a4b)
            if assessment_needs_autofix(asm):
                bad_i = i
                break
        if bad_i is None:
            break

        u = units[bad_i]
        note = assess_unit_pair(
            u, pairs[bad_i].pt_text, title=title, require_a4b=require_a4b
        ).editorial_note
        log(f"  [C] L{u.line_start} ({u.kind}) — {note[:80]}")

        sr = search_exhaustive_pt_for_unit(filename, u, profile=profile, title=title)
        for line in sr.log:
            log(f"  {line}")

        new_pt: str | None = None
        if u.kind == "session_header":
            header = format_session_header_pt(u.jp_text)
            if header:
                asm = assess_unit_pair(u, header, title=title)
                if assessment_acceptable_for_autofix(asm):
                    new_pt = header
                    log(f"  [C] L{u.line_start} ← data JP ({header[:40]})")
        if not new_pt and pairs[bad_i].pt_text and require_a4b and u.kind in ("interlocutor", "meishu"):
            cand = format_a4b_turn(u.kind, pairs[bad_i].pt_text)
            asm = assess_unit_pair(u, cand, title=title, require_a4b=require_a4b)
            if assessment_acceptable_for_autofix(asm):
                new_pt = cand
                log(f"  [C] L{u.line_start} ← rótulo A4B")
        if sr.pt_text:
            cand = sr.pt_text
            if require_a4b and u.kind in ("interlocutor", "meishu"):
                cand = format_a4b_turn(u.kind, cand)
            asm = assess_unit_pair(u, cand, title=title, require_a4b=require_a4b)
            if assessment_acceptable_for_autofix(asm):
                new_pt = cand
                corpus_n += 1
                log(f"  [C] L{u.line_start} ← corpus ({sr.source})")
        if not new_pt and translate:
            try:
                new_pt = translate_unit_full(u.jp_text, title=title, kind=u.kind)
                if require_a4b and u.kind in ("interlocutor", "meishu"):
                    new_pt = format_a4b_turn(u.kind, new_pt)
                asm = (
                    assess_unit_pair(u, new_pt, title=title, require_a4b=require_a4b)
                    if new_pt
                    else None
                )
                if asm and assessment_acceptable_for_autofix(asm):
                    api_n += 1
                    log(f"  [C] L{u.line_start} ← API ({len(new_pt)} chars)")
                elif asm and asm.needs_human:
                    note2 = asm.human_doubt or asm.editorial_note
                    log(f"  [C] L{u.line_start} dúvida semântica — {note2[:80]}")
                    new_pt = None
                else:
                    note2 = asm.editorial_note if asm else "vazio"
                    log(f"  [C] L{u.line_start} tradução rejeitada — {note2[:80]}")
                    new_pt = None
            except Exception as exc:
                log(f"  [C] L{u.line_start} falhou: {exc}")

        if not new_pt:
            break
        blocks[bad_i] = new_pt

    return blocks, api_n, corpus_n


def _adopt_segment_candidate(
    candidate: str,
    units: list[JpContentUnit],
    jp_slice: str,
    *,
    title: str,
    preserve_a4b: bool,
    segment_index: int,
    bound: Boundary,
    original_pt_len: int,
    bad_before: int,
    log: Callable[[str], None],
    source: str,
) -> tuple[bool, str, list[LinePair], int]:
    """Valida candidato de trecho inteiro; substituição directa sem rebuild."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", (candidate or "").strip()) if p.strip()]
    if len(paras) == len(units):
        blocks = paras
    else:
        blocks = [p.pt_text for p in align_units_to_pt(units, candidate.strip() + "\n")]
    ok, pt_out, pairs, _bad = _finalize_segment_blocks(
        units,
        blocks,
        jp_slice,
        title=title,
        preserve_a4b=preserve_a4b,
        segment_index=segment_index,
        bound=bound,
        original_pt_len=original_pt_len,
        bad_before=bad_before,
        log=log,
        source=source,
    )
    return ok, pt_out if ok else candidate, pairs, _bad


def search_exhaustive_pt_for_segment(
    filename: str,
    segment_index: int,
    jp_body: str,
    jp_slice: str,
    units: list[JpContentUnit],
    spec: dict[str, Any],
    *,
    title: str,
    bound: Boundary,
    preserve_a4b: bool,
    original_pt_len: int,
    bad_before: int,
    log: Callable[[str], None],
) -> tuple[bool, str, list[LinePair]]:
    """Busca PT do trecho inteiro nos corpus — extrai slice e substitui sem remontagem."""
    from protocol_line_revision import SearchResult, _pt_sources, _read_pt_file  # noqa: WPS433

    del SearchResult
    seen_body: set[str] = set()
    seen_candidate: set[str] = set()
    for label, path in _pt_sources(filename):
        log(f"  [C] busca trecho: {label} ({path.name})")
        try:
            body = _read_pt_file(path)
        except OSError as exc:
            log(f"    erro leitura: {exc}")
            continue
        if not body.strip():
            log("    vazio")
            continue
        body_key = hashlib.sha256(body.encode()).hexdigest()
        if body_key in seen_body:
            log("    ignorado — conteúdo duplicado")
            continue
        seen_body.add(body_key)

        try:
            invalidate_slice_cache(filename)
            _jp_slices, pt_slices = get_volume_slices(filename, jp_body, body, spec)
        except Exception as exc:
            log(f"    erro separação: {exc}")
            continue

        if segment_index >= len(pt_slices):
            log("    trecho ausente")
            continue

        candidate = pt_slices[segment_index]
        if not candidate.strip():
            log("    trecho PT vazio")
            continue

        cand_key = hashlib.sha256(candidate.strip().encode()).hexdigest()
        if cand_key in seen_candidate:
            log("    ignorado — trecho já testado")
            continue
        seen_candidate.add(cand_key)

        slice_ok, slice_issues = validate_segment_slice(
            jp_slice,
            candidate,
            segment_index,
            title=bound.title_pt or bound.title_jp or "",
            kind=getattr(bound, "kind", "") or "",
        )
        if not slice_ok:
            log(f"    rejeitado — {slice_issues[0][:72]}")
            continue

        ok, pt_out, pairs, bad_after = _adopt_segment_candidate(
            candidate,
            units,
            jp_slice,
            title=title,
            preserve_a4b=preserve_a4b,
            segment_index=segment_index,
            bound=bound,
            original_pt_len=original_pt_len,
            bad_before=bad_before,
            log=log,
            source=label,
        )
        if ok:
            return True, pt_out, pairs
        if bad_after > bad_before:
            log("  [C] corpus piora pareamento — skip restantes snapshots")
            break

    log("  [C] busca de trecho concluída — sem correspondente")
    return False, "", []


def try_whole_segment_replace(
    filename: str,
    segment_index: int,
    jp_body: str,
    jp_slice: str,
    units: list[JpContentUnit],
    spec: dict[str, Any],
    pt_slice: str,
    *,
    title: str,
    preserve_a4b: bool,
    bound: Boundary,
    original_pt_len: int,
    bad_before: int,
    log: Callable[[str], None],
    profile: str = "gokowa_roku_qa",
    max_unit_fixes: int = 12,
) -> tuple[bool, str, list[LinePair], int, int]:
    """C: busca trecho → API estruturada → ajuste linha a linha do resto."""
    log(f"  [C] correção ({len(units)} unidades; {bad_before} com problemas)")

    skip_corpus = getattr(bound, "kind", "") == "preface" or not any(
        u.kind in ("interlocutor", "meishu") for u in units
    )
    if not skip_corpus and units and bad_before >= 3:
        log(
            f"  [C] {bad_before}/{len(units)} unidades com problemas — "
            "API directa (skip busca corpus)"
        )
        skip_corpus = True
    ok = False
    pt_out = ""
    pairs: list[LinePair] = []
    if not skip_corpus:
        ok, pt_out, pairs = search_exhaustive_pt_for_segment(
            filename,
            segment_index,
            jp_body,
            jp_slice,
            units,
            spec,
            title=title,
            bound=bound,
            preserve_a4b=preserve_a4b,
            original_pt_len=original_pt_len,
            bad_before=bad_before,
            log=log,
        )
        if ok:
            return True, pt_out, pairs, 0, 1
    else:
        log("  [C] skip busca corpus — retradução API")

    log("  [C] corpus sem trecho — retradução do trecho inteiro (API)")
    api_n = 0
    corpus_n = 0
    try:
        blocks = translate_segment_structured(units, title=title, preserve_a4b=preserve_a4b)
        api_n = 1
    except Exception as exc:
        log(f"  [C] API falhou — {exc}")
        return False, pt_slice, [], 0, 0

    ok, pt_out, pairs, bad_after = _finalize_segment_blocks(
        units,
        blocks,
        jp_slice,
        title=title,
        preserve_a4b=preserve_a4b,
        segment_index=segment_index,
        bound=bound,
        original_pt_len=original_pt_len,
        bad_before=bad_before,
        log=log,
        source="API estruturada",
    )
    if ok:
        return True, pt_out, pairs, api_n, corpus_n

    if bad_after > 0:
        log(f"  [C] ajustar {bad_after} unidade(s) linha a linha")
        blocks, fix_api, fix_corpus = _fix_remaining_unit_blocks(
            filename,
            units,
            blocks,
            title=title,
            preserve_a4b=preserve_a4b,
            profile=profile,
            translate=True,
            max_fixes=max_unit_fixes,
            log=log,
        )
        api_n += fix_api
        corpus_n += fix_corpus
        ok, pt_out, pairs, _bad = _finalize_segment_blocks(
            units,
            blocks,
            jp_slice,
            title=title,
            preserve_a4b=preserve_a4b,
            segment_index=segment_index,
            bound=bound,
            original_pt_len=original_pt_len,
            bad_before=bad_after,
            log=log,
            source="API + ajuste linha a linha",
        )
        if ok:
            return True, pt_out, pairs, api_n, corpus_n

    # Retradução estruturada 1:1 — adopta se persistível (corrige pareamento JP↔PT)
    if api_n > 0 and len(blocks) == len(units):
        candidate, struct_pairs = build_pairs_and_slice_from_structured(
            units, blocks, preserve_a4b=preserve_a4b
        )
        safe, why = pt_slice_safe_to_persist(
            jp_slice, candidate, segment_index, bound, original_pt_len=original_pt_len
        )
        if safe:
            bad_final = sum(
                1
                for p in struct_pairs
                if not assess_unit_pair(
                    p.unit, p.pt_text, title=title, require_a4b=preserve_a4b
                ).ok
            )
            log(
                f"  [C] adoção retradução 1:1 — realinhamento "
                f"({bad_before}→{bad_final} flags)"
            )
            return True, candidate, struct_pairs, api_n, corpus_n
        log(f"  [C] retradução 1:1 não gravada — {why[0] if why else 'slice inválido'}")

    return False, pt_slice, [], api_n, corpus_n


def translate_unit_full(jp_text: str, *, title: str, kind: str) -> str:
    from run_deepseek_revision_pilot import load_env_api_key, load_glossary  # noqa: WPS433
    from run_translation_warn_pilot import DeepSeekClient  # noqa: WPS433
    from translation_protocol_core import PROTOCOL_PATH, review_pt_text, translate_jp_text  # noqa: WPS433
    from retranslate_qa import validate_translation  # noqa: WPS433

    if kind == "session_header":
        header = format_session_header_pt(jp_text)
        if header:
            return header

    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    glossary = load_glossary()
    client = DeepSeekClient(api_key=load_env_api_key())

    src = jp_text.strip()
    if kind == "interlocutor" and not src.startswith(("――", "—", "（")):
        src = f"―― {src}"

    draft, _, _ = translate_jp_text(client, src, protocol, glossary, title=title, chunk_delay=0.15)
    final, _, _ = review_pt_text(client, src, draft, protocol, glossary)
    final, qa = validate_translation(src, final, sanitize=True)
    if not qa.ok and "japones_residual" in str(qa.issues):
        raise RuntimeError(f"retranslate_qa: {qa.issues}")
    out = sanitize_turn_text(final)
    if kind == "interlocutor":
        out = re.sub(r"^[—―–\-]{1,2}\s*", "", out)
        out = re.sub(r"^Interlocutor:\s*", "", out, flags=re.I)
    elif kind == "meishu":
        out = re.sub(r"^Meishu-Sama:\s*", "", out, flags=re.I)
    return out.strip()


def translate_unit_with_instruction(
    jp_text: str,
    *,
    title: str,
    kind: str,
    instruction: str = "",
    pt_reference: str = "",
) -> str:
    """Retraduz uma unidade com orientação do tradutor humano."""
    from run_deepseek_revision_pilot import format_glossary_block, load_env_api_key, load_glossary  # noqa: WPS433
    from run_translation_warn_pilot import DeepSeekClient  # noqa: WPS433
    from retranslate_core import MAX_OUTPUT_TOKENS, call_deepseek  # noqa: WPS433
    from translation_protocol_core import PROTOCOL_PATH, extract_prose_from_response, select_glossary_entries  # noqa: WPS433
    from retranslate_qa import validate_translation  # noqa: WPS433

    if kind == "session_header":
        header = format_session_header_pt(jp_text)
        if header:
            return header

    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    glossary = load_glossary()
    client = DeepSeekClient(api_key=load_env_api_key())

    src = jp_text.strip()
    if kind == "interlocutor" and not src.startswith(("――", "—", "（")):
        src = f"―― {src}"

    gloss = format_glossary_block(select_glossary_entries(src, glossary))
    extra = ""
    if pt_reference.strip():
        extra += f"\n\nTradução portuguesa actual (referência — pode estar errada):\n{pt_reference.strip()}"
    if instruction.strip():
        extra += f"\n\nInstrução do tradutor humano:\n{instruction.strip()}"

    prompt = f"""{protocol}

---

Glossário (termos relevantes):
{gloss}

Título / contexto: {title}
Tipo de unidade: {kind}

Traduza para português brasileiro o seguinte excerto japonês.
Responda APENAS com o texto traduzido, sem comentários.{extra}

Japonês:
{src}
"""
    raw, _usage = call_deepseek(client, prompt, max_tokens=MAX_OUTPUT_TOKENS)
    final = extract_prose_from_response(raw)
    final, qa = validate_translation(src, final, sanitize=True)
    if not qa.ok and "japones_residual" in str(qa.issues):
        raise RuntimeError(f"retranslate_qa: {qa.issues}")
    out = sanitize_turn_text(final)
    if kind == "interlocutor":
        out = re.sub(r"^[—―–\-]{1,2}\s*", "", out)
        out = re.sub(r"^Interlocutor:\s*", "", out, flags=re.I)
    elif kind == "meishu":
        out = re.sub(r"^Meishu-Sama:\s*", "", out, flags=re.I)
    return out.strip()


def _strip_a4b(para: str) -> tuple[str, str]:
    if para.startswith("Interlocutor:"):
        return "Interlocutor", para[len("Interlocutor:") :].strip()
    if para.startswith("Meishu-Sama:"):
        return "Meishu-Sama", para[len("Meishu-Sama:") :].strip()
    return "", para


def _format_pair_pt(pair: LinePair, pt: str, preserve_a4b: bool) -> str:
    pt = sanitize_turn_text(pt)
    if not pt:
        return ""
    kind = pair.unit.kind
    if preserve_a4b and kind == "interlocutor":
        _l, body = _strip_a4b(pt)
        body = re.sub(r"^[—―–\-]{1,2}\s*", "", body)
        return f"Interlocutor: {body if body else pt}"
    if preserve_a4b and kind == "meishu":
        _l, body = _strip_a4b(pt)
        return f"Meishu-Sama: {body if body else pt}"
    return pt


def resolve_preserve_a4b(profile: str, pt_slice: str) -> bool:
    """Perfis QA exigem §4.4-B; senão segue formato já presente no trecho."""
    from a4b_assessment import profile_requires_a4b  # noqa: WPS433

    if profile_requires_a4b(profile):
        return True
    return _slice_uses_a4b_labels(pt_slice)


def _pairs_overlap(anchored: list[LinePair]) -> bool:
    prev = -1
    for pair in anchored:
        if pair.pt_start < prev:
            return True
        prev = pair.pt_end
    return False


def rebuild_pt_from_pairs(
    pairs: list[LinePair],
    *,
    preserve_a4b: bool,
    source_slice: str = "",
) -> str:
    """Reconstrói trecho PT — merge posicional quando possível; senão junção deduplicada."""
    source = (source_slice or "").strip("\n")
    anchored = sorted(
        (p for p in pairs if p.pt_start >= 0 and p.pt_end > p.pt_start),
        key=lambda p: p.pt_start,
    )
    if source and anchored and not _pairs_overlap(anchored):
        parts: list[str] = []
        cursor = 0
        for pair in anchored:
            if pair.pt_start > cursor:
                gap = source[cursor:pair.pt_start].strip()
                if gap:
                    parts.append(gap)
            text = sanitize_turn_text(pair.pt_text) or source[pair.pt_start : pair.pt_end].strip()
            block = _format_pair_pt(pair, text, preserve_a4b)
            if block:
                parts.append(block)
            cursor = max(cursor, pair.pt_end)
        if cursor < len(source):
            tail = source[cursor:].strip()
            if tail:
                parts.append(tail)
        return trim_pt_chunk_leakage("\n\n".join(p for p in parts if p).strip()) + "\n"

    blocks: list[str] = []
    seen: list[str] = []
    for pair in pairs:
        pt = sanitize_turn_text(pair.pt_text)
        if not pt:
            continue
        if any((pt in s or s in pt) and len(s) > 40 for s in seen):
            continue
        block = _format_pair_pt(pair, pt, preserve_a4b)
        if block:
            blocks.append(block)
            seen.append(pt)
    if source:
        max_end = max((p.pt_end for p in pairs if p.pt_end > 0), default=0)
        if max_end < len(source):
            tail = source[max_end:].strip()
            if tail and not any(tail in s or s in tail for s in seen if len(s) > 40):
                blocks.append(tail)
    return trim_pt_chunk_leakage("\n\n".join(blocks).strip()) + "\n"


def _slice_uses_a4b_labels(pt_slice: str) -> bool:
    """Trecho usa formato Interlocutor/Meishu-Sama de forma consistente (não uma ocorrência solta)."""
    n_i = pt_slice.count("Interlocutor:")
    n_m = pt_slice.count("Meishu-Sama:")
    return n_i >= 2 or (n_i >= 1 and n_m >= 1)


def pt_slice_safe_to_persist(
    jp_slice: str,
    pt_slice: str,
    segment_index: int,
    bound: Boundary,
    *,
    original_pt_len: int,
) -> tuple[bool, list[str]]:
    """Validação estrutural da saída — mesma regra da fase A + limite de crescimento."""
    ok, issues = validate_segment_slice(
        jp_slice,
        pt_slice,
        segment_index,
        title=bound.title_pt or bound.title_jp or "",
        kind=getattr(bound, "kind", "") or "",
    )
    if not ok:
        return False, issues
    pt_len = len((pt_slice or "").strip())
    jp_len = len((jp_slice or "").strip())
    # Tecto duro ancorado no JP (fonte estável, nunca corrompida por uma
    # tentativa anterior) — 4× o comprimento JP já é uma folga generosa acima
    # do rácio empírico PT/JP observado neste corpus (~2.3-2.4×). `original_pt_len`
    # só pode ESTREITAR este tecto (permitir menos crescimento quando o PT de
    # partida já era substancial), nunca alargá-lo: usá-lo para alargar foi a
    # causa raiz de uma corrupção em cadeia — cada retentativa lia de disco um
    # `original_pt_len` já inflado pela tentativa anterior, e o tecto (1.35×
    # esse valor) subia junto, nunca travando a duplicação progressiva do trecho.
    hard_cap = max(int(jp_len * 4), 800)
    cap = hard_cap
    if 0 < original_pt_len < hard_cap:
        cap = max(int(original_pt_len * 1.35), int(jp_len * 2.5), 400)
        cap = min(cap, hard_cap)
    if pt_len > cap:
        issues = issues + [
            f"PT saída cresceu além do limite ({pt_len} chars; teto {cap}; entrada {original_pt_len}; jp {jp_len})"
        ]
        return False, issues
    return True, []


def search_exhaustive_pt_for_unit(
    filename: str,
    unit: JpContentUnit,
    *,
    profile: str = "gokowa_roku_qa",
    title: str = "",
) -> Any:
    from line_pair_assessment import prefilter_unit_pair  # noqa: WPS433
    from protocol_line_revision import (  # noqa: WPS433
        SearchResult,
        _extract_pt_paragraph_at_needles,
        _pt_sources,
        _read_pt_file,
    )

    from a4b_assessment import format_a4b_turn, profile_requires_a4b  # noqa: WPS433

    require_a4b = profile_requires_a4b(profile)
    res = SearchResult()
    header_pats = unit_pt_start_patterns(unit) if unit.kind == "session_header" else []

    for label, path in _pt_sources(filename):
        res.log.append(f"  busca: {label} ({path.name})")
        try:
            body = _read_pt_file(path)
        except OSError as exc:
            res.log.append(f"    erro leitura: {exc}")
            continue
        if not body.strip():
            res.log.append("    vazio")
            continue

        candidate: str | None = None
        if header_pats:
            pos = find_pt_start(body, header_pats, 0)
            if pos >= 0:
                end = body.find("\n\n", pos)
                end = len(body) if end < 0 else end
                candidate = body[pos:end].strip()

        if not candidate:
            candidate = _extract_pt_paragraph_at_needles(body, unit.jp_text)

        if not candidate:
            res.log.append("    não encontrado")
            continue

        if prefilter_unit_pair(unit.kind, candidate) is not None:
            res.log.append("    rejeitado (pré-filtro)")
            continue

        if require_a4b and unit.kind in ("interlocutor", "meishu"):
            candidate = format_a4b_turn(unit.kind, candidate)

        assessment = assess_unit_pair(
            unit, candidate, title=title, require_a4b=require_a4b
        )
        if assessment.ok:
            res.pt_text = candidate
            res.source = label
            res.log.append(f"    ENCONTRADO ({len(candidate)} chars)")
            return res
        res.log.append(f"    rejeitado — {assessment.editorial_note[:72]}")

    res.log.append("  busca exaustiva concluída — sem correspondente")
    return res


def validate_segment_line_by_line(
    jp_slice: str,
    pt_slice: str,
    pairs: list[LinePair],
    *,
    filename: str,
    bound: Boundary,
    profile: str,
    segment_index: int = 0,
) -> tuple[bool, list[str], list[str]]:
    """Checklist fase D — blocking só para dúvida semântica; mecânico vai para autofix."""
    review = classify_segment_review(
        jp_slice,
        pt_slice,
        pairs,
        filename=filename,
        bound=bound,
        profile=profile,
        segment_index=segment_index,
    )
    blocking = bool(review.get("needs_human"))
    issues = list(review.get("issues") or [])
    notes = list(review.get("notes") or [])
    return blocking, issues, notes


def classify_segment_review(
    jp_slice: str,
    pt_slice: str,
    pairs: list[LinePair],
    *,
    filename: str,
    bound: Boundary,
    profile: str,
    segment_index: int = 0,
) -> dict[str, Any]:
    """Separa dúvidas semânticas (humano) de inconsistências mecânicas (agente)."""
    from a4b_assessment import profile_requires_a4b  # noqa: WPS433
    from line_pair_assessment import assess_unit_pair  # noqa: WPS433

    require_a4b = profile_requires_a4b(profile)
    title = bound.title_jp or bound.title_pt or ""
    slice_ok, slice_issues = validate_segment_slice(
        jp_slice,
        pt_slice,
        segment_index,
        title=bound.title_pt or bound.title_jp or "",
        kind=getattr(bound, "kind", "") or "",
    )

    needs_human = False
    mechanical = not slice_ok
    issues: list[str] = []
    notes: list[str] = list(slice_issues)
    human_indices: list[int] = []
    mechanical_indices: list[int] = []

    if not slice_ok and ISSUE_ALIGN not in issues:
        issues.append(ISSUE_ALIGN)

    for i, pair in enumerate(pairs):
        if pair.unit.kind == "blank":
            continue
        assessment = assess_unit_pair(
            pair.unit,
            pair.pt_text,
            title=title,
            require_a4b=require_a4b,
        )
        if assessment.needs_human:
            needs_human = True
            human_indices.append(i)
            if "needs_human" not in issues:
                issues.append("needs_human")
            notes.append(
                f"JP L{pair.unit.line_start}-{pair.unit.line_end} ({pair.unit.kind}): "
                f"{assessment.human_doubt or assessment.editorial_note}"
            )
        elif not assessment.ok:
            mechanical = True
            mechanical_indices.append(i)
            if "label_mismatch" in assessment.issues:
                key = "label_mismatch"
            elif "desalinhamento" in assessment.issues or "traducao_incompleta" in assessment.issues:
                key = ISSUE_ALIGN
            elif "cjk_residual" in assessment.issues:
                key = ISSUE_CJK
            else:
                key = ISSUE_NO_PT
            if key not in issues:
                issues.append(key)
            notes.append(
                f"JP L{pair.unit.line_start}-{pair.unit.line_end} ({pair.unit.kind}): "
                f"{assessment.editorial_note}"
            )

    if has_blocking_cjk(pt_slice) and ISSUE_CJK not in issues:
        mechanical = True
        issues.append(ISSUE_CJK)
        notes.append("CJK bloqueante no trecho")

    return {
        "needs_human": needs_human,
        "mechanical": mechanical and not needs_human,
        "approved": not needs_human and not mechanical,
        "issues": issues,
        "notes": notes,
        "human_indices": human_indices,
        "mechanical_indices": mechanical_indices,
    }


def extract_segment_slices(
    filename: str,
    segment_index: int,
    jp_body: str,
    pt_body: str,
    spec: dict[str, Any],
) -> tuple[str, str, dict[str, int]]:
    """Trecho JP/PT via separação sequencial (line_by_line_slices)."""
    jp_slices, pt_slices = get_volume_slices(filename, jp_body, pt_body, spec)
    if segment_index >= len(jp_slices):
        raise IndexError(segment_index)
    from line_by_line_slices import _SLICE_CACHE  # noqa: WPS433

    bounds = _SLICE_CACHE.get(filename, {}).get("bounds") or [Boundary.from_article(a) for a in spec.get("articles") or []]
    art = bounds[segment_index] if segment_index < len(bounds) else None
    lr = getattr(art, "line_range_jp", None) if art else None
    if not lr or not isinstance(lr, dict) or not lr.get("start"):
        lr = {"start": 0, "end": 0}
    return jp_slices[segment_index], pt_slices[segment_index], lr


def pt_slice_tail_for_align(
    filename: str,
    segment_index: int,
    jp_body: str,
    pt_body: str,
    spec: dict[str, Any],
    *,
    max_chars: int = 500,
) -> str:
    """Início do trecho PT seguinte — cabeçalhos de sessão na fronteira JP/PT."""
    jp_slices, pt_slices = get_volume_slices(filename, jp_body, pt_body, spec)
    nxt = segment_index + 1
    if nxt >= len(pt_slices):
        return ""
    return pt_slices[nxt][:max_chars]


def process_segment_line_by_line(
    filename: str,
    segment_index: int,
    jp_body: str,
    pt_body: str,
    spec: dict[str, Any],
    *,
    translate: bool = True,
    max_translate: int = 40,
    log_fn: Callable[[str], None] | None = None,
) -> SegmentProtocolResult:
    log = log_fn or (lambda _m: None)
    profile = spec.get("profile") or "gokowa_roku_qa"
    bounds = [Boundary.from_article(a) for a in spec.get("articles") or []]
    bound = bounds[segment_index] if segment_index < len(bounds) else Boundary(kind="session", title_jp="", jp_anchor="")

    res = SegmentProtocolResult(jp_slice="", pt_slice="")

    log("  [A] map_jp_lines + separação sequencial de trecho")
    invalidate_slice_cache(filename)
    jp_slice, pt_slice, _ = extract_segment_slices(filename, segment_index, jp_body, pt_body, spec)
    pt_tail = pt_slice_tail_for_align(filename, segment_index, jp_body, pt_body, spec)
    res.jp_slice = jp_slice
    res.pt_slice = pt_slice
    units = build_jp_content_units(jp_slice)
    res.phase_log.append(f"A: {len(units)} unidades JP")
    log(f"  [A] {len(units)} unidades JP, PT trecho {len(pt_slice)} chars")

    title = bound.title_jp or bound.title_pt or filename

    from a4b_assessment import profile_requires_a4b  # noqa: WPS433

    require_a4b = profile_requires_a4b(profile)
    preserve_a4b = resolve_preserve_a4b(profile, pt_slice)

    slice_ok, slice_issues = validate_segment_slice(
        jp_slice,
        pt_slice,
        segment_index,
        title=bound.title_pt or bound.title_jp or "",
        kind=getattr(bound, "kind", "") or "",
    )
    if not slice_ok:
        for msg in slice_issues:
            log(f"  [A] slice inválido — {msg}")
        res.blocking = True
        res.slice_invalid = True
        res.review_issues = [ISSUE_ALIGN]
        res.review_notes = slice_issues
        res.phase_log.append(f"A: slice inválido — {len(slice_issues)} problema(s)")
        return res

    log("  [B] alinhar PT sequencialmente (início JP → início PT, fim = próximo)")
    pairs = align_units_to_pt(units, pt_slice, pt_tail=pt_tail)
    has_dialogue = any(u.kind in ("interlocutor", "meishu") for u in units)
    if preserve_a4b and has_dialogue:
        log("  [B] aplicar rótulos §4.4-B (Interlocutor:/Meishu-Sama:)")
        pt_slice = rebuild_pt_from_pairs(pairs, preserve_a4b=True, source_slice=pt_slice)
        pairs = align_units_to_pt(units, pt_slice, pt_tail=pt_tail)
    for pair in pairs:
        assessment = assess_unit_pair(
            pair.unit, pair.pt_text, title=title, require_a4b=require_a4b
        )
        if not assessment.ok:
            log(f"  [B] JP L{pair.unit.line_start} ({pair.unit.kind}) — {assessment.editorial_note}")
    tr0 = sum(
        1
        for p in pairs
        if not assess_unit_pair(p.unit, p.pt_text, title=title, require_a4b=require_a4b).ok
    )
    res.phase_log.append(f"B: {tr0}/{len(pairs)} unidades com problemas")
    log(f"  [B] triagem {tr0}/{len(pairs)} unidades com problemas")

    if tr0 == 0:
        pt_slice = rebuild_pt_from_pairs(
            pairs, preserve_a4b=preserve_a4b, source_slice=pt_slice
        )
    original_pt = pt_slice
    original_pt_len = len(pt_slice.strip())
    translated_n = 0
    corpus_n = 0
    structured_used = False

    if tr0 > 0 and translate:
        ok_c, pt_slice, pairs, api_n, corp_n = try_whole_segment_replace(
            filename,
            segment_index,
            jp_body,
            jp_slice,
            units,
            spec,
            pt_slice,
            title=title,
            preserve_a4b=preserve_a4b,
            bound=bound,
            original_pt_len=original_pt_len,
            bad_before=tr0,
            log=log,
            profile=profile,
            max_unit_fixes=max_translate,
        )
        translated_n += api_n
        corpus_n += corp_n
        structured_used = ok_c
        if not ok_c:
            pt_slice = trim_pt_chunk_leakage(original_pt)
            pairs = align_units_to_pt(units, pt_slice, pt_tail=pt_tail)
            log("  [C] sem substituição — PT de entrada mantido")
    res.pt_slice = pt_slice
    res.turns_fixed_corpus = corpus_n
    res.turns_translated = translated_n

    log("  [D] checklist linha a linha (verificação pós-correção)")
    pairs = align_units_to_pt(units, pt_slice, pt_tail=pt_tail)
    blocking, issues, notes = validate_segment_line_by_line(
        jp_slice, pt_slice, pairs, filename=filename, bound=bound, profile=profile,
        segment_index=segment_index,
    )
    res.blocking = blocking
    res.review_issues = issues
    res.review_notes = notes
    log(f"  [D] blocking={blocking}")
    for n in notes[:8]:
        log(f"       {n}")

    safe, persist_issues = pt_slice_safe_to_persist(
        jp_slice, pt_slice, segment_index, bound, original_pt_len=original_pt_len
    )
    if not safe:
        res.persist_blocked = True
        res.slice_invalid = True
        res.blocking = True
        for msg in persist_issues:
            log(f"  [D] saída não persistível — {msg}")
        if ISSUE_ALIGN not in res.review_issues:
            res.review_issues.append(ISSUE_ALIGN)

    return res
