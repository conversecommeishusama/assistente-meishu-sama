#!/usr/bin/env python3
"""Corrigir 観音講座 PT: cabeçalhos §4.4, paragrafação JP-first, artefactos."""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from translation_protocol_core import (  # noqa: E402
    _join_paragraphs,
    _reflow_pt_paragraphs_to_jp,
    _split_paragraphs,
    split_jp_prose_paragraphs,
    split_jp_structural_blocks,
)

FILENAME = "19350000-観音講座　（１～７）.txt"
WORK = Path("/var/www/goshinsho/reports/livros_trabalho")

LECTURES = [
    ("Primeira Aula", "O Propósito do Deus Principal e a Verdadeira Natureza do Plano Divino para o Paraíso e a Terra"),
    ("Segunda Aula", "A Origem da Religião e o Advento do Salvador"),
    ("Terceira Aula", "A Essência do Bodhisattva Kannon"),
    ("Quarta Aula", "A Realidade dos Três Mundos: Divino, Espiritual e Material"),
    ("Quinta Aula", "A Verdade do Bem e do Mal e a Construção do Mundo Luminoso"),
    ("Sexta Aula", "A Missão do Japão e dos Países Estrangeiros"),
    ("Sétima Aula", "Princípio da Doença e do Método de Saúde Absoluta"),
]

SESSION_DATES = [
    r"\(15 de julho de 1935[^)]*\)",
    r"\(25 de julho de 1935\)",
    r"\(5 de agosto de 1935\)",
    r"\(15 de agosto de 1935\)",
    r"\(25 de agosto de 1935\)",
    r"\(5 de setembro de 1935\)",
    r"\(15 de setembro de 1935\)",
]

HEADER_JUNK_RE = re.compile(
    r"^(?:\*\*)?(?:Curso de Kannon|Palestra(?:s)? sobre Kannon|Palestra Kannon|"
    r"Segundo Curso|Terceira Palestra|Quarta Palestra|Quinta Aula|Sexta Aula|"
    r"Sétima Palestra|\*\*Palestra sobre Kannon\*\*|\*\*Terceira Palestra\*\*)"
    r"(?:\*\*)?\s*$",
    re.I,
)


def strip_jp_lecture(chunk: str) -> str:
    lines: list[str] = []
    skip = 0
    for ln in chunk.splitlines():
        s = ln.strip()
        if re.match(r"第[一二三四五六七]講座", s):
            skip = 2
            continue
        if skip:
            skip -= 1
            continue
        if s in {"観音講座", "観音講座　（１～７）　講座を弟子が筆録したもの"}:
            continue
        if re.match(r"^観音講座\s*$", s):
            continue
        lines.append(ln)
    return "\n".join(lines).strip()


def split_jp_lectures(jp_body: str) -> list[str]:
    parts = re.split(r"(第[一二三四五六七]講座[^\n]*)", jp_body)
    return [strip_jp_lecture(parts[i + 1]) for i in range(1, len(parts), 2)]


def split_pt_by_dates(body: str) -> list[str]:
    """Parte o corpo PT pelas datas de sessão (7 aulas)."""
    markers: list[tuple[int, int]] = []
    for pat in SESSION_DATES:
        m = re.search(pat, body)
        if not m:
            raise ValueError(f"Data de sessão não encontrada: {pat}")
        markers.append((m.start(), m.end()))
    markers.sort()
    chunks: list[str] = []
    prev = 0
    for start, end in markers:
        chunks.append(body[prev:end].strip())
        prev = end
    if prev < len(body):
        tail = body[prev:].strip()
        if tail:
            chunks[-1] = f"{chunks[-1]}\n\n{tail}".strip()
    return chunks


def clean_lecture_body(text: str) -> str:
    lines = []
    for ln in text.splitlines():
        if HEADER_JUNK_RE.match(ln.strip()):
            continue
        if re.match(r"^\*\*(Primeira|Segunda|Terceira|Quarta|Quinta|Sexta|Sétima) Aula\*\*", ln):
            continue
        if ln.strip().startswith("**") and ln.strip().endswith("**") and "Aula" not in ln:
            # subtítulo antigo duplicado — removido; re-inserimos depois
            if any(sub in ln for _, sub in LECTURES):
                continue
        lines.append(ln)
    return "\n".join(lines).strip()


def safe_reflow(jp_body: str, pt_body: str, *, structural: bool) -> str:
    jp_blocks = split_jp_structural_blocks(jp_body) if structural else split_jp_prose_paragraphs(jp_body)
    pt_blocks = _split_paragraphs(pt_body)
    if not jp_blocks or not pt_blocks:
        return pt_body
    aligned = _reflow_pt_paragraphs_to_jp(pt_blocks, jp_blocks)
    return _join_paragraphs(aligned)


def apply_post_patches(text: str) -> str:
    text = text.replace("\n---\n\n**Primeira", "\n\n**Primeira")
    text = re.sub(
        r"superior a essa\.\s+não\.\s+Era",
        "superior a essa. Era",
        text,
    )
    text = re.sub(
        r"\n---\n\nO centro do universo",
        "\n\nO centro do universo",
        text,
    )
    for _title, subtitle in LECTURES:
        text = re.sub(
            rf"(\*\*{re.escape(subtitle)}\*\*\s*\n\n){re.escape(subtitle)}\s+",
            r"\1",
            text,
        )
    text = re.sub(
        r"No final, os espíritos de divindades e a Ciência se unem\. os espíritos",
        "No final, os espíritos de divindades e a Ciência se unem. Os espíritos",
        text,
    )
    text = text.replace(
        "Este espíritos de divindades e a Ciência",
        "Os espíritos de divindades e a Ciência",
    )
    text = re.sub(r"\n espíritos de divindades =", "\nEspíritos de divindades =", text)
    text = re.sub(r"\n Ciência = Exterior", "\nCiência = Exterior", text)
    text = text.replace(
        "Esta palestra é a mais importante da série de palestras Kannon",
        "Esta aula é a mais importante da série de aulas Kannon",
    )
    text = text.replace("Interlocutor:", "")
    return text


def main() -> int:
    jp_path = WORK / "jp" / FILENAME
    pt_path = WORK / "pt" / FILENAME
    jp_body = jp_path.read_text(encoding="utf-8").split("---", 1)[1]
    pt_full = pt_path.read_text(encoding="utf-8")

    anchor = pt_full.find("**Primeira Aula**")
    if anchor < 0:
        anchor = pt_full.find("O que vou explicar a partir de agora")
    if anchor < 0:
        raise SystemExit("Corpo PT não encontrado")

    prefix = pt_full[:anchor].replace("\n---\n\n", "\n\n").rstrip()
    body = pt_full[anchor:]

    jp_lectures = split_jp_lectures(jp_body)
    pt_lectures = split_pt_by_dates(body)
    if len(jp_lectures) != 7 or len(pt_lectures) != 7:
        raise SystemExit(f"Contagem aulas JP={len(jp_lectures)} PT={len(pt_lectures)}")

    out_parts = [prefix, ""]
    for i, ((title, subtitle), jp_chunk, pt_chunk) in enumerate(
        zip(LECTURES, jp_lectures, pt_lectures)
    ):
        cleaned = clean_lecture_body(pt_chunk)
        # 1ª aula: blocos kotodama/tabelas — preservar paragrafação PT; só normalizar cabeçalho
        if i == 0:
            reflowed = cleaned
        else:
            reflowed = safe_reflow(jp_chunk, cleaned, structural=False)
        # títulos internos em negrito (secções JP) — linha própria
        reflowed = re.sub(
            r"(\*\*[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ][^*]{3,80}\*\*)\s+",
            r"\1\n\n",
            reflowed,
        )
        header = f"**{title}**\n\n**{subtitle}**"
        out_parts.append(f"{header}\n\n{reflowed.strip()}")
        out_parts.append("")

    result = apply_post_patches("\n".join(out_parts).rstrip() + "\n")
    pt_path.write_text(result, encoding="utf-8")

    # métricas
    def count_paras(t: str) -> int:
        n = 0
        active = False
        for ln in t.splitlines():
            if ln.strip():
                if not active:
                    n += 1
                    active = True
            else:
                active = False
        return n

    body_out = result[result.find("**Primeira Aula**") :]
    print(f"OK {FILENAME}")
    for i, (title, _) in enumerate(LECTURES):
        jp_n = len(
            split_jp_structural_blocks(jp_lectures[i])
            if i == 0
            else split_jp_prose_paragraphs(jp_lectures[i])
        )
        # extrair secção PT
        pat = rf"\*\*{re.escape(title)}\*\*"
        ms = list(re.finditer(pat, body_out))
        if not ms:
            print(f"  {title}: header missing")
            continue
        start = ms[0].start()
        next_titles = [LECTURES[j][0] for j in range(i + 1, 7)]
        end = len(body_out)
        for nt in next_titles:
            nm = re.search(rf"\*\*{re.escape(nt)}\*\*", body_out[start + 1 :])
            if nm:
                end = start + 1 + nm.start()
                break
        pt_n = count_paras(body_out[start:end])
        flag = "OK" if jp_n == pt_n else f"delta {pt_n - jp_n:+d}"
        print(f"  {title}: JP={jp_n} PT={pt_n} [{flag}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
