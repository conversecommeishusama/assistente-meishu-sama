"""Parser de turnos Q&A (御伺い/御垂示, Pergunta/Resposta) para comparativos P1b."""

from __future__ import annotations

import re
from dataclasses import dataclass

TurnKind = str  # interlocutor | meishu | teaching | header | narration

from livros_qa_markers import (  # noqa: E402
    JP_DATE_HEADER_RE,
    is_gokowa_pt_question_line,
    is_jp_question_line,
    is_pt_question_line,
    pt_split_date_line,
    reflow_gokowa_pt,
)

PT_MARKER_RE = re.compile(
    r"(\(Pergunta\)|\(Consulta\)|\[Resposta Divina\]|\[Revelação Divina\]"
    r"|\[Orientação Divina\]|\[Instrução Divina\]|\[Ensinamento\]|\(Ensinamento\))"
)
JP_DATE_RE = JP_DATE_HEADER_RE
JP_INDENT_RE = re.compile(r"^[\u3000\u0020\u00a0]+")
PT_SUBQUESTION_RE = re.compile(r"^\(\d+\)")
PT_PAREN_ASIDE_RE = re.compile(r"^\([^)]{1,120}\)\s*$")


@dataclass(frozen=True)
class QaTurn:
    kind: TurnKind
    text: str


def _flush(buf: list[str], mode: TurnKind | None, turns: list[QaTurn]) -> None:
    if not buf:
        return
    body = "\n".join(buf).strip()
    if body:
        turns.append(QaTurn(mode or "narration", body))
    buf.clear()


def _pt_split_date(s: str) -> tuple[str | None, str | None]:
    """Separa cabeçalho de data PT do resto da linha (ex. ``18 de agosto (Pergunta)…``)."""
    return pt_split_date_line(s)


def _pt_consume_markers(
    s: str,
    *,
    turns: list[QaTurn],
    buf: list[str],
    mode: TurnKind | None,
) -> TurnKind | None:
    parts = PT_MARKER_RE.split(s)
    if len(parts) == 1:
        if mode in ("interlocutor", "meishu", "teaching"):
            buf.append(s)
        elif PT_SUBQUESTION_RE.match(s):
            mode = "interlocutor"
            buf.append(s)
        else:
            _flush(buf, mode, turns)
            turns.append(QaTurn("narration", s))
            mode = None
        return mode

    for part in parts:
        if not part:
            continue
        if part in ("(Pergunta)", "(Consulta)"):
            _flush(buf, mode, turns)
            mode = "interlocutor"
        elif part in ("[Resposta Divina]", "[Revelação Divina]", "[Orientação Divina]", "[Instrução Divina]"):
            _flush(buf, mode, turns)
            mode = "meishu"
        elif part in ("[Ensinamento]", "(Ensinamento)"):
            _flush(buf, mode, turns)
            # PT usa [Ensinamento] tanto como 〔御垂示〕 (após consulta) quanto 【御教え】 (apêndice).
            mode = "meishu" if mode == "interlocutor" else "teaching"
        elif part.strip():
            if mode is None and PT_SUBQUESTION_RE.match(part.strip()):
                mode = "interlocutor"
            elif mode is None:
                mode = "narration"
            buf.append(part.strip())
    return mode


def parse_qa_turns_jp_mioshie(text: str) -> list[QaTurn]:
    """Mioshie/Ochishiji JP: （お伺） + continuação 　… até 〔御垂示〕/【御教え】."""
    turns: list[QaTurn] = []
    mode: TurnKind | None = None
    buf: list[str] = []

    for line in text.splitlines():
        raw = line.rstrip()
        s = raw.strip()
        if not s:
            continue

        if JP_DATE_RE.match(s) or (s.startswith("［") and s.endswith("］")):
            _flush(buf, mode, turns)
            mode = None
            turns.append(QaTurn("header", s))
            continue

        if s.startswith("（お伺）"):
            _flush(buf, mode, turns)
            mode = "interlocutor"
            body = s[4:].strip()
            if body:
                buf.append(body)
            continue

        if s.startswith("――"):
            _flush(buf, mode, turns)
            mode = "interlocutor"
            body = s[2:].strip()
            if body:
                buf.append(body)
            continue

        if s.startswith("〔御垂示〕"):
            _flush(buf, mode, turns)
            mode = "meishu"
            rest = s[len("〔御垂示〕") :].strip()
            if rest:
                buf.append(rest)
            continue

        if s.startswith("【御教え】"):
            _flush(buf, mode, turns)
            mode = "teaching"
            rest = s[len("【御教え】") :].strip()
            if rest:
                buf.append(rest)
            continue

        if JP_INDENT_RE.match(raw) and mode in ("interlocutor", "meishu", "teaching"):
            buf.append(s)
            continue

        if mode in ("interlocutor", "meishu", "teaching"):
            buf.append(s)
            continue

        _flush(buf, mode, turns)
        mode = None
        turns.append(QaTurn("narration", s))

    _flush(buf, mode, turns)
    return turns


def parse_qa_turns_pt_mioshie(text: str) -> list[QaTurn]:
    """PT Mioshie: (Pergunta) … até [Resposta Divina]/[Revelação Divina]/[Ensinamento]."""
    turns: list[QaTurn] = []
    mode: TurnKind | None = None
    buf: list[str] = []

    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue

        date_hdr, rest = _pt_split_date(s)
        if date_hdr:
            _flush(buf, mode, turns)
            mode = None
            turns.append(QaTurn("header", date_hdr))
            if not rest:
                continue
            s = rest

        if s.startswith("【Ensinamento】") or s.startswith("[Mioshie]"):
            _flush(buf, mode, turns)
            mode = "teaching"
            body = s.replace("【Ensinamento】", "").replace("[Mioshie]", "").strip()
            if body:
                buf.append(body)
            continue

        if PT_MARKER_RE.search(s):
            mode = _pt_consume_markers(s, turns=turns, buf=buf, mode=mode)
            continue

        if s in (
            "[Resposta Divina]",
            "[Revelação Divina]",
            "[Orientação Divina]",
            "[Instrução Divina]",
            "[Ensinamento]",
            "(Ensinamento)",
        ):
            _flush(buf, mode, turns)
            if s in ("[Ensinamento]", "(Ensinamento)"):
                mode = "meishu" if mode == "interlocutor" else "teaching"
            else:
                mode = "meishu"
            continue

        if s.startswith("(Ensinamento após"):
            _flush(buf, mode, turns)
            mode = "teaching"
            buf.append(s)
            continue

        if is_pt_question_line(s):
            _flush(buf, mode, turns)
            mode = "interlocutor"
            for prefix in ("(Pergunta)", "(Consulta)", "—", "——", "―"):
                if s.startswith(prefix):
                    s = s[len(prefix) :].strip()
                    break
            if s:
                buf.append(s)
            continue

        if PT_SUBQUESTION_RE.match(s) and mode in (None, "interlocutor"):
            if mode is None:
                mode = "interlocutor"
            buf.append(s)
            continue

        if mode == "interlocutor" and PT_PAREN_ASIDE_RE.match(s):
            buf.append(s)
            continue

        if mode in ("interlocutor", "meishu", "teaching"):
            buf.append(s)
        else:
            _flush(buf, mode, turns)
            turns.append(QaTurn("narration", s))
            mode = None

    _flush(buf, mode, turns)
    return turns


def parse_qa_turns_gokowa(text: str, *, lang: str, alternating: bool = False) -> list[QaTurn]:
    """Gokōwa/Gosuiji: perguntas ——/—— e respostas seguintes ou entre aspas."""
    if lang == "pt":
        text = reflow_gokowa_pt(text)
    turns: list[QaTurn] = []
    mode: TurnKind | None = None
    buf: list[str] = []
    next_is_q = True

    for line in text.splitlines():
        s = line.strip()
        if not s:
            continue

        if lang == "jp" and (JP_DATE_RE.match(s) or (s.startswith("［") and s.endswith("］"))):
            _flush(buf, mode, turns)
            mode = None
            turns.append(QaTurn("header", s))
            continue
        if lang == "pt":
            date_hdr, rest = _pt_split_date(s)
            if date_hdr:
                _flush(buf, mode, turns)
                mode = None
                next_is_q = True
                turns.append(QaTurn("header", date_hdr))
                if not rest:
                    continue
                s = rest
            elif re.match(r"^\[\d", s):
                _flush(buf, mode, turns)
                mode = None
                turns.append(QaTurn("header", s))
                continue
            elif s.startswith("Interlocutor:"):
                _flush(buf, mode, turns)
                mode = "interlocutor"
                body = s[len("Interlocutor:") :].strip()
                if body:
                    buf.append(body)
                continue
            elif s.startswith("Meishu-Sama:"):
                _flush(buf, mode, turns)
                mode = "meishu"
                body = s[len("Meishu-Sama:") :].strip()
                if body:
                    buf.append(body)
                continue

        is_q = is_jp_question_line(s) if lang == "jp" else is_gokowa_pt_question_line(s)
        if lang == "pt" and alternating and re.match(r"^[—―–\-]{1,2}", s):
            _flush(buf, mode, turns)
            mode = "interlocutor" if next_is_q else "meishu"
            next_is_q = not next_is_q
            body = re.sub(r"^[—―–\-]{1,2}\s*", "", s)
            if body:
                buf.append(body)
            continue

        if is_q:
            _flush(buf, mode, turns)
            mode = "interlocutor"
            for prefix in ("――", "——", "—", "―", "(Pergunta)", "(Consulta)"):
                if s.startswith(prefix):
                    s = s[len(prefix) :].strip()
                    break
            if s.startswith("——"):
                s = s[2:].strip()
            elif s.startswith("—"):
                s = s[1:].strip()
            if s:
                buf.append(s)
            continue

        if lang == "jp" and line.startswith("　"):
            if mode == "interlocutor":
                _flush(buf, mode, turns)
                mode = "meishu"
            if mode == "meishu":
                buf.append(s)
                continue
            if mode is None:
                mode = "meishu"
                buf.append(s)
                continue

        if mode == "interlocutor":
            _flush(buf, mode, turns)
            mode = "meishu"
            buf.append(s)
            continue

        if mode == "meishu":
            buf.append(s)
            continue

        _flush(buf, mode, turns)
        mode = None
        turns.append(QaTurn("narration", s))

    _flush(buf, mode, turns)
    return turns


def parse_qa_turns(text: str, *, lang: str, profile: str = "mioshie_shu") -> list[QaTurn]:
    if profile in ("mioshie_shu", "ochishiji_roku"):
        return parse_qa_turns_jp_mioshie(text) if lang == "jp" else parse_qa_turns_pt_mioshie(text)
    if profile in ("gokowa_roku_qa", "gokowa_roku_ho"):
        return parse_qa_turns_gokowa(text, lang=lang, alternating=profile == "gokowa_roku_ho")
    return [QaTurn("narration", text.strip())] if text.strip() else []


def format_qa_turn(turn: QaTurn) -> str:
    if turn.kind == "header":
        return f"▸ {turn.text}"
    if turn.kind == "interlocutor":
        return f"▸ Interlocutor: {turn.text}"
    if turn.kind == "teaching":
        return f"◂ Meishu-Sama [ensinamento]: {turn.text}"
    if turn.kind == "meishu":
        return f"◂ Meishu-Sama: {turn.text}"
    if turn.kind == "narration":
        return f"· {turn.text}"
    return turn.text


def annotate_qa_speakers(text: str, *, lang: str, profile: str = "mioshie_shu") -> str:
    turns = parse_qa_turns(text, lang=lang, profile=profile)
    return "\n\n".join(format_qa_turn(t) for t in turns)


def qa_turn_counts(turns: list[QaTurn]) -> tuple[int, int, int]:
    q = sum(1 for t in turns if t.kind == "interlocutor")
    a = sum(1 for t in turns if t.kind == "meishu")
    t = sum(1 for t in turns if t.kind == "teaching")
    return q, a, t


def verify_qa_alignment(jp_text: str, pt_text: str, *, profile: str) -> list[str]:
    jp = parse_qa_turns(jp_text, lang="jp", profile=profile)
    pt = parse_qa_turns(pt_text, lang="pt", profile=profile)
    jq, ja, jte = qa_turn_counts(jp)
    pq, pa, pte = qa_turn_counts(pt)
    warnings: list[str] = []
    if jq != pq:
        warnings.append(f"perguntas JP={jq} vs PT={pq}")
    if profile in ("gokowa_roku_qa", "gokowa_roku_ho"):
        if profile == "gokowa_roku_ho":
            from livros_qa_markers import count_gokowa_pt_questions, count_jp_questions  # noqa: WPS433

            jq_ho = count_jp_questions(jp_text)
            pq_ho = count_gokowa_pt_questions(pt_text, alternating=False)
            pq_ho += sum(1 for ln in pt_text.splitlines() if ln.strip().startswith("――"))
            warnings = []
            if jq_ho != pq_ho:
                warnings.append(f"perguntas JP={jq_ho} vs PT={pq_ho}")
        return warnings
    if ja != pa:
        warnings.append(f"respostas JP={ja} vs PT={pa}")
    if jte != pte and not (jq == pq and ja == pa):
        warnings.append(f"ensinamentos JP={jte} vs PT={pte}")
    return warnings


def _truncate_at_word(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    cut = text[:max_len]
    if " " in cut[-40:]:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "…"


def preview_qa_turns(
    text: str,
    *,
    lang: str,
    profile: str,
    source_chars: int,
    limit: int = 1400,
    max_pairs: int = 1,
    q_max: int = 420,
    a_max: int = 480,
) -> tuple[str, bool]:
    """Pré-visualização sincronizada: cabeçalho + N pares pergunta/resposta completos."""
    turns = parse_qa_turns(text, lang=lang, profile=profile)
    parts: list[str] = []
    used = 0
    truncated = False
    pairs = 0
    i = 0

    while i < len(turns) and turns[i].kind == "header":
        line = format_qa_turn(turns[i])
        parts.append(line)
        used += len(line) + 2
        i += 1

    while i < len(turns) and pairs < max_pairs:
        if turns[i].kind != "interlocutor":
            i += 1
            continue
        q_line = f"▸ Interlocutor: {_truncate_at_word(turns[i].text, q_max)}"
        block = q_line
        if i + 1 < len(turns) and turns[i + 1].kind in ("meishu", "teaching"):
            a_turn = turns[i + 1]
            label = (
                "◂ Meishu-Sama [ensinamento]: "
                if a_turn.kind == "teaching"
                else "◂ Meishu-Sama: "
            )
            block += "\n\n" + label + _truncate_at_word(a_turn.text, a_max)
            i += 2
        else:
            i += 1
        if used + len(block) > limit and parts:
            truncated = True
            break
        parts.append(block)
        used += len(block) + 2
        pairs += 1

    has_more = any(t.kind in ("interlocutor", "meishu", "teaching") for t in turns[i:])
    if has_more or source_chars > limit:
        truncated = True

    out = "\n\n".join(parts)
    if truncated:
        out += (
            f"\n\n[… pré-visualização: {pairs} diálogo(s); "
            f"texto completo {source_chars:,} caracteres …]"
        )
    return out, truncated


def preview_qa_annotated(
    annotated: str,
    *,
    source_chars: int,
    limit: int = 1400,
    q_head: int = 380,
    a_head: int = 520,
) -> tuple[str, bool]:
    """Compat: delega para preview por turnos quando possível."""
    del q_head, a_head
    if len((annotated or "").strip()) <= limit:
        return (annotated or "").strip(), False
    cut = annotated[:limit]
    if " " in cut[-40:]:
        cut = cut.rsplit(" ", 1)[0]
    return (
        cut + f"\n\n[… pré-visualização: texto completo tem {source_chars:,} caracteres …]",
        True,
    )
