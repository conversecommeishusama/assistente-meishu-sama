#!/usr/bin/env python3
"""Shared retranslation logic (protocol, chunking, API, QA)."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from pathlib import Path

from run_deepseek_revision_pilot import (
    MODEL,
    format_glossary_block,
    load_glossary,
    select_glossary_entries,
)
from retranslate_qa import sanitize_pt_translation, validate_translation

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = PROJECT_ROOT / "protocolo_retraducao.txt"
JP_PUBLICATION = PROJECT_ROOT / "data" / "publication_sources" / "jp"
JP_BOOKS = PROJECT_ROOT / "textos_japones"

SINGLE_CALL_MAX_CHARS = 14_000
CHUNK_MAX_CHARS = 10_000
CHUNK_OVERLAP_CHARS = 500
MAX_OUTPUT_TOKENS = 12_000

METADATA_PREFIXES = (
    "Title:",
    "Publication source:",
    "Original publication",
    "Date:",
    "Language:",
    "Collection ID:",
    "Paired ",
    "Original path:",
    "Display ",
)
HEADER_KEYS = frozenset(
    {
        "Title",
        "Publication source",
        "Original publication reference",
        "Date",
        "Language",
        "Collection ID",
        "Paired Portuguese title",
        "Paired date",
        "Display source name",
    }
)


@dataclass
class UsageTotal:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    api_calls: int = 0

    def add(self, usage: dict) -> None:
        self.prompt_tokens += int(usage.get("prompt_tokens") or 0)
        self.completion_tokens += int(usage.get("completion_tokens") or 0)
        self.api_calls += 1

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def usd(self) -> float:
        return self.prompt_tokens * 0.14 / 1e6 + self.completion_tokens * 0.28 / 1e6

    def brl(self, fx: float = 5.8) -> float:
        return self.usd() * fx


def strip_metadata(text: str) -> str:
    lines = []
    for line in text.splitlines():
        if line.startswith(METADATA_PREFIXES):
            continue
        if line.strip():
            lines.append(line)
    return "\n".join(lines)


def extract_metadata_block(raw: str) -> list[str]:
    header: list[str] = []
    for line in raw.splitlines():
        key = line.split(":", 1)[0].strip() if ":" in line else ""
        if key in HEADER_KEYS or line.startswith("Paired "):
            header.append(line)
            continue
        if header and not line.strip():
            continue
        if header:
            break
    return header


def extract_title(raw: str) -> str:
    for line in raw.splitlines():
        if line.startswith("Title:"):
            return line.split(":", 1)[1].strip()
    body = strip_metadata(raw)
    return body.split("\n", 1)[0].strip()[:120] if body else "Sem título"


def list_jp_sources() -> list[Path]:
    paths = list(JP_PUBLICATION.rglob("*.txt")) + list(JP_BOOKS.glob("*.txt"))
    return sorted(set(paths))


def call_deepseek(client, prompt: str, *, max_tokens: int = MAX_OUTPUT_TOKENS) -> tuple[str, dict]:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
        max_tokens=max_tokens,
    )
    usage = {}
    if response.usage:
        usage = {
            "prompt_tokens": response.usage.prompt_tokens,
            "completion_tokens": response.usage.completion_tokens,
            "total_tokens": response.usage.total_tokens,
        }
    return response.choices[0].message.content or "", usage


def _coalesce_structural_blocks(blocks: list[str], chunk_max: int) -> list[str]:
    """Agrupa blocos estruturais JP até chunk_max sem partir blocos lógicos."""
    chunks: list[str] = []
    current = ""
    for block in blocks:
        block = (block or "").strip()
        if not block:
            continue
        if len(block) > chunk_max:
            if current:
                chunks.append(current.strip())
                current = ""
            # bloco único demasiado grande: subdivisão por parágrafo/linha
            sub = [p.strip() for p in re.split(r"\n\s*\n+", block) if p.strip()]
            if len(sub) <= 1:
                sub = [ln.strip() for ln in block.splitlines() if ln.strip()]
            sub_chunks: list[str] = []
            sub_cur = ""
            for piece in sub:
                cand = f"{sub_cur}\n\n{piece}".strip() if sub_cur else piece
                if len(cand) > chunk_max and sub_cur:
                    sub_chunks.append(sub_cur.strip())
                    sub_cur = piece
                else:
                    sub_cur = cand
            if sub_cur:
                sub_chunks.append(sub_cur.strip())
            chunks.extend(sub_chunks or [block[:chunk_max]])
            continue
        candidate = f"{current}\n\n{block}".strip() if current else block
        if len(candidate) > chunk_max and current:
            chunks.append(current.strip())
            current = block
        else:
            current = candidate
    if current:
        chunks.append(current.strip())
    return chunks


def split_jp_chunks(
    text: str,
    *,
    single_call_max: int | None = None,
    chunk_max_chars: int | None = None,
    structural: bool = True,
) -> list[str]:
    single_max = single_call_max if single_call_max is not None else SINGLE_CALL_MAX_CHARS
    chunk_max = chunk_max_chars if chunk_max_chars is not None else CHUNK_MAX_CHARS
    if len(text) <= single_max:
        return [text]

    if structural:
        from translation_protocol_core import split_jp_structural_blocks

        blocks = split_jp_structural_blocks(text)
        if blocks:
            structural_chunks = _coalesce_structural_blocks(blocks, chunk_max)
            if structural_chunks and (len(structural_chunks) > 1 or len(structural_chunks[0]) <= single_max):
                return structural_chunks

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", text) if p.strip()]
    if len(paragraphs) == 1 and len(paragraphs[0]) > chunk_max:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) > 1:
            paragraphs = lines

    overlap = min(CHUNK_OVERLAP_CHARS, chunk_max // 2)
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if len(para) > chunk_max:
            if current:
                chunks.append(current.strip())
                current = ""
            start = 0
            while start < len(para):
                end = min(len(para), start + chunk_max)
                piece = para[start:end].strip()
                if piece:
                    chunks.append(piece)
                if end >= len(para):
                    break
                next_start = end - overlap
                start = next_start if next_start > start else end
            continue
        candidate = f"{current}\n\n{para}".strip() if current else para
        if len(candidate) > chunk_max and current:
            chunks.append(current.strip())
            current = para
        else:
            current = candidate
    if current:
        chunks.append(current.strip())
    return chunks or [text]


def build_prompt(
    protocol: str,
    glossary_block: str,
    jp_chunk: str,
    *,
    part: int,
    total_parts: int,
    title: str,
) -> str:
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
"""
    return f"""{protocol}
{part_note}
{glossary_block}

### TEXTO JAPONÊS (fonte — traduza integralmente):

{jp_chunk}

### TRADUÇÃO EM PORTUGUÊS (PT-BR):
"""


def compose_pt_output(jp_raw: str, pt_translated: str, pt_existing: Path | None) -> str:
    """Monta arquivo PT final preservando cabeçalho de metadados quando aplicável."""
    translated = pt_translated.strip()
    if not translated:
        return "\n"

    jp_header = extract_metadata_block(jp_raw)
    if not jp_header:
        return translated + "\n"

    lines = translated.splitlines()
    title_line = lines[0].strip()
    body = "\n".join(lines[1:]).strip()

    pt_header_map: dict[str, str] = {}
    if pt_existing and pt_existing.exists():
        for line in pt_existing.read_text(encoding="utf-8").splitlines():
            if ":" in line:
                key = line.split(":", 1)[0].strip()
                pt_header_map[key] = line

    out_header: list[str] = []
    for line in jp_header:
        key = line.split(":", 1)[0].strip()
        if key == "Language":
            out_header.append("Language: pt")
        elif key == "Title":
            out_header.append(f"Title: {title_line}")
        elif key == "Collection ID" and key in pt_header_map:
            out_header.append(pt_header_map[key])
        elif key.startswith("Paired") and key in pt_header_map:
            out_header.append(pt_header_map[key])
        elif key in pt_header_map:
            out_header.append(pt_header_map[key])
        elif key.startswith("Paired"):
            continue
        else:
            out_header.append(line)

    parts = ["\n".join(out_header), "", title_line]
    if body:
        parts.extend(["", body])
    return "\n".join(parts) + "\n"


def retranslate_file(
    client,
    jp_path: Path,
    protocol: str,
    glossary: dict,
    *,
    chunk_delay: float = 0.3,
) -> tuple[str, UsageTotal, list[dict]]:
    raw = jp_path.read_text(encoding="utf-8")
    jp_body = strip_metadata(raw)
    title = extract_title(raw)
    chunks = split_jp_chunks(jp_body)
    usage = UsageTotal()
    chunk_logs: list[dict] = []
    translated_parts: list[str] = []

    for i, chunk in enumerate(chunks, start=1):
        gloss = format_glossary_block(select_glossary_entries(chunk, "", glossary, 55))
        prompt = build_prompt(protocol, gloss, chunk, part=i, total_parts=len(chunks), title=title)
        pt_part, u = call_deepseek(client, prompt, max_tokens=MAX_OUTPUT_TOKENS)
        usage.add(u)
        pt_part = sanitize_pt_translation(pt_part.strip()).text
        chunk_logs.append({"part": i, "chars_jp": len(chunk), "chars_pt": len(pt_part), "usage": u})
        translated_parts.append(pt_part)
        if i < len(chunks) and chunk_delay:
            time.sleep(chunk_delay)

    return "\n\n".join(translated_parts), usage, chunk_logs
