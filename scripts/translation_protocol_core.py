#!/usr/bin/env python3
"""Two-pass translation pipeline (protocolo_traducao.txt): translate + post-review."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from retranslate_core import (
    MAX_OUTPUT_TOKENS,
    MODEL,
    UsageTotal,
    call_deepseek,
    extract_title,
    split_jp_chunks,
    strip_metadata,
)
from retranslate_qa import CJK_RE, find_japanese_residuals, sanitize_pt_translation, validate_translation
from post_translation_glossary import apply_post_translation_glossary, glossary_qa_issues
from run_deepseek_revision_pilot import (
    format_glossary_block,
    load_glossary,
    parse_revision_response,
)
from translation_header_parser import (
    PERIODICAL_FICHA_RE,
    SERIES_FICHA_RE,
    ensure_header_from_jp_metadata,
    pt_has_periodical_ficha,
    pt_has_series_ficha,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = PROJECT_ROOT / "protocolo_traducao.txt"
REVIEW_BATCH_SIZE = 4
MAX_REVIEW_PAIRS = 64  # PT degenerado (ex.: repetição) não pode disparar centenas de chamadas
LAYOUT_FALLBACK_MAX_CHARS = 4000  # último recurso: PT colapsado sem JP disponível

SESSION_DATE_RE = re.compile(r"^[［\[][^\]]+[］\]]\s*$")
SECTION_HEADING_RE = re.compile(
    r"^(Prefácio|Prefacio|Introdução|Introducao|Nota editorial|序文)\s*$",
    re.IGNORECASE,
)
JP_SECTION_TITLE_RE = re.compile(
    r"^[\u4e00-\u9fff\u3000\u30a0-\u30ff\u3040-\u309f\s]{2,35}$",
)
JP_INQUIRY_RE = re.compile(r"^御伺")
JP_REVELATION_RE = re.compile(r"^御垂示")
JP_SPEAKER_RE = re.compile(
    r"^(?:"
    r"[^\s　]{1,12}氏"
    r"|[明][主为]主?[様样]"
    r"|[\u3040-\u30ff\u4e00-\u9fffァ-ヶ]{1,6}"
    r")[:：\t]"
)
NAMED_SPEAKER_RE = re.compile(
    r"^(Sr\.|Sra\.|Dr\.|Prof\.|Mr\.|Mrs\.)\s+[A-Za-zÀ-ÿōūāīēŌŪĀĪĒ\-]+:",
)
PT_MARKDOWN_SPEAKER_RE = re.compile(r"^\*\*([^*]+?):\*\*\s*")

# Falantes NOMEADOS de entrevistas/mesas-redondas que NÃO usam o padrão
# Interlocutor:/Meishu-Sama: (levantados do corpus real em 2026-08-26).
# IMPORTANTE: NÃO usar um padrão genérico "palavra:" aqui — qualquer palavra
# seguida de dois-pontos no meio de frase virava quebra indevida de parágrafo
# (regressão: ~1.265 quebras falsas só no Eiko). A lista é fechada aos falantes
# reais; novos falantes devem ser acrescentados explicitamente ao aparecerem.
PT_NAMED_SPEAKERS = (
    "Tanikawa|Moderador|Repórter|Jornalista|Secretário|Político|Médico|Promotor|"
    "Esposa|Chefe|Presidente|Vice-Presidente|Pai|Imperador|"
    "Ino|Okada|Okumura|Miyata|Musei|Itō|Nakajima|Onoshima|Tsuchiya|Kataoka|"
    "Matsumoto|Adachi|Shugakuin|Kitami|Nabata|Suzuki|Sue|Nichiren"
)
PT_NAMED_SPEAKER_RE = re.compile(
    rf"^(?:{PT_NAMED_SPEAKERS}):",
)
PT_NAMED_SPEAKER_INLINE_RE = re.compile(
    rf"(?<=\S)\s+(?=(?:{PT_NAMED_SPEAKERS}):)",
)

PT_SPEAKER_RE = re.compile(
    r"^("
    r"Interlocutor:|Meishu-Sama:"
    r"|(?:Sr|Sra|Dr|Prof)\.\s+[A-Za-zÀ-ÿ\-]+:"
    rf"|(?:{PT_NAMED_SPEAKERS}):"
    r")",
    re.IGNORECASE,
)
PT_INLINE_SPEAKER_SPLIT_RE = re.compile(
    r"(?<=\S)\s+(?=(?:"
    r"Interlocutor:|Meishu-Sama:"
    r"|(?:Sr|Sra|Dr|Prof)\.\s+[A-Za-zÀ-ÿ\-]+:"
    r"|\*\*[^*]{1,40}:\*\*"
    rf"|(?:{PT_NAMED_SPEAKERS}):"
    r"))",
    re.IGNORECASE,
)


def _split_paragraphs(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"\n\s*\n+", text or "") if part.strip()]


def _join_paragraphs(parts: list[str]) -> str:
    return "\n\n".join(part.strip() for part in parts if part.strip())


def _split_sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?…])\s+", text or "") if part.strip()]


PT_SECTION_TITLE_RE = re.compile(
    r"^(A |O |Uma |Sobre |Religião|Religión|Mattō|Gosuiji|Luz do|Uma Palavra|Nos sutras|\*\*)",
    re.I,
)
PT_NOT_SECTION_TITLE_RE = re.compile(
    r"^(A [a-záàâãéêíóôõú]|O [a-záàâãéêíóôõú]|É |Além |Isso |Não |Se |Por |Em |No |Na |Muitas |"
    r"Originalmente|Certamente|Contudo|Entretanto|Foi |Pelo |Pensamentos|Como |Atrevo|Essas |"
    r"As respostas|Nesse sentido|Maio do)",
)


def _contains_cjk(text: str) -> bool:
    return bool(CJK_RE.search(text or ""))


def _is_pt_section_title(block: str) -> bool:
    if PT_SPEAKER_RE.match(block) or block.startswith("["):
        return False
    if "publicado em" in block or len(block) > 80:
        return False
    if block.strip() in {"Prefácio", "O Editor", "Prefacio"}:
        return False
    if block.startswith("Interlocutor:") or block.startswith("Meishu-Sama:"):
        return False
    stripped = block.strip()
    if (
        stripped.endswith("?")
        and len(stripped) <= 65
        and re.match(r"^(O que|A qu|Qual|Como|Por que|Quando|Onde|Em que|Que )", stripped, re.I)
    ):
        return True
    if PT_NOT_SECTION_TITLE_RE.match(block):
        return False
    if "," in block and len(block) > 35:
        return False
    if len(block) <= 55 and block[0].isupper() and not block.rstrip().endswith("."):
        return bool(PT_SECTION_TITLE_RE.match(block) or block.istitle() or block[1:3] == " ")
    return bool(PT_SECTION_TITLE_RE.match(block))


def _is_jp_section_title_block(block: str) -> bool:
    first = block.split("\n")[0].strip()
    return (
        len(first) <= 35
        and JP_SECTION_TITLE_RE.fullmatch(first)
        and not JP_INQUIRY_RE.match(first)
        and not JP_REVELATION_RE.match(first)
        and not first.startswith("「")
    )


def _split_qa_sections(blocks: list[str], *, is_jp: bool) -> list[list[str]]:
    indices = [
        i
        for i, b in enumerate(blocks)
        if (_is_jp_section_title_block(b) if is_jp else _is_pt_section_title(b))
    ]
    if not indices:
        return [blocks]
    sections: list[list[str]] = []
    for si, start in enumerate(indices):
        end = indices[si + 1] if si + 1 < len(indices) else len(blocks)
        sections.append(blocks[start:end])
    return sections


def _split_speaker_runs(blocks: list[str], *, is_jp: bool) -> list[list[str]]:
    runs: list[list[str]] = []
    current: list[str] = []
    mode: str | None = None

    def flush() -> None:
        nonlocal current, mode
        if current:
            runs.append(current)
            current = []
        mode = None

    for block in blocks:
        if is_jp:
            if _is_jp_section_title_block(block):
                flush()
                runs.append([block])
                continue
            if JP_INQUIRY_RE.match(block):
                flush()
                current = [block]
                mode = "inquiry"
                continue
            if JP_REVELATION_RE.match(block):
                flush()
                current = [block]
                mode = "revelation"
                continue
            if mode == "revelation":
                current.append(block)
                continue
        else:
            if _is_pt_section_title(block):
                flush()
                runs.append([block])
                continue
            if block.startswith("Interlocutor:"):
                flush()
                current = [block]
                mode = "inquiry"
                continue
            if block.startswith("Meishu-Sama:"):
                flush()
                current = [block]
                mode = "revelation"
                continue
            if mode == "revelation":
                current.append(block)
                continue
        if mode:
            current.append(block)
        else:
            flush()
            current = [block]
    flush()
    return runs


def _reflow_matched_runs(pt_runs: list[list[str]], jp_runs: list[list[str]]) -> list[str]:
    out: list[str] = []
    for pt_run, jp_run in zip(pt_runs, jp_runs):
        out.extend(_expand_pt_run_to_jp(pt_run, jp_run))
    for extra in pt_runs[len(jp_runs) :]:
        out.extend(extra)
    return out


def _speaker_prefix(block: str) -> str:
    match = PT_SPEAKER_RE.match(block)
    if match:
        return match.group(1)
    if block.startswith("Interlocutor:"):
        return "Interlocutor:"
    if block.startswith("Meishu-Sama:"):
        return "Meishu-Sama:"
    return ""


def _expand_pt_run_to_jp(pt_run: list[str], jp_run: list[str]) -> list[str]:
    if not pt_run:
        return []
    if len(pt_run) == len(jp_run):
        return pt_run
    prefix = _speaker_prefix(pt_run[0])
    body = " ".join(_strip_speaker_prefix(p) for p in pt_run)
    parts = _split_paragraphs(_reflow_body_by_jp_weights(body, jp_run))
    out: list[str] = []
    for idx, part in enumerate(parts):
        if idx == 0 and prefix and not part.startswith(prefix.rstrip(":")):
            out.append(f"{prefix} {part}" if prefix.endswith(":") else part)
        else:
            out.append(part)
    return out


def normalize_pt_speaker_markers(text: str) -> str:
    """Converte **Okada:** / **Musei:** em Okada: / Musei: (§4.4-B)."""
    if not text:
        return text
    out = re.sub(r"\*\*([^*]{1,40}):\*\*\s*", r"\1: ", text)
    out = PT_MARKDOWN_SPEAKER_RE.sub(r"\1: ", out)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def _jp_speaker_turn_count(blocks: list[str]) -> int:
    count = 0
    for block in blocks:
        head = block.split("\n")[0].strip()
        if JP_SPEAKER_RE.match(head):
            count += 1
    return count


def split_collapsed_speaker_paragraph(para: str) -> list[str]:
    """Separa turnos colados: Interlocutor + Meishu-Sama ou falantes nomeados."""
    text = normalize_pt_speaker_markers((para or "").strip())
    if not text:
        return []
    parts = PT_INLINE_SPEAKER_SPLIT_RE.split(text)
    if len(parts) <= 1:
        return [text]
    return [part.strip() for part in parts if part.strip()]


def split_collapsed_speaker_blocks(blocks: list[str]) -> list[str]:
    out: list[str] = []
    for block in blocks:
        out.extend(split_collapsed_speaker_paragraph(block))
    return out


def _split_jp_inquiry_response_pairs(jp_blocks: list[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for block in jp_blocks:
        if "「" not in block:
            if pairs:
                inquiry, response = pairs[-1]
                pairs[-1] = (inquiry, f"{response} {block}".strip() if response else block)
            continue
        match = re.match(r"^(「[^」]*」)\s*(.*)$", block, re.DOTALL)
        if match:
            pairs.append((match.group(1).strip(), match.group(2).strip()))
        else:
            pairs.append((block.strip(), ""))
    return pairs


def _reflow_quote_dialogue(pt_blocks: list[str], jp_blocks: list[str]) -> list[str]:
    """Gosuiji/Gokōwa: alinha pares 「pergunta」/resposta do JP ao PT."""
    pt_date_idx = next((i for i, block in enumerate(pt_blocks) if re.fullmatch(r"\[[^\]]+\]", block)), -1)
    jp_date_idx = next((i for i, block in enumerate(jp_blocks) if SESSION_DATE_RE.match(block)), -1)
    if pt_date_idx < 0 or jp_date_idx < 0:
        return pt_blocks

    prefix = pt_blocks[: pt_date_idx + 1]
    pt_body = split_collapsed_speaker_blocks(pt_blocks[pt_date_idx + 1 :])
    jp_pairs = _split_jp_inquiry_response_pairs(jp_blocks[jp_date_idx + 1 :])
    if not jp_pairs:
        return prefix + pt_body

    pt_turns: list[tuple[str, str]] = []
    mode: str | None = None
    current_inq = ""
    current_resp: list[str] = []

    def flush_turn() -> None:
        nonlocal current_inq, current_resp, mode
        if current_inq or current_resp:
            pt_turns.append((current_inq, " ".join(current_resp).strip()))
        current_inq = ""
        current_resp = []
        mode = None

    for block in pt_body:
        for piece in split_collapsed_speaker_paragraph(block):
            if piece.startswith("Interlocutor:") or piece.startswith('"') or piece.startswith("“"):
                flush_turn()
                current_inq = piece
                mode = "inquiry"
            elif piece.startswith("Meishu-Sama:"):
                if mode == "inquiry":
                    mode = "response"
                current_resp.append(_strip_speaker_prefix(piece))
            elif mode == "inquiry":
                current_inq = f"{current_inq} {piece}".strip() if current_inq else piece
                mode = "response"
                current_resp.append(piece)
            elif mode == "response":
                current_resp.append(piece)
            else:
                current_resp.append(piece)
    flush_turn()

    out = list(prefix)
    for idx, (jp_inq, jp_resp) in enumerate(jp_pairs):
        pt_inq, pt_resp = pt_turns[idx] if idx < len(pt_turns) else ("", "")
        if pt_inq:
            inquiry = pt_inq if pt_inq.startswith("Interlocutor:") else f"Interlocutor: {pt_inq}"
            out.append(inquiry.strip())
        elif jp_inq and not _contains_cjk(jp_inq):
            out.append(f"Interlocutor: {jp_inq}" if not jp_inq.startswith("Interlocutor:") else jp_inq)
        if pt_resp or jp_resp:
            jp_rev = [jp_resp] if jp_resp else [jp_inq]
            merged = _split_paragraphs(_reflow_body_by_jp_weights(pt_resp or jp_resp, jp_rev))
            for j, para in enumerate(merged):
                if j == 0:
                    out.append(para if para.startswith("Meishu-Sama:") else f"Meishu-Sama: {para}")
                else:
                    out.append(para)
    for extra in pt_turns[len(jp_pairs) :]:
        if extra[0]:
            out.append(extra[0])
        if extra[1]:
            out.append(f"Meishu-Sama: {extra[1]}" if not extra[1].startswith("Meishu-Sama:") else extra[1])
    return out


def _is_qa_text(jp_blocks: list[str]) -> bool:
    return sum(1 for b in jp_blocks if JP_INQUIRY_RE.match(b.split("\n")[0])) >= 2


def _is_dialogue_text(jp_blocks: list[str]) -> bool:
    return sum(1 for b in jp_blocks if "「" in b) >= 2


def _has_collapsed_dialogue_turns(blocks: list[str]) -> bool:
    return any("Interlocutor:" in block and "Meishu-Sama:" in block for block in blocks)


JP_NEW_PARA_RE = re.compile(
    r"^(また、|いま一?つ|この例|別言|元来|ところが|右は|第一|勿論|したがって|以上|次に|そうして|だから|しかし)"
)


JP_OCR_CONTINUATION_RE = re.compile(r"^[ぁ-んー]")


def _should_merge_jp_lines(buf: str, nxt: str) -> bool:
    buf = buf.strip()
    nxt = nxt.strip()
    if not buf or not nxt:
        return False
    if re.search(r"[。！？…」]\s*$", buf):
        return False
    if JP_NEW_PARA_RE.match(nxt):
        return False
    if re.search(r"っ\s*$", buf) and JP_OCR_CONTINUATION_RE.match(nxt):
        return True
    if re.search(r"とこ\s*$", buf) and nxt.startswith("ろ"):
        return True
    return False


def merge_dangling_jp_lines(jp_blocks: list[str]) -> list[str]:
    """Funde linhas JP partidas no meio de frase (quebra de OCR/impressão)."""
    if len(jp_blocks) < 2:
        return jp_blocks
    out: list[str] = []
    buf = ""
    for block in jp_blocks:
        stripped = block.strip()
        if not buf:
            buf = stripped
            continue
        if _should_merge_jp_lines(buf, stripped):
            buf = f"{buf}{stripped}"
        else:
            out.append(buf)
            buf = stripped
    if buf:
        out.append(buf)
    return out


def split_jp_prose_paragraphs(jp_body: str) -> list[str]:
    """Parágrafos de prosa (artigos A4) quando o JP usa quebra simples de linha."""
    blocks = split_jp_structural_blocks(jp_body)
    out: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if len(lines) > 1:
            out.extend(merge_dangling_jp_lines(lines))
        elif lines:
            out.append(lines[0])
    return out if out else blocks


def _strip_speaker_prefix(block: str) -> str:
    for prefix in ("Interlocutor:", "Meishu-Sama:"):
        if block.startswith(prefix):
            return block[len(prefix) :].strip()
    return block.strip()


def _build_jp_qa_sections(jp_blocks: list[str]) -> list[dict]:
    sections: list[dict] = []
    pending_title: str | None = None
    i = 0
    while i < len(jp_blocks):
        block = jp_blocks[i]
        first = block.split("\n")[0]
        if (
            _is_jp_section_title_block(block)
            and not JP_INQUIRY_RE.match(first)
            and not JP_REVELATION_RE.match(first)
        ):
            pending_title = block
            i += 1
            continue
        if JP_INQUIRY_RE.match(first):
            sec_title = pending_title
            pending_title = None
            inquiry = block
            i += 1
            revelation: list[str] = []
            while i < len(jp_blocks):
                nb = jp_blocks[i]
                nfl = nb.split("\n")[0]
                if (
                    _is_jp_section_title_block(nb)
                    and not JP_REVELATION_RE.match(nfl)
                    and not JP_INQUIRY_RE.match(nfl)
                ):
                    pending_title = nb
                    i += 1
                    break
                if JP_INQUIRY_RE.match(nfl):
                    break
                revelation.append(nb)
                i += 1
            sections.append({"title": sec_title, "inquiry": inquiry, "revelation": revelation})
            continue
        i += 1
    return sections


def _build_pt_qa_sections(pt_blocks: list[str]) -> list[dict]:
    sections: list[dict] = []
    pending_title: str | None = None
    i = 0
    while i < len(pt_blocks):
        block = pt_blocks[i]
        if block.startswith("Interlocutor:"):
            sec_title = pending_title
            pending_title = None
            inquiry = block
            i += 1
            revelation: list[str] = []
            while i < len(pt_blocks):
                nb = pt_blocks[i]
                if nb.startswith("Interlocutor:"):
                    break
                if _is_pt_section_title(nb):
                    pending_title = nb
                    i += 1
                    break
                revelation.append(nb)
                i += 1
            sections.append({"title": sec_title, "inquiry": inquiry, "revelation": revelation})
            continue
        if _is_pt_section_title(block):
            pending_title = block
            i += 1
            continue
        if block.startswith("Meishu-Sama:"):
            if sections:
                sections[-1]["revelation"].append(block)
            i += 1
            continue
        i += 1
    return sections


def _emit_qa_section(pt_sec: dict, jp_sec: dict | None = None) -> list[str]:
    out: list[str] = []
    title = pt_sec.get("title")
    if title and not _contains_cjk(title):
        out.append(title.strip())
    inquiry = pt_sec.get("inquiry") or ""
    if inquiry and not _contains_cjk(inquiry):
        if not inquiry.startswith("Interlocutor:"):
            inquiry = f"Interlocutor: {inquiry}"
        out.append(inquiry.strip())

    jp_sec = jp_sec or {}
    jp_rev = jp_sec.get("revelation") or []
    pt_rev = pt_sec.get("revelation") or []
    if not pt_rev:
        return out
    body = " ".join(_strip_speaker_prefix(p) for p in pt_rev if not _contains_cjk(p))
    if not body.strip():
        return out
    if jp_rev and len(jp_rev) <= max(12, len(pt_rev) * 4):
        merged = _split_paragraphs(_reflow_body_by_jp_weights(body, jp_rev))
    else:
        merged = _split_paragraphs(body) if len(pt_rev) > 1 else [body]
    for idx, para in enumerate(merged):
        if _contains_cjk(para):
            continue
        if idx == 0:
            out.append(para if para.startswith("Meishu-Sama:") else f"Meishu-Sama: {para}")
        else:
            out.append(para)
    return out


def _qa_body_start_pt(pt_blocks: list[str]) -> int:
    for i, block in enumerate(pt_blocks):
        if block.startswith("Interlocutor:"):
            if i > 0 and _is_pt_section_title(pt_blocks[i - 1]):
                return i - 1
            return i
    return len(pt_blocks)


def _reflow_qa_body_by_jp_sections(pt_body: list[str], jp_body: list[str]) -> list[str]:
    pt_secs = _build_pt_qa_sections(pt_body)
    jp_secs = _build_jp_qa_sections(jp_body)
    if not pt_secs:
        return _reflow_matched_runs(
            _split_speaker_runs(pt_body, is_jp=False),
            _split_speaker_runs(jp_body, is_jp=True),
        )
    out: list[str] = []
    for idx, pt_sec in enumerate(pt_secs):
        jp_sec = jp_secs[idx] if idx < len(jp_secs) else {}
        out.extend(_emit_qa_section(pt_sec, jp_sec))
    return out


def _reflow_qa_sections(pt_blocks: list[str], jp_blocks: list[str]) -> list[str]:
    pt_start = _qa_body_start_pt(pt_blocks)
    jp_start = _body_start_jp(jp_blocks)
    prefix = pt_blocks[:pt_start]
    aligned_body = _reflow_qa_body_by_jp_sections(pt_blocks[pt_start:], jp_blocks[jp_start:])
    return prefix + aligned_body


def _split_dialogue_header_blocks(blocks: list[str], *, is_jp: bool) -> tuple[list[str], list[str]]:
    """Preserva cabeçalho A4 (título, ficha, entrevista, dateline) antes do reflow de falas."""
    for i, block in enumerate(blocks):
        head = block.split("\n")[0]
        if (JP_SPEAKER_RE if is_jp else PT_SPEAKER_RE).match(head):
            return blocks[:i], blocks[i:]
    return blocks, []


JP_SPEAKER_PT_NAMES = {"岡田": "Okada", "夢声": "Musei", "明主": "Meishu-Sama", "明為": "Meishu-Sama"}


def _jp_block_pt_speaker(jp_block: str) -> str:
    head = jp_block.split("\n")[0].strip()
    if not JP_SPEAKER_RE.match(head):
        return ""
    name = re.split(r"[:：]", head, maxsplit=1)[0].strip()
    for jp_name, pt_name in JP_SPEAKER_PT_NAMES.items():
        if name == jp_name or name.endswith(jp_name):
            return f"{pt_name}:"
    return f"{name}:"


def _strip_pt_speaker(text: str) -> tuple[str, str]:
    text = (text or "").strip()
    match = PT_SPEAKER_RE.match(text)
    if match:
        return match.group(0).rstrip(), text[match.end() :].strip()
    return "", text


def _align_dialogue_blocks_1to1(pt_blocks: list[str], jp_blocks: list[str]) -> list[str]:
    """Um parágrafo PT por bloco JP (nota editorial + turnos de fala)."""
    pt_header, pt_body = _split_dialogue_header_blocks(pt_blocks, is_jp=False)
    _, jp_body = _split_dialogue_header_blocks(jp_blocks, is_jp=True)
    if not jp_body:
        return pt_blocks

    pt_turns: list[tuple[str, str]] = []
    for block in split_collapsed_speaker_blocks(pt_body):
        block = normalize_pt_speaker_markers(block)
        speaker, body = _strip_pt_speaker(block)
        if speaker:
            pt_turns.append((speaker, body))
        elif body:
            if pt_turns and not pt_turns[-1][1]:
                pt_turns[-1] = (pt_turns[-1][0], body)
            else:
                pt_turns.append(("", body))

    out: list[str] = list(pt_header)
    pt_idx = 0
    editorial_used = False
    for jp_block in jp_body:
        if jp_block.startswith("＊"):
            editorial = next(
                (txt for sp, txt in pt_turns[pt_idx:] if not sp and txt),
                next((txt for sp, txt in pt_turns if not sp and "diálogo" in txt.lower()), ""),
            )
            if editorial:
                out.append(editorial)
                editorial_used = True
                while pt_idx < len(pt_turns) and not pt_turns[pt_idx][0]:
                    if pt_turns[pt_idx][1] == editorial:
                        pt_idx += 1
                        break
                    pt_idx += 1
            continue

        expected = _jp_block_pt_speaker(jp_block)
        if pt_idx < len(pt_turns):
            speaker, body = pt_turns[pt_idx]
            pt_idx += 1
            label = expected or speaker
            out.append(f"{label} {body}".strip() if label else body)
        elif expected:
            out.append(expected)

    while pt_idx < len(pt_turns):
        speaker, body = pt_turns[pt_idx]
        pt_idx += 1
        if editorial_used and not speaker and "diálogo" in body.lower():
            continue
        out.append(f"{speaker} {body}".strip() if speaker else body)

    return out


def _reflow_named_speaker_dialogue(pt_blocks: list[str], jp_blocks: list[str]) -> list[str]:
    pt_header, pt_body = _split_dialogue_header_blocks(pt_blocks, is_jp=False)
    _, jp_body = _split_dialogue_header_blocks(jp_blocks, is_jp=True)
    if not pt_body:
        return pt_blocks

    pt_runs: list[list[str]] = []
    jp_runs: list[list[str]] = []
    pt_cur: list[str] = []
    jp_cur: list[str] = []
    for block in pt_body:
        if PT_SPEAKER_RE.match(block):
            if pt_cur:
                pt_runs.append(pt_cur)
            pt_cur = [block]
        else:
            pt_cur.append(block)
    if pt_cur:
        pt_runs.append(pt_cur)
    for block in jp_body:
        head = block.split("\n")[0]
        if JP_SPEAKER_RE.match(head):
            if jp_cur:
                jp_runs.append(jp_cur)
            jp_cur = [block]
        else:
            jp_cur.append(block)
    if jp_cur:
        jp_runs.append(jp_cur)
    if not pt_runs or not jp_runs:
        merged = _reflow_body_by_jp_weights(" ".join(pt_body), jp_body or jp_blocks)
        return pt_header + _split_paragraphs(merged)
    if len(pt_runs) == len(jp_runs):
        return pt_header + _reflow_matched_runs(pt_runs, jp_runs)

    out: list[str] = list(pt_header)
    jp_total = len(jp_runs)
    pt_total = len(pt_runs)
    jp_cursor = 0
    for pi, pt_run in enumerate(pt_runs):
        jp_end = round((pi + 1) * jp_total / pt_total) if pi < pt_total - 1 else jp_total
        jp_slice = jp_runs[jp_cursor:jp_end]
        jp_cursor = jp_end
        flat_jp = [block for run in jp_slice for block in run]
        if not flat_jp and jp_runs:
            flat_jp = jp_runs[min(jp_cursor - 1, jp_total - 1)]
        out.extend(_expand_pt_run_to_jp(pt_run, flat_jp))
    return out


def _merge_pt_blocks_by_jp_weights(pt_blocks: list[str], jp_blocks: list[str]) -> list[str]:
    """Funde parágrafos PT adjacentes até igualar a contagem dos blocos JP."""
    if len(pt_blocks) <= len(jp_blocks):
        return pt_blocks
    jp_lens = [max(len(re.sub(r"\s+", "", b)), 1) for b in jp_blocks]
    total_jp = sum(jp_lens)
    targets: list[float] = []
    cum = 0.0
    for length in jp_lens[:-1]:
        cum += length / total_jp
        targets.append(cum)

    pt_lens = [max(len(re.sub(r"\s+", "", b)), 1) for b in pt_blocks]
    total_pt = sum(pt_lens)
    result: list[str] = []
    buf: list[str] = []
    char_count = 0
    target_i = 0

    for pi, block in enumerate(pt_blocks):
        buf.append(block.strip())
        char_count += pt_lens[pi]
        at_last = pi == len(pt_blocks) - 1
        past_target = target_i < len(targets) and char_count >= targets[target_i] * total_pt
        if at_last or (past_target and len(result) < len(jp_blocks) - 1):
            result.append("\n\n".join(buf) if len(buf) == 1 else " ".join(buf))
            buf = []
            target_i += 1

    if buf:
        merged = "\n\n".join(buf) if len(buf) == 1 else " ".join(buf)
        if result:
            result[-1] = f"{result[-1]} {merged}".strip()
        else:
            result.append(merged)
    return result


def _reflow_pt_paragraphs_to_jp(pt_blocks: list[str], jp_blocks: list[str]) -> list[str]:
    """Alinha parágrafos PT aos blocos JP (§4.4-F), por seção e turno de fala."""
    if not pt_blocks or not jp_blocks:
        return pt_blocks
    speaker_turns = sum(1 for b in jp_blocks if JP_SPEAKER_RE.match(b.split("\n")[0]))
    if len(pt_blocks) == len(jp_blocks) and (
        speaker_turns >= 2 or _is_qa_text(jp_blocks) or _is_dialogue_text(jp_blocks)
    ):
        return pt_blocks

    if speaker_turns >= 2:
        return _reflow_named_speaker_dialogue(pt_blocks, jp_blocks)
    if _is_qa_text(jp_blocks):
        return _reflow_qa_sections(pt_blocks, jp_blocks)
    if _is_dialogue_text(jp_blocks):
        expanded: list[str] = []
        for inq, resp in _split_jp_inquiry_response_pairs(jp_blocks):
            expanded.append(inq)
            if resp:
                expanded.append(resp)
        if len(expanded) > len(jp_blocks):
            jp_blocks = expanded

    if len(pt_blocks) == len(jp_blocks):
        return pt_blocks
    merged = _reflow_body_by_jp_weights(" ".join(pt_blocks), jp_blocks)
    return _split_paragraphs(merged)


def reflow_pt_by_jp_blocks(jp_body: str, pt_body: str, *, jp_raw: str | None = None) -> str:
    """Alinha parágrafos PT aos blocos estruturais do JP (assunto/turno)."""
    if jp_raw:
        pt_body = ensure_header_from_jp_metadata(jp_raw, pt_body)

    pt_body = normalize_pt_speaker_markers(pt_body)
    prose_jp = split_jp_prose_paragraphs(jp_body)
    if _jp_speaker_turn_count(prose_jp) >= 2:
        pt_blocks = _split_paragraphs(apply_structural_layout(pt_body))
        pt_blocks = split_collapsed_speaker_blocks(pt_blocks)
        if pt_blocks:
            aligned = _reflow_named_speaker_dialogue(pt_blocks, prose_jp)
            return label_dialogue_turns(_join_paragraphs(aligned))

    jp_blocks = split_jp_structural_blocks(jp_body)
    pt_blocks = _split_paragraphs(apply_structural_layout(pt_body))
    pt_blocks = split_collapsed_speaker_blocks(pt_blocks)
    if not jp_blocks or not pt_blocks:
        return apply_structural_layout(pt_body)

    if _is_qa_text(jp_blocks):
        aligned = _reflow_qa_sections(pt_blocks, jp_blocks)
        return label_dialogue_turns(_join_paragraphs(aligned))

    pt_date_idx = next((i for i, block in enumerate(pt_blocks) if re.fullmatch(r"\[[^\]]+\]", block)), -1)
    jp_date_idx = next((i for i, block in enumerate(jp_blocks) if SESSION_DATE_RE.match(block)), -1)

    if pt_date_idx >= 0 and jp_date_idx >= 0:
        pt_body_blocks = pt_blocks[pt_date_idx + 1 :]
        jp_body_blocks = jp_blocks[jp_date_idx + 1 :]
        if (
            _is_dialogue_text(jp_body_blocks)
            and _has_collapsed_dialogue_turns(pt_body_blocks)
        ):
            aligned = _reflow_quote_dialogue(pt_blocks, jp_blocks)
            return label_dialogue_turns(_join_paragraphs(aligned))
        prefix = pt_blocks[: pt_date_idx + 1]
        if pt_body_blocks and jp_body_blocks:
            aligned = _reflow_pt_paragraphs_to_jp(pt_body_blocks, jp_body_blocks)
            return label_dialogue_turns(_join_paragraphs(prefix + aligned))

    if sum(1 for b in jp_blocks if JP_SPEAKER_RE.match(b.split("\n")[0])) >= 2:
        return label_dialogue_turns(_join_paragraphs(_reflow_named_speaker_dialogue(pt_blocks, jp_blocks)))

    prose_jp = split_jp_prose_paragraphs(jp_body)
    header_blocks = pt_blocks
    body_blocks = pt_blocks
    split_header = False
    for idx, block in enumerate(pt_blocks):
        if PERIODICAL_FICHA_RE.match(block) or SERIES_FICHA_RE.match(block):
            header_blocks = pt_blocks[: idx + 1]
            body_blocks = pt_blocks[idx + 1 :]
            split_header = True
            break
    if body_blocks and len(prose_jp) > 1:
        aligned_body = _reflow_pt_paragraphs_to_jp(body_blocks, prose_jp)
        merged = (header_blocks + aligned_body) if split_header else aligned_body
        return label_dialogue_turns(_join_paragraphs(merged))

    aligned = _reflow_pt_paragraphs_to_jp(pt_blocks, jp_blocks)
    return label_dialogue_turns(_join_paragraphs(aligned))


def split_jp_structural_blocks(text: str) -> list[str]:
    """Blocos lógicos do JP: linha em branco, ［data］, 「, seção, 御伺い/御垂示."""
    blocks: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf
        if buf:
            joined = "\n".join(buf).strip()
            if joined:
                blocks.append(joined)
            buf = []

    for line in (text or "").splitlines():
        stripped = line.strip()
        if not stripped:
            flush()
            continue
        if SESSION_DATE_RE.match(stripped):
            flush()
            blocks.append(stripped)
            continue
        if stripped.startswith("「"):
            flush()
            buf.append(stripped)
            continue
        if stripped.startswith("（") and "）" in stripped:
            flush()
            blocks.append(stripped)
            continue
        if SECTION_HEADING_RE.match(stripped) or stripped in {"序文", "Prefácio", "Prefacio"}:
            flush()
            blocks.append(stripped)
            continue
        if JP_INQUIRY_RE.match(stripped):
            flush()
            blocks.append(stripped)
            continue
        if JP_REVELATION_RE.match(stripped):
            flush()
            buf.append(stripped)
            continue
        if (
            not (line.startswith("　") or line.startswith("\u3000"))
            and JP_SECTION_TITLE_RE.fullmatch(stripped)
            and "御" not in stripped[:2]
            and len(stripped) <= 35
        ):
            flush()
            blocks.append(stripped)
            continue
        if (line.startswith("　") or line.startswith("\u3000")) and buf and JP_REVELATION_RE.match(buf[0]):
            flush()
            buf.append(stripped)
            continue
        if JP_SPEAKER_RE.match(stripped):
            flush()
            buf.append(stripped)
            continue
        buf.append(stripped)
    flush()
    return blocks


def dedupe_repeated_title(text: str) -> str:
    """Remove título duplicado colado: 'Luz X Luz X, publicado...'."""
    m = re.search(r"^(.+?),\s*publicado em", text)
    if not m:
        return text
    title = m.group(1).strip()
    doubled = re.fullmatch(r"(.+?)\s+\1", title, re.IGNORECASE)
    if not doubled:
        return text
    return text.replace(title, doubled.group(1).strip(), 1)


def split_publication_and_preface(out: str) -> str:
    """Separa ficha '..., publicado em ... (ano)' do prefácio/corpo."""
    out = dedupe_repeated_title(out)

    # Título A4 colado à ficha periódica (ex.: "...Tamesato Eiko nº 79, publicado em...")
    out = re.sub(
        r"^(.{10,120}?)\s+((?:Eiko|Kyusei|Mattō|Matto|Mattou|Hikari)\s+n\.?[ºo]?\s*\d+,\s*publicado em)",
        r"\1\n\n\2",
        out,
        count=1,
        flags=re.M | re.I,
    )

    # Ficha de publicação termina em (YYYY) — corpo começa depois
    out = re.sub(
        r"(publicado em [^\n(]+\(\d{4}\))\s+(?=[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ(«\"])",
        r"\1\n\n",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(
        r"(publicado em [^\n(]+\(\d{4}\))\s+(Prefácio|Prefacio|Introdução|Introducao)\b",
        r"\1\n\n\2",
        out,
        flags=re.IGNORECASE,
    )

    # Linha de atribuição / contexto entre parênteses (entrevistas Eiko)
    out = re.sub(
        r"(\(\d{4}\))\s+(\([^)]+\))\s+",
        r"\1\n\n\2\n\n",
        out,
    )
    out = re.sub(
        r"(\([^)]*(?:Entrevista|Diálogo|Dialogo|Jornal|Departamento|Vice-Chefe)[^)]*\))\s+",
        r"\1\n\n",
        out,
        flags=re.IGNORECASE,
    )

    # Dateline / lead após subtítulo de entrevista: "? — Em 4 de outubro..."
    out = re.sub(
        r"(\?\s*[—–-]\s*Em [^\n.!?…]+\.)\s+",
        r"\1\n\n",
        out,
        flags=re.IGNORECASE,
    )

    return out


def split_volume_reopen_blocks(out: str) -> str:
    """Segunda abertura editorial após prefácio (ex. Luz do Ensinamento)."""
    book_title = None
    m = re.search(r"^(.+?),\s*publicado em", out, re.M)
    if m:
        book_title = m.group(1).strip()
        doubled = re.fullmatch(r"(.+?)\s+\1", book_title, re.IGNORECASE)
        if doubled:
            book_title = doubled.group(1).strip()

    out = re.sub(
        r"(Maio do ano \d+ da Era Showa \(\d{4}\))\s+(O Editor)\b",
        r"\1\n\n\2",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(r"\b(O Editor)(?=\s+[A-ZÁÉÍÓÚ])", r"\1\n\n", out)

    if book_title:
        escaped = re.escape(book_title)
        out = re.sub(
            rf"\b({escaped})\s+(Questões de )",
            r"\1\n\n\2",
            out,
            flags=re.IGNORECASE,
        )

    out = re.sub(
        r"(Questões de [^\n]+?)\s+(A [A-ZÁÉÍÓÚ][^\n]{2,60}?)\s+(Interlocutor:)",
        r"\1\n\n\2\n\n\3",
        out,
    )
    out = re.sub(
        r"([A-ZÁÉÍÓÚÀÂÊÔÃÕÇ][^\n.!?…]{2,60}?)\s+(Interlocutor:)",
        r"\1\n\n\2",
        out,
    )
    return out


def apply_structural_layout(pt: str) -> str:
    """§4.4-A/B: cabeçalho, [data], falas e citações — sem reflow por tamanho."""
    out = (pt or "").replace("\r\n", "\n").strip()
    if not out:
        return out

    out = split_publication_and_preface(out)
    out = split_volume_reopen_blocks(out)

    out = re.sub(r"\)\s*\[", ")\n\n[", out)
    out = re.sub(r"(\[[^\]]+\])\s+(?!\n)", r"\1\n\n", out)
    out = re.sub(r"\]\s*(Interlocutor:|Meishu-Sama:)", r"]\n\n\1", out)
    out = re.sub(r"(?<!\n)\s+(Interlocutor:)", r"\n\n\1", out)
    out = re.sub(r"(?<!\n)\s+(Meishu-Sama:)", r"\n\n\1", out)
    out = re.sub(r'([.!?…][^"\n]*["\u201d])\s+(Meishu-Sama:)', r"\1\n\n\2", out)
    out = re.sub(r"(Interlocutor:[^\n]+?)\s+(Meishu-Sama:)", r"\1\n\n\2", out)
    out = re.sub(r"(?<=[.!?…])\s+(Meishu-Sama:)", r"\n\n\1", out)

    # Ficha periódica A4: Fonte nº N, publicado em...
    out = re.sub(
        r"(?<!\n)\s+([A-Z][A-Za-zÀ-ÿōūāīēŌŪĀĪĒ\-]{2,})\s+n\.?[ºo]\.?\s*(\d+,\s*publicado em)",
        r"\n\n\1 nº \2",
        out,
    )
    out = re.sub(
        r"([A-Za-zÀ-ÿōūāīēŌŪĀĪĒ\-]+)\s+n\.?[ºo]\.?\s*(\d+,\s*publicado em [^\n(]+\(\d{4}\))\s+",
        r"\1 nº \2\n\n",
        out,
    )

    out = re.sub(r"(\(\d{4}\))\s+(?=[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ\"«(])", r"\1\n\n", out)

    # Falantes nomeados (entrevistas Eiko): Sr. Tamesato:, Sr. Ōishi:
    out = re.sub(
        r'(?<!\n)\s+((?:Sr|Sra|Dr|Prof)\.\s+[A-Za-zÀ-ÿōūāīēŌŪĀĪĒ\-]+:)',
        r"\n\n\1",
        out,
    )

    # Título de seção colado ao corpo (Prefácio Este livreto...)
    out = re.sub(
        r"\b(Prefácio|Prefacio|Introdução|Introducao)\s+(?=[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ])",
        r"\1\n\n",
        out,
        flags=re.IGNORECASE,
    )

    out = re.sub(r'(?<=[.!?…])\s+(")', r"\n\n\1", out)
    out = re.sub(r'"\s+(?=[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ])', r'"\n\n', out)

    # Títulos de seção (Prefácio, etc.) em linha própria
    out = re.sub(
        r"(\(\d{4}\))\s+(Prefácio|Prefacio|Introdução|Introducao)\b",
        r"\1\n\n\2",
        out,
        flags=re.IGNORECASE,
    )

    return re.sub(r"\n{3,}", "\n\n", out).strip()


def label_dialogue_turns(text: str) -> str:
    """Add Interlocutor:/Meishu-Sama: when quotes/responses were collapsed."""
    out: list[str] = []
    expect_meishu = False
    for para in _split_paragraphs(text):
        if re.fullmatch(r"\[[^\]]+\]", para):
            expect_meishu = False
            out.append(para)
            continue
        if para.startswith("Interlocutor:"):
            expect_meishu = True
            out.append(para)
            continue
        if NAMED_SPEAKER_RE.match(para) or para.startswith("Meishu-Sama:"):
            expect_meishu = False
            out.append(para)
            continue
        if para.startswith('"'):
            out.append(f"Interlocutor: {para}")
            expect_meishu = True
            continue
        if expect_meishu:
            out.append(f"Meishu-Sama: {para}")
            expect_meishu = False
            continue
        out.append(para)
    return _join_paragraphs(out)


def _coalesce_jp_blocks(jp_blocks: list[str], target_count: int) -> list[str]:
    """Funde blocos JP adjacentes até target_count."""
    if target_count <= 0 or len(jp_blocks) <= target_count:
        return jp_blocks
    result: list[str] = []
    idx = 0
    for ti in range(target_count):
        if ti == target_count - 1:
            chunk = jp_blocks[idx:]
        else:
            remaining = target_count - ti - 1
            remaining_blocks = max(len(jp_blocks) - idx - remaining, 1)
            n = max(1, round(len(jp_blocks) / target_count))
            n = min(n, remaining_blocks)
            chunk = jp_blocks[idx : idx + n]
            idx += n
        if chunk:
            result.append("\n".join(chunk))
    return result


def _ideal_paragraph_count(jp_count: int, sentence_count: int) -> int:
    """Estima parágrafos PT quando JP tem mais blocos que frases (§4.4-F)."""
    if sentence_count <= 0 or jp_count <= sentence_count:
        return jp_count
    ratio = jp_count / sentence_count
    if ratio <= 1.2:
        return sentence_count
    return max(1, min(sentence_count, round(sentence_count**2 / jp_count)))


def _distribute_sentences_by_weights(sentences: list[str], jp_blocks: list[str]) -> str:
    weights = [max(len(block), 1) for block in jp_blocks]
    total_w = sum(weights)
    result: list[str] = []
    idx = 0
    for bi, weight in enumerate(weights):
        if bi == len(weights) - 1:
            chunk = " ".join(sentences[idx:])
        else:
            remaining_blocks = len(weights) - bi - 1
            remaining_sents = max(len(sentences) - idx - remaining_blocks, 1)
            n = max(1, round(len(sentences) * weight / total_w))
            n = min(n, remaining_sents)
            chunk = " ".join(sentences[idx : idx + n])
            idx += n
        if chunk.strip():
            result.append(chunk.strip())
    return _join_paragraphs(result)


def _distribute_sentences_by_char_weights(sentences: list[str], jp_blocks: list[str]) -> str:
    """Agrupa frases PT conforme peso de caracteres dos blocos JP (§4.4-F)."""
    if not sentences or not jp_blocks:
        return _join_paragraphs(sentences)
    if len(sentences) <= len(jp_blocks):
        return _distribute_sentences_by_weights(sentences, jp_blocks)

    fracs: list[float] = []
    lens = [max(len(re.sub(r"\s+", "", block)), 1) for block in jp_blocks]
    total = sum(lens)
    cum = 0.0
    for length in lens[:-1]:
        cum += length / total
        fracs.append(cum)

    sent_lens = [max(len(re.sub(r"\s+", "", s)), 1) for s in sentences]
    total_chars = sum(sent_lens)
    result: list[str] = []
    buf: list[str] = []
    char_count = 0
    target_i = 0

    for si, sent in enumerate(sentences):
        buf.append(sent)
        char_count += sent_lens[si]
        at_last = si == len(sentences) - 1
        past_target = target_i < len(fracs) and char_count >= fracs[target_i] * total_chars
        if at_last or (past_target and len(result) < len(jp_blocks) - 1):
            result.append(" ".join(buf).strip())
            buf = []
            target_i += 1

    if buf:
        if result:
            result[-1] = f"{result[-1]} {' '.join(buf)}".strip()
        else:
            result.append(" ".join(buf).strip())

    return _join_paragraphs(result)


def _reflow_body_by_jp_weights(body_pt: str, jp_body_blocks: list[str]) -> str:
    """Distribui frases do PT conforme peso relativo dos blocos JP (bidirecional)."""
    sentences = _split_sentences(body_pt)
    if not sentences or not jp_body_blocks:
        return body_pt.strip()

    jp_count = len(jp_body_blocks)
    sent_count = len(sentences)

    if jp_count == 1:
        return _join_paragraphs(sentences)

    if sent_count < jp_count:
        output_count = _ideal_paragraph_count(jp_count, sent_count)
        jp_coalesced = _coalesce_jp_blocks(jp_body_blocks, output_count)
        return _distribute_sentences_by_weights(sentences, jp_coalesced)

    return _distribute_sentences_by_char_weights(sentences, jp_body_blocks)


def _body_start_pt(pt_blocks: list[str]) -> int:
    for i, block in enumerate(pt_blocks):
        if PT_SPEAKER_RE.match(block):
            return i
    return len(pt_blocks)


def _body_start_jp(jp_blocks: list[str]) -> int:
    for i, block in enumerate(jp_blocks):
        if (
            JP_INQUIRY_RE.match(block)
            or JP_REVELATION_RE.match(block)
            or block.startswith("「")
            or JP_SPEAKER_RE.match(block)
        ):
            return i
    return len(jp_blocks)


def split_long_paragraphs_fallback(text: str, max_chars: int = LAYOUT_FALLBACK_MAX_CHARS) -> str:
    """Último recurso quando não há JP para alinhar e o bloco é enorme."""
    result: list[str] = []
    for para in _split_paragraphs(text):
        if len(para) <= max_chars:
            result.append(para)
            continue
        chunk = ""
        for sentence in _split_sentences(para):
            if chunk and len(chunk) + len(sentence) + 1 > max_chars:
                result.append(chunk.strip())
                chunk = sentence
            else:
                chunk = f"{chunk} {sentence}".strip() if chunk else sentence
        if chunk:
            result.append(chunk.strip())
    return _join_paragraphs(result)


def align_structural_paragraphs(jp_body: str, pt_text: str) -> list:
    """Pares JP/PT usando blocos estruturais do japonês (para revisão §6.2)."""
    from paragraph_glossary import ParagraphPair

    jp_paras = split_jp_structural_blocks(jp_body)
    pt_paras = _split_paragraphs(apply_structural_layout(pt_text))
    count = max(len(jp_paras), len(pt_paras), 1)
    pairs: list[ParagraphPair] = []
    for index in range(count):
        jp = jp_paras[index] if index < len(jp_paras) else ""
        pt = pt_paras[index] if index < len(pt_paras) else ""
        pairs.append(ParagraphPair(index=index, jp=jp, pt=pt))
    return pairs


def _paragraph_fingerprint(para: str) -> str:
    return re.sub(r"\s+", " ", (para or "").lower().strip())[:240]


def _sentence_fingerprint(sentence: str, *, prefix: int = 100) -> str:
    return re.sub(r"\s+", " ", (sentence or "").lower().strip())[:prefix]


SCRAMBLE_CLOSING_STARTERS = ("finalmente,", "por fim,", "em conclusão,")
SCRAMBLE_OPENING_MARKERS = (
    "edição especial",
    "distribuí esta",
    "até agora",
    "até o momento",
    "neste artigo",
    "sobre o cultivo natural",
)


def repair_scrambled_prose_opening(text: str) -> str:
    """Recoloca o início quando a tradução abre pelo fecho do original."""
    stripped = (text or "").strip()
    if not stripped:
        return text
    first_line = stripped.split("\n", 1)[0].strip()
    if PT_SPEAKER_RE.match(first_line) or first_line.startswith("["):
        return text

    sentences = _split_sentences(stripped)
    if len(sentences) < 3:
        return text
    if not any(sentences[0].lower().strip().startswith(marker) for marker in SCRAMBLE_CLOSING_STARTERS):
        return text

    for idx, sent in enumerate(sentences[1:], start=1):
        lowered = sent.lower()
        if any(marker in lowered for marker in SCRAMBLE_OPENING_MARKERS):
            rotated = sentences[idx:] + sentences[:idx]
            return " ".join(rotated)
    return text


def dedupe_repeated_sentences(text: str, *, min_chars: int = 48, fingerprint_chars: int = 100) -> str:
    """Remove frases repetidas (incl. quasi-duplicatas), mantendo a 1.ª ocorrência."""
    sentences = _split_sentences(text)
    if len(sentences) < 2:
        return text
    seen: set[str] = set()
    kept: list[str] = []
    for sent in sentences:
        key = _sentence_fingerprint(sent, prefix=fingerprint_chars)
        if len(key) >= min_chars and key in seen:
            continue
        if len(key) >= min_chars:
            seen.add(key)
        kept.append(sent)
    if len(kept) == len(sentences):
        return text
    return " ".join(kept)


def dedupe_repeated_sentence_runs(
    text: str,
    *,
    min_run: int = 3,
    max_run: int = 30,
) -> str:
    """Remove blocos consecutivos de frases já vistas antes no texto."""
    sentences = _split_sentences(text)
    if len(sentences) < min_run * 2:
        return text

    fps = [_sentence_fingerprint(s) for s in sentences]
    removed: set[int] = set()
    n = len(fps)
    upper_run = min(max_run, n // 2)

    for run_len in range(upper_run, min_run - 1, -1):
        seen: dict[tuple[str, ...], int] = {}
        for i in range(n - run_len + 1):
            if any(j in removed for j in range(i, i + run_len)):
                continue
            key = tuple(fps[i : i + run_len])
            if not all(key):
                continue
            prev = seen.get(key)
            if prev is not None and prev <= i - run_len:
                removed.update(range(i, i + run_len))
            elif prev is None:
                seen[key] = i

    if not removed:
        return text
    kept = [sent for idx, sent in enumerate(sentences) if idx not in removed]
    return " ".join(kept)


def cleanup_prose_duplication(text: str) -> str:
    """Pós-revisão: corrige ordem invertida e duplicação frasal (prosa A4)."""
    if not (text or "").strip():
        return text
    out = repair_scrambled_prose_opening(text)
    out = dedupe_repeated_sentence_runs(out)
    out = dedupe_repeated_sentences(out)
    return out


def dedupe_repeated_paragraphs(text: str, *, min_chars: int = 48) -> str:
    """Remove parágrafos idênticos (layout/reflow aplicado mais de uma vez)."""
    paras = _split_paragraphs(text)
    if len(paras) < 2:
        return text
    seen: set[str] = set()
    kept: list[str] = []
    for para in paras:
        key = _paragraph_fingerprint(para)
        if len(key) >= min_chars and key in seen:
            continue
        if len(key) >= min_chars:
            seen.add(key)
        kept.append(para)
    return _join_paragraphs(kept)


def apply_layout_protocol(pt: str, jp_body: str | None = None, *, jp_raw: str | None = None) -> str:
    """§4.4 layout: estrutura editorial + parágrafos conforme blocos do JP."""
    pt = cleanup_prose_duplication(pt)
    if jp_body:
        out = reflow_pt_by_jp_blocks(jp_body, pt, jp_raw=jp_raw)
    else:
        out = label_dialogue_turns(apply_structural_layout(pt))
        if jp_raw:
            out = ensure_header_from_jp_metadata(jp_raw, out)

    if len(_split_paragraphs(out)) == 1 and len(out) > LAYOUT_FALLBACK_MAX_CHARS:
        out = split_long_paragraphs_fallback(out)

    out = _join_paragraphs(split_collapsed_speaker_blocks(_split_paragraphs(out)))
    out = _drop_pure_cjk_paragraphs(out)
    out = dedupe_repeated_paragraphs(out)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def _drop_pure_cjk_paragraphs(text: str) -> str:
    kept: list[str] = []
    for para in _split_paragraphs(text):
        remainder = CJK_RE.sub("", para).strip(" ·-–—:.")
        if remainder:
            kept.append(para)
    return _join_paragraphs(kept)


@dataclass
class PilotCase:
    jp_path: str
    label: str
    max_chars: int | None = None
    pt_legacy_path: str | None = None


def select_glossary_entries(jp_text: str, glossary: dict, max_entries: int = 100) -> list[tuple[str, object]]:
    """All glossary terms present in JP, longest Japanese keys first."""
    selected: list[tuple[str, object]] = []
    for japanese, portuguese in glossary.items():
        if japanese in jp_text:
            selected.append((japanese, portuguese))
    selected.sort(key=lambda item: len(item[0]), reverse=True)
    return selected[:max_entries]


def build_translate_prompt(
    protocol: str,
    glossary_block: str,
    jp_chunk: str,
    *,
    part: int,
    total_parts: int,
    title: str,
) -> str:
    """Pass 6.1 — prose only; §7 JSON applies to review pass, not here."""
    if total_parts > 1:
        part_note = f"""
### CONTEXTO DE CHUNK ({part}/{total_parts})
- Traduza SOMENTE o japonês abaixo (parte {part} de {total_parts} do artigo «{title}»).
- Traduza TUDO: nenhum caractere japonês pode permanecer na saída.
- Em etimologia de kanji: use só português ou romaji; nunca reproduza kanji/hiragana.
- Não escreva "Parte {part}", marcadores ou notas do tradutor.
- {"Inclua o título traduzido na primeira linha." if part == 1 else "Não repita o título; continue a prosa naturalmente."}
"""
    else:
        part_note = """
### LEMBRETE
- Nenhum caractere japonês na saída (kanji, hiragana, katakana).
- Em explicações etimológicas: português ou romaji apenas; nunca "(五)" ou similares.
- Parágrafos: linha em branco entre cabeçalho, [data], cada fala (Interlocutor:/Meishu-Sama:) e cada bloco distinto do JP (por assunto).
- Nunca entregue o texto inteiro em um único parágrafo corrido; não divida por tamanho.
"""
    layout_note = """
### LAYOUT (obrigatório — §4.4)
- Cabeçalho A1–A4 em linhas/blocos separados; linha em branco entre cada bloco.
- A1 Gosuiji/Gokōwa: ficha + [data] + corpo; A4 Eiko/Kyusei: título + ficha periódica + corpo.
- [Data da sessão] sempre sozinha em uma linha; linha em branco; depois o corpo.
- Cada pergunta (Interlocutor:) e cada resposta (Meishu-Sama:) em parágrafo PRÓPRIO — nunca colados.
- Parágrafos: preserve as quebras do japonês (linha em branco = novo assunto/turno; 「 = pergunta).
- Nunca divida por tamanho de caracteres; divida por assunto conforme o original.
- Artigos Eiko/Kyusei: incluir «{Fonte} nº {N}, publicado em {data Showa + ocidental}» na linha 2.
"""
    return f"""{protocol}

### MODO 6.1 — TRADUÇÃO NOVA (somente japonês)
Ignore §7 (formato JSON) neste passe. Entregue APENAS prosa contínua em português brasileiro.
NÃO use JSON, markdown, blocos de código nem comentários do tradutor.
Respeite §4.4-A (cabecalhos A1–A4 por tipo de obra), §4.4-B (Interlocutor:/Meishu-Sama:) e §2.7 (nomes próprios transliterados).
{layout_note}
{part_note}
{glossary_block}

### TEXTO JAPONÊS (fonte — traduza integralmente):

{jp_chunk}

### TRADUÇÃO EM PORTUGUÊS (PT-BR):
"""


def extract_prose_from_response(raw: str) -> str:
    """If the model returns §7 JSON despite instructions, recover prose."""
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    if text.startswith("{") and '"paragraphs"' in text:
        parsed = parse_revision_response(text)
        if parsed and "paragraphs" in parsed:
            parts = []
            for item in sorted(parsed["paragraphs"], key=lambda x: int(x.get("index", 0))):
                pt = str(item.get("revised_pt") or "").strip()
                if pt:
                    parts.append(pt)
            if parts:
                return "\n\n".join(parts)

    return raw.strip()


def build_review_prompt(batch: list[dict], protocol: str, glossary_block: str) -> str:
    blocks = []
    for item in batch:
        blocks.append(
            f"### PARÁGRAFO {item['index']}\n"
            f"JP:\n{item['jp']}\n\n"
            f"PT (tradução recém-feita — revisar, não imitar PT antigo do acervo):\n{item['pt']}"
        )
    return f"""{protocol}

### MODO 6.2 — REVISÃO PÓS-TRADUÇÃO
Compare cada parágrafo JP ↔ PT novo. Corrija violações de glossário, fidelidade, fluidez e datas.
Verifique especialmente §4.4-A (cabecalho + [data] em blocos separados) e §4.4-B (Interlocutor:/Meishu-Sama:).
Nunca deixe pergunta e resposta no mesmo parágrafo. Artigos A4 exigem ficha «Fonte nº N, publicado em…».
Se o PT estiver em parágrafo único corrido, reformatar seguindo os blocos do japonês (linha em branco, ［data］, 「).
NÃO use o português antigo do acervo como critério de aceitação.
Responda APENAS com JSON válido conforme §7 do protocolo.

{glossary_block}

{chr(10).join(blocks)}
"""


def translate_jp_text(
    client,
    jp_body: str,
    protocol: str,
    glossary: dict,
    *,
    title: str,
    chunk_delay: float = 0.3,
    jp_raw: str | None = None,
    on_chunk: Callable[[int, int], None] | None = None,
) -> tuple[str, UsageTotal, list[dict]]:
    chunks = split_jp_chunks(jp_body)
    usage = UsageTotal()
    logs: list[dict] = []
    parts: list[str] = []
    total = len(chunks)

    for i, chunk in enumerate(chunks, start=1):
        if on_chunk:
            on_chunk(i, total)
        gloss = format_glossary_block(select_glossary_entries(chunk, glossary))
        prompt = build_translate_prompt(protocol, gloss, chunk, part=i, total_parts=total, title=title)
        pt_part, u = call_deepseek(client, prompt, max_tokens=MAX_OUTPUT_TOKENS)
        usage.add(u)
        pt_part = extract_prose_from_response(pt_part)
        pt_part = sanitize_pt_translation(pt_part).text
        logs.append({"pass": "translate", "part": i, "chars_jp": len(chunk), "chars_pt": len(pt_part), "usage": u})
        parts.append(pt_part)
        if i < total and chunk_delay:
            time.sleep(chunk_delay)

    return "\n\n".join(parts), usage, logs


def review_pt_text(
    client,
    jp_body: str,
    pt_draft: str,
    protocol: str,
    glossary: dict,
    *,
    chunk_delay: float = 0.3,
    jp_raw: str | None = None,
    on_progress: Callable[..., None] | None = None,
) -> tuple[str, UsageTotal, list[dict]]:
    pairs = align_structural_paragraphs(jp_body, pt_draft)
    if len(pairs) > MAX_REVIEW_PAIRS:
        return pt_draft, UsageTotal(), [
            {
                "pass": "review",
                "skipped": True,
                "reason": "too_many_pairs",
                "pairs": len(pairs),
                "max_pairs": MAX_REVIEW_PAIRS,
            }
        ]

    glossary_block = format_glossary_block(select_glossary_entries(jp_body, glossary))
    usage = UsageTotal()
    logs: list[dict] = []
    revised_by_index: dict[int, str] = {}
    n_batches = max(1, (len(pairs) + REVIEW_BATCH_SIZE - 1) // REVIEW_BATCH_SIZE)

    for batch_num, start in enumerate(range(0, len(pairs), REVIEW_BATCH_SIZE), start=1):
        if on_progress:
            on_progress(
                phase="review",
                review_batch=batch_num,
                review_batches_total=n_batches,
            )
        batch_pairs = pairs[start : start + REVIEW_BATCH_SIZE]
        batch = [{"index": p.index, "jp": p.jp, "pt": p.pt} for p in batch_pairs]
        prompt = build_review_prompt(batch, protocol, glossary_block)
        raw, u = call_deepseek(client, prompt, max_tokens=MAX_OUTPUT_TOKENS)
        usage.add(u)

        parsed = parse_revision_response(raw)
        record: dict = {
            "pass": "review",
            "start_index": batch_pairs[0].index,
            "usage": u,
            "parsed_ok": parsed is not None and "paragraphs" in (parsed or {}),
            "changes": [],
        }

        if parsed and "paragraphs" in parsed:
            for item in parsed["paragraphs"]:
                idx = int(item.get("index", -1))
                revised = str(item.get("revised_pt") or "").strip()
                if idx >= 0 and revised:
                    revised_by_index[idx] = revised
                if item.get("changed"):
                    record["changes"].append(
                        {"index": item.get("index"), "changes": item.get("changes", [])}
                    )
        else:
            record["error"] = "json_parse_failed"
            for p in batch_pairs:
                revised_by_index[p.index] = p.pt

        logs.append(record)
        if start + REVIEW_BATCH_SIZE < len(pairs) and chunk_delay:
            time.sleep(chunk_delay)

    revised = "\n\n".join(revised_by_index.get(p.index, p.pt) for p in pairs)
    return revised, usage, logs


def load_jp_excerpt(jp_path: Path, max_chars: int | None) -> tuple[str, str]:
    raw = jp_path.read_text(encoding="utf-8")
    body = strip_metadata(raw)
    title = extract_title(raw)
    if max_chars and len(body) > max_chars:
        body = body[:max_chars].rsplit("\n", 1)[0].strip()
    return body, title


def resolve_pt_legacy(jp_rel: str, pt_override: str | None) -> Path | None:
    if pt_override:
        path = PROJECT_ROOT / pt_override
        return path if path.exists() else None
    if jp_rel.startswith("textos_japones/"):
        candidate = PROJECT_ROOT / jp_rel.replace("textos_japones/", "textos_portugues/", 1)
        return candidate if candidate.exists() else None
    try:
        from run_retranslate_mass import build_jp_target_map

        mapped = build_jp_target_map().get(jp_rel)
        return mapped if mapped and mapped.exists() else None
    except Exception:
        return None


def run_api_passes(
    client,
    jp_path: Path,
    protocol: str,
    glossary: dict,
    *,
    max_chars: int | None = None,
    on_translate_chunk: Callable[[int, int], None] | None = None,
    on_progress: Callable[..., None] | None = None,
) -> dict:
    """Traduz + revisa + layout (sem glossário local nem QA final)."""
    jp_rel = str(jp_path.relative_to(PROJECT_ROOT))
    jp_raw = jp_path.read_text(encoding="utf-8")
    jp_body, title = load_jp_excerpt(jp_path, max_chars)

    def _progress(**fields: object) -> None:
        if on_progress:
            on_progress(**fields)
        elif on_translate_chunk and "chunk" in fields and "chunks_total" in fields:
            on_translate_chunk(int(fields["chunk"]), int(fields["chunks_total"]))

    def _on_translate_chunk(part: int, total: int) -> None:
        _progress(chunk=part, chunks_total=total, phase="translate")

    pt_draft, u1, t_logs = translate_jp_text(
        client,
        jp_body,
        protocol,
        glossary,
        title=title,
        jp_raw=jp_raw,
        on_chunk=_on_translate_chunk,
    )
    n_translate = len(t_logs) or 1
    _progress(chunk=n_translate, chunks_total=n_translate, phase="review")
    pt_final, u2, r_logs = review_pt_text(
        client,
        jp_body,
        pt_draft,
        protocol,
        glossary,
        jp_raw=jp_raw,
        on_progress=_progress,
    )
    pt_final = cleanup_prose_duplication(pt_final)
    qa_draft = validate_translation(jp_body, pt_draft)[1]
    _progress(chunk=n_translate, chunks_total=n_translate, phase="layout")
    pt_final = apply_layout_protocol(pt_final, jp_body=jp_body, jp_raw=jp_raw)

    usage = UsageTotal()
    for log in t_logs + r_logs:
        usage.add(log.get("usage") or {})

    return {
        "jp_path": jp_rel,
        "title": title,
        "jp_body": jp_body,
        "jp_raw": jp_raw,
        "chars_jp": len(jp_body),
        "pt_draft": pt_draft,
        "pt_final": pt_final,
        "translate_logs": t_logs,
        "review_logs": r_logs,
        "qa_draft": qa_draft,
        "n_translate": n_translate,
        "usage": {
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "total_tokens": usage.total_tokens,
            "api_calls": usage.api_calls,
            "usd": round(usage.usd(), 4),
            "brl": round(usage.brl(), 2),
        },
    }


def finalize_translation(
    api_result: dict,
    glossary: dict,
    *,
    on_progress: Callable[..., None] | None = None,
) -> dict:
    """Glossário §4.4-H + QA final (faixa local, pode correr em paralelo com API do próximo ficheiro)."""
    jp_body = api_result["jp_body"]
    pt_final = api_result["pt_final"]
    n_translate = int(api_result.get("n_translate") or 1)

    def _progress(**fields: object) -> None:
        if on_progress:
            on_progress(**fields)

    _progress(chunk=n_translate, chunks_total=n_translate, phase="glossary")
    pt_final, glossary_report = apply_post_translation_glossary(
        jp_body,
        pt_final,
        glossary,
        on_progress=_progress,
    )
    _progress(chunk=n_translate, chunks_total=n_translate, phase="qa")
    pt_final, qa_final = validate_translation(jp_body, pt_final, sanitize=True)
    glossary_issues = glossary_qa_issues(glossary_report)

    def qa_dict(qa, extra_issues: list[str] | None = None) -> dict:
        issues = list(qa.issues)
        for issue in extra_issues or []:
            if issue not in issues:
                issues.append(issue)
        return {"ok": qa.ok and not extra_issues, "issues": issues, "sanitized": qa.sanitized}

    return {
        **api_result,
        "pt_final": pt_final,
        "glossary_report": glossary_report,
        "qa_draft": qa_dict(api_result["qa_draft"]),
        "qa_final": qa_dict(qa_final, glossary_issues),
    }


def run_two_pass(
    client,
    jp_path: Path,
    protocol: str,
    glossary: dict,
    *,
    max_chars: int | None = None,
    on_translate_chunk: Callable[[int, int], None] | None = None,
    on_progress: Callable[..., None] | None = None,
) -> dict:
    api_result = run_api_passes(
        client,
        jp_path,
        protocol,
        glossary,
        max_chars=max_chars,
        on_translate_chunk=on_translate_chunk,
        on_progress=on_progress,
    )
    finalized = finalize_translation(api_result, glossary, on_progress=on_progress)
    return {
        "jp_path": finalized["jp_path"],
        "title": finalized["title"],
        "chars_jp": finalized["chars_jp"],
        "pt_draft": finalized["pt_draft"],
        "pt_final": finalized["pt_final"],
        "translate_logs": finalized["translate_logs"],
        "review_logs": finalized["review_logs"],
        "glossary_report": finalized["glossary_report"],
        "qa_draft": finalized["qa_draft"],
        "qa_final": finalized["qa_final"],
        "usage": finalized["usage"],
    }
