#!/usr/bin/env python3
"""Reconstrói o monólito PT do 御教え集1号 em ordem JP (9 sessões por data)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import work_root  # noqa: E402
from fix_periodicos_work_headers import format_article, parse_article, split_file  # noqa: E402

FILENAME = "19510920-御教え集1号.txt"
SNAPSHOT_PT = (
    Path(__file__).resolve().parents[1]
    / "reports/acervo_revision/snapshots/livros_acervo"
    / "2026-06-27T012356Z__livros_acervo__P2_cabecalhos__pre"
    / "livros_trabalho/pt"
    / FILENAME
)

SESSION_SPLIT = re.compile(
    r"\*\*(1º de agosto|5 de agosto \(Neste dia apenas, não baseado em taquigrafia\)|8 de agosto)\*\*"
)
DATE_HEADER = {
    "1º de agosto": "1 de agosto",
    "5 de agosto (Neste dia apenas, não baseado em taquigrafia)": "5 de agosto",
    "8 de agosto": "8 de agosto",
}
SESSION_MARKERS = (
    "1 de agosto",
    "5 de agosto",
    "8 de agosto",
    "11 de agosto",
    "16 de agosto",
    "18 de agosto",
    "21 de agosto",
    "25 de agosto",
    "28 de agosto",
)
INLINE_SESSION_RE = re.compile(
    r"(?<!\d)(1|5|8|11|16|18|21|25|28) de agosto\s*(\(Pergunta\)|\n|\Z)",
    re.I,
)


def _normalize_labels(text: str) -> str:
    text = text.replace("(Instrução Divina)", "[Resposta Divina]")
    text = re.sub(r"\[Ensinamento\]", "[Ensinamento]", text)
    text = re.sub(r"\*\*Coleção de Ensinamentos[^\n]*\*\*\s*", "", text)
    return text.strip()


def _trim_partial_last_question(block: str) -> str:
    matches = list(re.finditer(r"\(Pergunta\)", block))
    if len(matches) < 2:
        return block
    last = matches[-1]
    tail = block[last.start() :]
    if tail.rstrip().endswith("..."):
        return block[: last.start()].rstrip()
    if len(tail) < 400 and not re.search(r"\[Resposta Divina\]|\[Revelação Divina\]", tail):
        return block[: last.start()].rstrip()
    return block


def _split_inline_session(mega: str, day: str, next_day: str | None) -> str:
    """Extrai sessão de mega-linha ``N de agosto (Pergunta)…``."""
    start_pat = rf"{day} de agosto\s*(\(Pergunta\)|\[)"
    m = re.search(start_pat, mega, re.I)
    if not m:
        return ""
    start = m.start()
    if next_day:
        end_m = re.search(rf"{next_day} de agosto\s*(\(Pergunta\)|\[)", mega[m.end() :], re.I)
        end = m.end() + end_m.start() if end_m else len(mega)
    else:
        end = len(mega)
    body = mega[start:end].strip()
    body = re.sub(rf"^{day} de agosto\s*", "", body, count=1, flags=re.I).strip()
    return body


def _dedupe_shimizu_question(text: str) -> str:
    """Remove fragmento duplicado da pergunta de Sumiichi Shimizu (18/ago)."""
    marker = "(Pergunta) Sou um crente chamado Sumiichi Shimizu"
    first = text.find(marker)
    if first < 0:
        return text
    second = text.find(marker, first + 20)
    if second < 0:
        return text
    dup = text.find("mas, em abril de 1949, fiz um exame de saúde na repartição fiscal", second)
    if dup < 0:
        return text
    resp = text.find("[Revelação Divina]", dup)
    if resp < 0:
        return text[:second].rstrip() + "\n\n" + text[dup:].lstrip()
    return text[:second].rstrip() + "\n\n" + text[dup:].lstrip()


def _dedupe_taizo_shide(text: str) -> str:
    """Remove variante duplicada Shite Daizō (25/ago); mantém Taizo Shide."""
    pat = r"\n?\(Pergunta\) Shite Daiz[ōo][^\[]*?\[Resposta Divina\][^\[]*?(?=\[Ensinamento\])"
    return re.sub(pat, "\n\n", text, count=1, flags=re.S)


def _dedupe_pneumonia_question(text: str) -> str:
    """Remove pneumonia duplicada embutida na resposta (28/ago)."""
    inline = (
        r"\(Pergunta\) Duas crianças, uma menina de treze anos"
        r".*?\[Resposta Divina\]\s*A pneumonia é uma boa purificação\."
        r".*?(?=\(Pergunta\) Em 3 de fevereiro)"
    )
    return re.sub(inline, "", text, count=1, flags=re.S)


def _merge_session_8(mega_body: str, aug8_tail: str) -> str:
    body = _trim_partial_last_question(_normalize_labels(mega_body))
    tail = _normalize_labels(aug8_tail)
    if not tail:
        return body
    if not body:
        return tail
    return body.rstrip() + "\n\n" + tail.lstrip()


def _extract_sessions_1_5_8(snapshot_text: str) -> list[str]:
    lines = snapshot_text.splitlines()
    if len(lines) < 76:
        raise ValueError("Snapshot PT demasiado curto")

    mega = lines[24]
    parts = SESSION_SPLIT.split(mega)
    if len(parts) < 7:
        raise ValueError("Mega-bloco do snapshot sem 3 sessões iniciais")

    aug8_tail = "\n".join(lines[32:75]).strip()
    chunks: list[str] = []
    for i in range(1, len(parts), 2):
        key = parts[i]
        body = parts[i + 1]
        header = DATE_HEADER.get(key, key.replace("º", "").split("(")[0].strip())
        if header == "8 de agosto":
            body = _merge_session_8(body, aug8_tail)
        else:
            body = _normalize_labels(body)
        chunks.append(f"{header}\n\n{body}")

    return chunks[:3]


def _line_range_body(lines: list[str], start: int, end: int) -> str:
    return _normalize_labels("\n".join(lines[start:end]).strip())


def _extract_from_snapshot(snapshot_text: str) -> str:
    lines = snapshot_text.splitlines()
    chunks = _extract_sessions_1_5_8(snapshot_text)

    # 11 de agosto: linhas 76-92 (até header 16)
    i11 = next(i for i, ln in enumerate(lines) if ln.strip() == "11 de agosto")
    i16 = next(i for i, ln in enumerate(lines) if ln.strip() == "16 de agosto")
    chunks.append(_line_range_body(lines, i11, i16))

    mega_inline = lines[96] if len(lines) > 96 else ""

    # 16 de agosto: versão completa inline em L96 (descarta 93-95 truncadas)
    s16 = _split_inline_session(mega_inline, "16", "18")
    if not s16:
        s16 = _line_range_body(lines, i16 + 1, min(i16 + 4, len(lines)))
    chunks.append(f"16 de agosto\n\n{s16}")

    # 18 de agosto: inline em L96 + continuação L97-107
    s18_head = _split_inline_session(mega_inline, "18", None)
    i21 = next(i for i, ln in enumerate(lines) if ln.strip() == "21 de agosto")
    s18_tail = _line_range_body(lines, 97, i21)
    s18 = s18_head
    if s18_tail:
        if s18 and not s18.endswith(s18_tail[:40]):
            s18 = s18.rstrip() + "\n\n" + s18_tail
        elif not s18:
            s18 = s18_tail
    s18 = _dedupe_shimizu_question(s18)
    chunks.append(f"18 de agosto\n\n{s18}")

    # 21 de agosto
    i25 = next(i for i, ln in enumerate(lines) if ln.strip() == "25 de agosto")
    chunks.append(f"21 de agosto\n\n" + _line_range_body(lines, i21 + 1, i25))

    # 25 de agosto
    i28 = next(i for i, ln in enumerate(lines) if ln.strip() == "28 de agosto")
    s25 = _line_range_body(lines, i25 + 1, i28)
    s25 = _dedupe_taizo_shide(s25)
    chunks.append(f"25 de agosto\n\n{s25}")

    # 28 de agosto
    s28 = _line_range_body(lines, i28 + 1, len(lines))
    s28 = _dedupe_pneumonia_question(s28)
    chunks.append(f"28 de agosto\n\n{s28}")

    return "\n\n".join(c for c in chunks if c.strip())


def rebuild_pt(snapshot_path: Path, target_path: Path) -> tuple[str, str]:
    snap_text = snapshot_path.read_text(encoding="utf-8")
    body_new = _extract_from_snapshot(snap_text)

    target_text = target_path.read_text(encoding="utf-8")
    header, blocks = split_file(target_text)
    art = parse_article(blocks[0])
    rebuilt = header.rstrip() + "\n" + format_article(art.fields, art.meta, body_new) + "\n"
    target_path.write_text(rebuilt, encoding="utf-8")
    return body_new, rebuilt


def main() -> int:
    p = argparse.ArgumentParser(description="Reconstrói PT do Mioshie-shu 1号 em ordem JP")
    p.add_argument("--work-root", type=Path, default=None)
    p.add_argument("--snapshot", type=Path, default=SNAPSHOT_PT)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    wr = args.work_root or work_root("livros_acervo")
    target = wr / "pt" / FILENAME
    if not args.snapshot.is_file():
        print(f"ERRO: snapshot não encontrado: {args.snapshot}", file=sys.stderr)
        return 1
    if not args.dry_run and not target.is_file():
        print(f"ERRO: PT alvo não encontrado: {target}", file=sys.stderr)
        return 1

    body = _extract_from_snapshot(args.snapshot.read_text(encoding="utf-8"))
    dates = re.findall(r"^(1|5|8|11|16|18|21|25|28) de agosto\b", body, re.M)
    print(f"Sessões PT (marcadores de data): {len(dates)} -> {dates}")
    print(f"Corpo reconstruído: {len(body):,} chars")

    if args.dry_run:
        return 0

    rebuild_pt(args.snapshot, target)
    print(f"Escrito: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
