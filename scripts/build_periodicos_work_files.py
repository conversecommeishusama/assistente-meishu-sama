#!/usr/bin/env python3
"""Consolida artigos de periódicos (publication_sources) em ficheiros de trabalho JP/PT."""

from __future__ import annotations

import json
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from acervo_work_paths import article_sep as _article_sep  # noqa: E402
from translation_header_parser import (
    build_a4_header_from_jp_metadata,
    parse_jp_source_metadata,
    _strip_jp_body_prefix,
    _strip_leading_header_attempt,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ACERVO_ROOT = Path("/root/goshinsho/textos_japones")
ENTRIES_PATH = PROJECT_ROOT / "data/publication_sources/entries.jsonl"
TITLE_OVERRIDES_AUDIT_PATH = PROJECT_ROOT / "reports/periodicos_trabalho/TITLE_PT_OVERRIDES_AUDIT.json"
if not ENTRIES_PATH.is_file():
    _deploy_entries = Path("/var/www/goshinsho/data/publication_sources/entries.jsonl")
    if _deploy_entries.is_file():
        ENTRIES_PATH = _deploy_entries
JP_ROOT = PROJECT_ROOT / "data/publication_sources/jp"
PT_ROOT = PROJECT_ROOT / "data/publication_sources/pt"
STAGING_ROOTS = (
    PROJECT_ROOT
    / "reports/translation_review/retranslate_mass/20260619T142344Z/corpus",
    PROJECT_ROOT
    / "reports/translation_review/translation_mass/20260620T190000Z/corpus",
)
# compat: primeiro root usado por código legado
STAGING_ROOT = STAGING_ROOTS[0]

ARTICLE_SEP = _article_sep()
FORBIDDEN_SOURCE_TERMS = (
    "浄霊上",
    "浄霊下",
    "浄霊 上",
    "浄霊 下",
    "社会・自然農法",
    "芸術",
    "paraíso dos fundamentos",
    "glória dos fundamentos",
)

# Livros já no acervo — excluir do pacote de trabalho (fonte = acervo).
EXCLUDE_BOOK_CATEGORIES = {
    "Evangelho do Reino dos Céus",
    "Shinko Zatsuwa",
    "Jikan Sosho",
    "Salvando a América",
    "Terapia Revolucionária da Tuberculose",
    "Terapia de Fé para Tuberculose",
    "Guia Rápido da Igreja Messiânica Mundial",
    "Agricultura Natural",
    "Esboço da Medicina",
    "Verdadeira Natureza da Tuberculose",
}

# Periódicos e fontes a manter.
KEEP_PERIODICAL_CATEGORIES = {
    "Eiko",
    "Hikari",
    "Tijotengoku",
    "Kyusei",
    "Jornais",
    "Keiko",
    "Relatos de Milagres",
    "Revista Asahi",
    "Medicina do Amanhã",
}

# Agrupados como «Ensinamentos diversos» (direitos autorais — direitos autorais).
ENSINAMENTOS_DIVERSOS_CATEGORIES = {
    "Fonte Sem Periódico Identificado",
    "Registro de Palestras Médicas",
    "Movimento Kannon",
    "Fenômenos da Transição Noite-Dia",
}

OUTPUT_FILE_BY_CATEGORY = {
    "Eiko": "Eiko",
    "Hikari": "Hikari",
    "Tijotengoku": "Tijotengoku",
    "Kyusei": "Kyusei",
    "Jornais": "Jornais",
    "Keiko": "Keiko",
    "Relatos de Milagres": "Relatos_de_Milagres",
    "Revista Asahi": "Revista_Asahi",
    "Medicina do Amanhã": "Medicina_do_Amanha",
    "Fonte Sem Periódico Identificado": "Ensinamentos_diversos",
    "Registro de Palestras Médicas": "Ensinamentos_diversos",
    "Movimento Kannon": "Ensinamentos_diversos",
    "Fenômenos da Transição Noite-Dia": "Ensinamentos_diversos",
}

HEADER_SOURCE_LABEL = {
    **{c: c for c in KEEP_PERIODICAL_CATEGORIES},
    **{c: "Ensinamentos diversos" for c in ENSINAMENTOS_DIVERSOS_CATEGORIES},
}

ACERVO_GLOB_BY_CATEGORY: dict[str, list[str]] = {
    "Evangelho do Reino dos Céus": ["*天国の福音*"],
    "Shinko Zatsuwa": ["*信仰雑話*"],
    "Jikan Sosho": ["*自観叢書*"],
    "Salvando a América": ["*アメリカを救う*"],
    "Terapia Revolucionária da Tuberculose": ["*結核の革命的療法*"],
    "Terapia de Fé para Tuberculose": ["*結核信仰療法*"],
    "Guia Rápido da Igreja Messiânica Mundial": ["*世界救世教早わかり*"],
    "Esboço da Medicina": ["*医学試稿*"],
    "Agricultura Natural": ["*自然農法*"],
    "Verdadeira Natureza da Tuberculose": ["*結核*"],
}

CATALOG_SECTION_TITLE_SUFFIX = re.compile(
    r"\s*[（(][^）)]*(?:浄霊\s*[上下]|社会・自然農法|芸術)[^）)]*[）)]\s*$"
)
CATALOG_SECTION_CHUNK = re.compile(
    r"[（(][^）)]*(?:浄霊\s*[上下]|社会・自然農法|芸術\s*タイトル|芸術)[^）)]*[）)]"
)
PT_MONTHS = {
    "janeiro": 1,
    "fevereiro": 2,
    "março": 3,
    "marco": 3,
    "abril": 4,
    "maio": 5,
    "junho": 6,
    "julho": 7,
    "agosto": 8,
    "setembro": 9,
    "outubro": 10,
    "novembro": 11,
    "dezembro": 12,
}


@dataclass
class ArticleRecord:
    entry_id: str
    category: str
    output_file: str
    header_source: str
    sort_key: tuple
    jp_path: Path
    pt_path: Path | None
    jp_entry: dict
    pt_entry: dict | None
    acervo_note: str = ""


def slug_key(path: str) -> str:
    return re.sub(r"-publication-(?:jp|pt)-\d+\.txt$", "", Path(path).name)


def parse_pt_date(text: str) -> tuple:
    text = (text or "").strip().lower()
    if not text:
        return (9999, 12, 31)
    m = re.search(
        r"(\d{1,2})\s+de\s+(\w+)\s+(?:de\s+)?(?:do\s+ano\s+\d+\s+da\s+era\s+showa\s+\()?(\d{4})",
        text,
    )
    if m:
        day, month_name, year = int(m.group(1)), m.group(2), int(m.group(3))
        return (year, PT_MONTHS.get(month_name, 99), day)
    m = re.search(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", text)
    if m:
        day, month_name, year = int(m.group(1)), m.group(2), int(m.group(3))
        return (year, PT_MONTHS.get(month_name, 99), day)
    m = re.search(r"(\d{4})", text)
    if m:
        return (int(m.group(1)), 1, 1)
    return (9999, 12, 31)


def clean_title(text: str) -> str:
    text = CATALOG_SECTION_CHUNK.sub("", (text or "").strip())
    text = CATALOG_SECTION_TITLE_SUFFIX.sub("", text)
    for term in FORBIDDEN_SOURCE_TERMS:
        text = re.sub(re.escape(term), "", text, flags=re.IGNORECASE)
    return text.strip()


def clean_reference(text: str) -> str:
    text = CATALOG_SECTION_CHUNK.sub("", (text or "").strip())
    text = CATALOG_SECTION_TITLE_SUFFIX.sub("", text)
    return text.strip()


def sanitize_source_label(label: str) -> str:
    low = (label or "").lower()
    for term in FORBIDDEN_SOURCE_TERMS:
        if term in low:
            return ""
    return label.strip()


def load_entries() -> tuple[list[dict], dict[str, dict], dict[str, dict]]:
    entries = [json.loads(line) for line in ENTRIES_PATH.read_text(encoding="utf-8").splitlines()]
    jp = [e for e in entries if e.get("lang") == "jp"]
    pt_by_slug = {slug_key(e["clean_path"]): e for e in entries if e.get("lang") == "pt"}
    jp_by_id = {e["entry_id"]: e for e in jp}
    return jp, pt_by_slug, jp_by_id


def acervo_files_for_category(category: str) -> list[str]:
    patterns = ACERVO_GLOB_BY_CATEGORY.get(category, [])
    found: list[str] = []
    for pattern in patterns:
        for path in ACERVO_ROOT.glob(pattern):
            if path.is_file():
                found.append(path.name)
    return sorted(set(found))


def resolve_pt_path(jp_entry: dict, pt_entry: dict | None) -> Path | None:
    rel = pt_entry["clean_path"] if pt_entry else jp_entry["clean_path"]
    candidates: list[Path] = [root / rel for root in STAGING_ROOTS]
    candidates.append(PROJECT_ROOT / rel)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    if pt_entry:
        return PROJECT_ROOT / pt_entry["clean_path"]
    return None


def read_file_text(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


PT_TITLE_BODY_SPLITS = (
    " Embora ",
    " Porém ",
    " Contudo ",
    " No entanto, ",
    " Quem vê ",
    " Quem ler ",
    " Recentemente, ",
    " Hoje, ",
    " A maioria ",
    " A reencarnação ",
    " O que são ",
    " Escreverei ",
)

# Artigos sem par PT em publication_sources — título manual quando staging não separa título/corpo.
STAGING_PT_TITLE_OVERRIDES: dict[str, str] = {
    "publication-jp-1725": "Impressões sobre a Situação Atual",
    "publication-jp-1385": "O Princípio da nossa terapia",
    "publication-jp-1225": "As Três Grandes Calamidades e as Três Pequenas Calamidades",
    "publication-jp-1651": "O Mundo Semi-Civilizado e Semi-Selvagem",
    "publication-jp-1741": 'Gravação de Rua "Sobre a Situação Social Atual"',
    "publication-jp-1758": (
        "A Grande Revolução na Agricultura: O Aumento de 50% na Produção de Arroz em Cinco Anos é Certo"
    ),
    "publication-jp-1540": "Fragmentos Médicos (6) — Uma História Estranha (1)",
    "publication-jp-1301": "Johrei é Terapia Científica (Parte Final)",
    "publication-jp-1576": "Fragmentos de Terapia (42) — Bocejo",
    "publication-jp-1641": "Prefácio — Criação da Civilização",
}

# Títulos PT corrigidos manualmente (catálogo com kanji/CJK ou título colado ao corpo).
TITLE_PT_OVERRIDES: dict[str, str] = {
    # livros_acervo — títulos corrigidos na consolidação/P2
    "c5a4fb5e2ebe1fc4": "Coleção de Poemas Recentes de Meishu",
    "4cb4d652aa2f9ec9": "Gosuiji-roku nº 22",
    "30863d1d8f1f0aa4": "Memórias da Perseguição Legal",
    "publication-jp-1645": "Lei e Barbarie Humana",
    "publication-jp-1100": "Quatro Nobres Verdades e Decoro do Caminho da Doutrina",
    "publication-jp-1794": "Ciência e Arte",
    "publication-jp-1098": "Senso de Justiça",
    "publication-jp-1761": (
        "A Grande Revolução na Agricultura: Cultivo Doméstico sem Fertilizantes"
    ),
    "publication-jp-1099": "Ó Insensato! Teu Nome é Malvado",
    "publication-jp-1241": "Desfrutar a Vida",
    "publication-jp-1230": "Reflexão Espiritual sobre Incêndios",
    "publication-jp-1789": "O Paraíso é o Mundo da Arte",
    "publication-jp-1109": "Daijo e Shojo",
    "publication-jp-1046": "Fé Shojo",
    "publication-jp-1117": "Amor Daijo",
    "publication-jp-1030": "A Verdadeira Religião Daijo",
    "publication-jp-1115": "Seja Daijo",
    "publication-jp-1116": "Sejam Cidadãos do Mundo",
    "publication-jp-1836": "Diálogo Meishu-Sama e Tokugawa Musei (Arte)",
    **STAGING_PT_TITLE_OVERRIDES,
}


def _load_title_audit_overrides() -> dict[str, str]:
    if not TITLE_OVERRIDES_AUDIT_PATH.is_file():
        return {}
    try:
        data = json.loads(TITLE_OVERRIDES_AUDIT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return {k: v for k, v in data.items() if isinstance(v, str) and v.strip()}


TITLE_PT_OVERRIDES.update(_load_title_audit_overrides())


def parse_pt_title_from_raw(raw: str) -> str:
    """Extrai Title: de ficheiros staging/retranslate (sem par PT em entries.jsonl)."""
    if not raw:
        return ""
    first = raw.strip().splitlines()[0]
    if not first.startswith("Title:"):
        return ""
    rest = first[len("Title:") :].strip()
    m = re.match(r"\*\*(.+?)\*\*", rest)
    if m:
        return clean_title(m.group(1))
    best_idx: int | None = None
    for sep in PT_TITLE_BODY_SPLITS:
        idx = rest.find(sep)
        if idx > 10 and (best_idx is None or idx < best_idx):
            best_idx = idx
    if best_idx is not None:
        return clean_title(rest[:best_idx].strip())
    if len(rest) <= 100:
        return clean_title(rest)
    cut = rest[:100]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return clean_title(cut.strip())


def strip_staging_pt_body(raw: str, pt_title: str = "") -> str:
    """Corpo PT limpo: ignora Title: colado ao texto na linha 1 do staging."""
    lines = raw.splitlines()
    meta_end = 0
    in_meta = False
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            if in_meta:
                meta_end = i + 1
                in_meta = False
            continue
        if s.startswith(
            ("Title:", "Publication source:", "Original publication", "Date:", "Language:", "Collection ID:", "Paired ")
        ):
            in_meta = True
            continue
        if in_meta:
            meta_end = i
            in_meta = False
            break
    if meta_end < len(lines):
        tail = "\n".join(lines[meta_end:]).strip()
        if len(tail) > 80:
            body = _strip_leading_header_attempt(tail)
        else:
            body = strip_pt_metadata(raw)
    else:
        body = strip_pt_metadata(raw)
    title = clean_title(pt_title)
    titles_to_strip: list[str] = []
    for candidate in (title, parse_pt_title_from_raw(raw)):
        candidate = clean_title(candidate)
        if candidate and candidate not in titles_to_strip:
            titles_to_strip.append(candidate)
    for strip_title in titles_to_strip:
        if strip_title and len(strip_title) <= 95 and body.startswith(strip_title):
            body = body[len(strip_title) :].lstrip()
        bold_prefix = re.match(rf"^\*\*{re.escape(strip_title)}\*\*\s*", body)
        if bold_prefix:
            body = body[bold_prefix.end() :].lstrip()
    return body


def pick_pt_title(
    *,
    staging_raw: str,
    jp_entry: dict,
    pt_entry: dict | None,
    jp_meta: dict,
) -> str:
    entry_id = jp_entry.get("entry_id", "")
    if entry_id in TITLE_PT_OVERRIDES:
        return TITLE_PT_OVERRIDES[entry_id]
    candidates = (
        clean_title(jp_entry.get("paired_title_pt") or ""),
        parse_pt_title_from_raw(staging_raw),
        clean_title((pt_entry or {}).get("title") or ""),
        clean_title(jp_meta.get("Paired Portuguese title") or ""),
    )
    for title in candidates:
        if title and not re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", title):
            return title
    for title in candidates:
        if title:
            return title
    return clean_title(jp_meta.get("Title", ""))


def build_jp_meta_block(meta: dict[str, str], *, entry_id: str, header_source: str) -> str:
    title = clean_title(meta.get("Title", ""))
    lines = [
        f"Title: {title}",
        f"Publication source: {header_source}",
        f"Original publication reference: {clean_reference(meta.get('Original publication reference', ''))}",
        f"Date: {meta.get('Date', '')}",
        "Language: jp",
        f"Collection ID: {entry_id}",
    ]
    if meta.get("Paired Portuguese title"):
        lines.append(f"Paired Portuguese title: {clean_title(meta['Paired Portuguese title'])}")
    if meta.get("Paired date"):
        lines.append(f"Paired date: {meta['Paired date']}")
    return "\n".join(lines)


def build_pt_meta_block(
    meta: dict[str, str],
    *,
    entry_id: str,
    pt_entry_id: str,
    header_source: str,
    a4_header: str,
) -> str:
    title_line = a4_header.splitlines()[0] if a4_header else clean_title(meta.get("Paired Portuguese title") or meta.get("Title", ""))
    lines = [
        f"Title: {title_line}",
        f"Publication source: {header_source}",
        f"Original publication reference: {clean_reference(meta.get('Original publication reference', ''))}",
        f"Date: {meta.get('Date', '')}",
        "Language: pt",
        f"Collection ID: {pt_entry_id or entry_id}",
        f"Paired JP entry: {entry_id}",
    ]
    return "\n".join(lines)


def strip_pt_metadata(raw: str) -> str:
    lines = raw.splitlines()
    body_start = 0
    in_meta = False
    for i, line in enumerate(lines):
        s = line.strip()
        if not s:
            if in_meta:
                body_start = i + 1
                break
            continue
        if s.startswith(
            ("Title:", "Publication source:", "Original publication", "Date:", "Language:", "Collection ID:", "Paired ")
        ):
            in_meta = True
            continue
        if in_meta:
            body_start = i
            break
        return _strip_leading_header_attempt(raw)
    body = "\n".join(lines[body_start:]).strip()
    return _strip_leading_header_attempt(body)


def format_article_block(
    *,
    lang: str,
    meta_block: str,
    a4_header: str,
    body: str,
    entry_id: str,
    paired_id: str,
    header_source: str,
    sort_date: str,
    title_jp: str,
    title_pt: str,
) -> str:
    parts = [
        ARTICLE_SEP,
        f"entry_id: {entry_id}",
        f"paired_id: {paired_id or ''}",
        f"source_file: {header_source}",
        f"sort_date: {sort_date}",
        f"title_jp: {title_jp}",
        f"title_pt: {title_pt}",
        "---",
        meta_block,
        "",
    ]
    if a4_header:
        parts.extend([a4_header, ""])
    parts.append(body.strip())
    parts.append("")
    return "\n".join(parts)


def classify_jp_entry(entry: dict) -> tuple[str, str] | None:
    category = entry.get("source_category", "")
    if category in EXCLUDE_BOOK_CATEGORIES:
        return "exclude", category
    if category in KEEP_PERIODICAL_CATEGORIES | ENSINAMENTOS_DIVERSOS_CATEGORIES:
        output = OUTPUT_FILE_BY_CATEGORY[category]
        header = HEADER_SOURCE_LABEL[category]
        return output, header
    return None


def main() -> None:
    out_root = PROJECT_ROOT / "reports/periodicos_trabalho"
    jp_out = out_root / "jp"
    pt_out = out_root / "pt"
    excl_out = out_root / "excluidos"
    for d in (jp_out, pt_out, excl_out):
        d.mkdir(parents=True, exist_ok=True)

    jp_entries, pt_by_slug, _ = load_entries()
    keep: list[ArticleRecord] = []
    excluded: list[dict] = []

    for jp_entry in jp_entries:
        decision = classify_jp_entry(jp_entry)
        if not decision:
            excluded.append(
                {
                    "entry_id": jp_entry["entry_id"],
                    "category": jp_entry.get("source_category"),
                    "title": jp_entry.get("title"),
                    "reason": "unmapped_category",
                }
            )
            continue
        kind, detail = decision
        if kind == "exclude":
            acervo = acervo_files_for_category(detail)
            excluded.append(
                {
                    "entry_id": jp_entry["entry_id"],
                    "category": detail,
                    "title": jp_entry.get("title"),
                    "source_date": jp_entry.get("source_date"),
                    "reason": "acervo_book",
                    "acervo_files": acervo,
                    "acervo_verified": bool(acervo),
                }
            )
            continue

        output_file, header_source = decision
        slug = slug_key(jp_entry["clean_path"])
        pt_entry = pt_by_slug.get(slug)
        jp_path = PROJECT_ROOT / jp_entry["clean_path"]
        pt_path = resolve_pt_path(jp_entry, pt_entry)
        sort_key = parse_pt_date(jp_entry.get("source_date") or (pt_entry or {}).get("source_date", ""))
        keep.append(
            ArticleRecord(
                entry_id=jp_entry["entry_id"],
                category=jp_entry.get("source_category", ""),
                output_file=output_file,
                header_source=header_source,
                sort_key=sort_key,
                jp_path=jp_path,
                pt_path=pt_path,
                jp_entry=jp_entry,
                pt_entry=pt_entry,
            )
        )

    grouped: dict[str, list[ArticleRecord]] = defaultdict(list)
    for rec in keep:
        grouped[rec.output_file].append(rec)
    for items in grouped.values():
        items.sort(key=lambda r: (r.sort_key, r.entry_id))

    manifest = {
        "total_jp_entries": len(jp_entries),
        "kept": len(keep),
        "excluded": len(excluded),
        "output_files": {k: len(v) for k, v in sorted(grouped.items())},
    }

    jp_buffers: dict[str, list[str]] = defaultdict(list)
    pt_buffers: dict[str, list[str]] = defaultdict(list)

    missing_pt: list[str] = []

    for output_file, items in sorted(grouped.items()):
        for rec in items:
            jp_raw = read_file_text(rec.jp_path)
            if not jp_raw and rec.jp_entry.get("body"):
                jp_raw = rec.jp_entry["body"]
            meta = parse_jp_source_metadata(jp_raw)
            if not meta.get("Title"):
                meta["Title"] = clean_title(rec.jp_entry.get("title", ""))
            meta["Publication source"] = rec.header_source
            meta["Title"] = clean_title(meta.get("Title", ""))
            if meta.get("Original publication reference"):
                meta["Original publication reference"] = clean_reference(meta["Original publication reference"])
            if meta.get("Paired Portuguese title"):
                meta["Paired Portuguese title"] = clean_title(meta["Paired Portuguese title"])

            jp_body = _strip_jp_body_prefix(jp_raw)
            jp_meta_block = build_jp_meta_block(meta, entry_id=rec.entry_id, header_source=rec.header_source)

            pt_entry_id = (rec.pt_entry or {}).get("entry_id", "")
            pt_raw = read_file_text(rec.pt_path) if rec.pt_path else ""
            if not pt_raw and rec.pt_entry and rec.pt_entry.get("body"):
                pt_raw = rec.pt_entry["body"]

            pt_meta = dict(meta)
            pt_meta["Publication source"] = rec.header_source
            pt_title = pick_pt_title(
                staging_raw=pt_raw,
                jp_entry=rec.jp_entry,
                pt_entry=rec.pt_entry,
                jp_meta=meta,
            )
            pt_meta["Paired Portuguese title"] = pt_title
            a4_header = build_a4_header_from_jp_metadata(
                pt_meta, jp_path=str(rec.jp_path), jp_raw=jp_raw
            )
            if a4_header:
                a4_lines = a4_header.splitlines()
                a4_lines[0] = pt_title
                a4_header = "\n".join(a4_lines)

            if not pt_raw:
                missing_pt.append(rec.entry_id)
                pt_body = ""
            else:
                pt_body = strip_staging_pt_body(pt_raw, pt_title)

            sort_date = rec.jp_entry.get("source_date") or (rec.pt_entry or {}).get("source_date") or ""
            title_jp = meta.get("Title", "")
            title_pt = pt_title

            jp_buffers[output_file].append(
                format_article_block(
                    lang="jp",
                    meta_block=jp_meta_block,
                    a4_header="",
                    body=jp_body,
                    entry_id=rec.entry_id,
                    paired_id=pt_entry_id,
                    header_source=rec.header_source,
                    sort_date=sort_date,
                    title_jp=title_jp,
                    title_pt=title_pt,
                )
            )
            pt_meta_block = build_pt_meta_block(
                pt_meta,
                entry_id=rec.entry_id,
                pt_entry_id=pt_entry_id,
                header_source=rec.header_source,
                a4_header=a4_header,
            )
            pt_buffers[output_file].append(
                format_article_block(
                    lang="pt",
                    meta_block=pt_meta_block,
                    a4_header=a4_header,
                    body=pt_body,
                    entry_id=rec.entry_id,
                    paired_id=pt_entry_id,
                    header_source=rec.header_source,
                    sort_date=sort_date,
                    title_jp=title_jp,
                    title_pt=title_pt,
                )
            )

    for output_file in sorted(set(jp_buffers) | set(pt_buffers)):
        header = (
            f"# Ficheiro de trabalho: {output_file}\n"
            f"# Artigos: {len(grouped[output_file])}\n"
            f"# Ordenação: cronológica (sort_date)\n"
            f"# Fonte: publicação original (Publication source / Original publication reference)\n\n"
        )
        (jp_out / f"{output_file}.txt").write_text(header + "".join(jp_buffers[output_file]), encoding="utf-8")
        (pt_out / f"{output_file}.txt").write_text(header + "".join(pt_buffers[output_file]), encoding="utf-8")

    (excl_out / "inventario_exclusoes.jsonl").write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in excluded) + ("\n" if excluded else ""),
        encoding="utf-8",
    )
    manifest["missing_pt"] = missing_pt
    manifest["missing_pt_count"] = len(missing_pt)
    (out_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    readme = f"""Pacote de trabalho — ensinamentos de revistas e jornais

Decisões aplicadas:
- Medicina do Amanhã (明日の医術): mantida (24 artigos)
- Livros do acervo: excluídos ({len(excluded)} artigos) — ver excluidos/inventario_exclusoes.jsonl
- Ensinamentos sem periódico claro: Ensinamentos_diversos.txt
- Secções 浄霊 / 社会・自然農法 / 芸術: nunca aparecem como fonte; usa-se a publicação original

Artigos incluídos: {len(keep)}
Ficheiros JP/PT: {len(grouped)}
missing_pt: {len(missing_pt)}

Estrutura:
  jp/   — textos japoneses consolidados
  pt/   — textos portugueses consolidados (cabeçalho A4 alinhado ao JP)
  excluidos/inventario_exclusoes.jsonl

Separador entre artigos: === ARTIGO ===
"""
    (out_root / "README.txt").write_text(readme, encoding="utf-8")

    zip_path = out_root / "periodicos_trabalho.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(out_root.rglob("*")):
            if path.is_file() and path.name != zip_path.name:
                zf.write(path, path.relative_to(out_root).as_posix())

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"\nOutput: {out_root}")
    print(f"ZIP: {zip_path} ({zip_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
