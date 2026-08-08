#!/usr/bin/env python3
"""Corrige cabeçalhos §4.4-A nos ficheiros consolidados periodicos_trabalho."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from apply_source_reference_glossary_fixes import apply_rules as apply_source_ref_rules  # noqa: E402
from translation_header_parser import (  # noqa: E402
    audit_translation_header,
    build_a4_header_from_jp_metadata,
    normalize_dates_in_pt_text,
    normalize_translation_header,
    parse_jp_source_metadata,
    strip_header_region,
    _is_ficha_line as strict_is_ficha_line,
    _peel_glued_header_line,
    _strip_jp_body_prefix,
    _strip_leading_header_attempt,
    GENERIC_PUB_RE,
    PERIODICAL_FICHA_RE,
    PUBLICATION_FICHA_RE,
    SERIES_FICHA_RE,
)

from build_periodicos_work_files import (  # noqa: E402
    STAGING_PT_TITLE_OVERRIDES,
    TITLE_PT_OVERRIDES,
    parse_pt_title_from_raw,
    strip_staging_pt_body,
)

from acervo_work_paths import work_root, article_sep as _article_sep  # noqa: E402

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORK_ROOT = work_root()
ARTICLE_SEP = _article_sep()
article_sep = _article_sep  # re-export — imports legados
PT_PRODUCTION = PROJECT_ROOT / "textos_portugues"
LIVROS_WORK = "livros_trabalho" in str(WORK_ROOT)

PT_SOURCE_LABEL = {
    "Eiko": "Eikō",
    "Hikari": "Hikari",
    "Kyusei": "Kyusei",
    "Tijotengoku": "Paraíso na Terra",
    "Jornais": "Jornais",
    "Keiko": "Keiko",
    "Relatos de Milagres": "Relatos de Milagres",
    "Revista Asahi": "Revista Asahi",
    "Medicina do Amanhã": "Medicina do Amanhã",
    "Ensinamentos diversos": "Ensinamentos diversos",
}

FICHA_LINE_FIXES = (
    (re.compile(r"^Eiko\b"), "Eikō"),
    (re.compile(r"^Glória\b"), "Eikō"),
    (re.compile(r"^Tijotengoku\b"), "Paraíso na Terra"),
    (re.compile(r"^Paraíso Terrestre\b"), "Paraíso na Terra"),
    (re.compile(r"^Céu na Terra\b"), "Paraíso na Terra"),
    (re.compile(r"^Luz\b"), "Hikari"),
    (re.compile(r"^Salvação do Mundo\b"), "Kyusei"),
    (re.compile(r"^Mensagem de Salvação\b"), "Kyusei"),
)

REF_LINE_FIXES = (
    (re.compile(r'(\("?)Glória\b'), r"\1Eikō"),
    (re.compile(r'(\("?)Luz\b'), r"\1Hikari"),
    (re.compile(r'(\("?)Salvação do Mundo\b'), r"\1Kyusei"),
    (re.compile(r'(\("?)Paraíso Terrestre\b'), r"\1Paraíso na Terra"),
    (re.compile(r'(\("?)Paraíso na Terra\b'), r"\1Paraíso na Terra"),
    (re.compile(r'(\("?)Céu na Terra\b'), r"\1Paraíso na Terra"),
    (re.compile(r'(\("?)Evangelho do Paraíso\b'), r"\1Evangelho do Reino dos Céus"),
    (re.compile(r'(\("?)O Evangelho do Paraíso\b'), r"\1O Evangelho do Reino dos Céus"),
)


CATALOG_SECTION_TITLE_SUFFIX = re.compile(
    r"\s*[（(][^）)]*(?:浄霊\s*[上下]|社会・自然農法|芸術)[^）)]*[）)]\s*$"
)
CATALOG_SECTION_CHUNK = re.compile(
    r"[（(][^）)]*(?:浄霊\s*[上下]|社会・自然農法|芸術\s*タイトル|芸術)[^）)]*[）)]"
)
FORBIDDEN_SOURCE_TERMS = (
    "浄霊上",
    "浄霊下",
    "浄霊 上",
    "浄霊 下",
    "社会・自然農法",
    "芸術",
)


@dataclass
class Article:
    fields: dict[str, str]
    meta: str
    content: str


def split_file(text: str) -> tuple[str, list[str]]:
    if ARTICLE_SEP not in text:
        return text, []
    parts = text.split(ARTICLE_SEP)
    header = parts[0]
    blocks = [b for b in parts[1:] if b.strip()]
    return header, blocks


def parse_article(block: str) -> Article:
    fields: dict[str, str] = {}
    if "---" not in block:
        return Article(fields, "", block.strip())
    pre, post = block.split("---", 1)
    for line in pre.strip().splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            fields[key.strip()] = val.strip()
    post = post.strip()
    meta_lines: list[str] = []
    content_lines: list[str] = []
    in_meta = True
    for line in post.splitlines():
        s = line.strip()
        if in_meta and s.startswith(
            ("Title:", "Publication source:", "Original publication", "Date:", "Language:", "Collection ID:", "Paired ")
        ):
            meta_lines.append(line)
            continue
        if in_meta and not s:
            continue
        in_meta = False
        content_lines.append(line)
    return Article(fields, "\n".join(meta_lines).strip(), "\n".join(content_lines).strip())


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


def apply_label_fixes(text: str) -> str:
    text, _ = apply_source_ref_rules(text)
    lines = text.splitlines()
    out: list[str] = []
    for line in lines:
        if line.startswith("Publication source:"):
            src = line.split(":", 1)[1].strip()
            line = f"Publication source: {PT_SOURCE_LABEL.get(src, src)}"
        elif line.startswith("Original publication reference:"):
            val = line.split(":", 1)[1]
            for pat, repl in REF_LINE_FIXES:
                val = pat.sub(repl, val)
            line = f"Original publication reference:{val}"
        elif "publicado em" in line.lower() and not line.startswith("Date:"):
            for pat, repl in FICHA_LINE_FIXES:
                line = pat.sub(repl, line)
        out.append(line)
    return "\n".join(out)


CJK_LINE_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")


COLOPHON_LINE_RE = re.compile(
    r"^(?:Formato\b|Autor:|Editor(?: responsável)?:|Editora:|Impress[ãa]o:|Páginas?:|\d+\s*páginas|Não comercializ)",
    re.I,
)
_CITATION_QUOTED = r"['\"'«»][^'\"'«»]+['\"'«»]"
PROSE_CITATION_TAIL_RE = re.compile(
    rf"^(.{{80,}}?)\s*((?:\*\*)?\s*(?:{_CITATION_QUOTED}|Revista Eikō|Coletânea|Mensagem de Salvação|Terapia[^,]{{0,40}})\s*,?\s*(?:n[º°]\s*\d+,\s*)?publicado em .+?\(\d{{4}}\))\s*$",
    re.I,
)


def _ficha_date_key(line: str) -> str:
    m = re.search(r"\((\d{4})\)", line)
    return m.group(1) if m else line.strip().lower()


def _peel_leading_body_line(line: str) -> tuple[str, str]:
    """Separa subtítulo/byline colado ao início do corpo."""
    s = (line or "").strip()
    if not s:
        return "", ""
    peeled = _peel_glued_header_line(s)
    if peeled and peeled[1]:
        return peeled[0].strip(), peeled[1].strip()
    idx = s.find("**")
    if idx > 15:
        head, tail = s[:idx].strip(), s[idx:].strip()
        bold = re.match(r"^(\*\*[^*]+\*\*)\s+(.+)$", tail, re.DOTALL)
        if bold:
            return f"{head}\n{bold.group(1).strip()}".strip(), bold.group(2).strip()
    bold = re.match(r"^(.{0,120}?\*\*[^*]+\*\*)\s+(.+)$", s)
    if bold:
        return bold.group(1).strip(), bold.group(2).strip()
    section = re.match(
        r"^((?:(?:Okada )?Mokiti|Matsui Seikun|O Autor))\s+"
        r"((?:A Grande Batida Policial|A Medicina Cria a Tuberculose|.+?))\s+"
        r"((?:Como|Eliminar|No ano|Prefácio)\b.+)$",
        s,
    )
    if section and len(section.group(2)) <= 80:
        return section.group(2).strip(), section.group(3).strip()
    byline = re.match(
        r"^((?:Okada|Matsui|Membro|Fundador|Registrado por:|Jikan\b)[^\n]{0,100}?)\s+((?:[A-ZÁÉÍÓÚÀÈÌÒÙÂÊÔÃÕÇ]|\"|\[).+)$",
        s,
    )
    if byline and len(byline.group(1)) <= 80:
        return byline.group(1).strip(), byline.group(2).strip()
    return "", s


def _colophon_follows(lines: list[str], start: int) -> int:
    j = start + 1
    while j < len(lines) and j < start + 12:
        t = lines[j].strip()
        if not t:
            j += 1
            continue
        if (
            COLOPHON_LINE_RE.match(t)
            or GENERIC_PUB_RE.match(t)
            or t.startswith("Não comercializável")
            or t.startswith("Impressor:")
        ):
            j += 1
            continue
        break
    return j


def strip_colophon_blocks(body: str, title_pt: str = "") -> str:
    """Remove blocos de colofão duplicados (publicado em + Formato/Autor/…)."""
    lines = body.splitlines()
    out: list[str] = []
    i = 0
    title_pt = (title_pt or "").strip()
    while i < len(lines):
        s = lines[i].strip()
        if title_pt and s == title_pt and i > 0:
            j = _colophon_follows(lines, i)
            if j > i + 1 or (j == i + 2 and GENERIC_PUB_RE.match(lines[i + 1].strip())):
                i = j
                continue
        if GENERIC_PUB_RE.match(s):
            j = _colophon_follows(lines, i)
            if j > i + 1:
                i = j
                continue
        out.append(lines[i])
        i += 1
    return "\n".join(out).strip()


def split_prose_citation_tails(body: str) -> str:
    """Separa citações bibliográficas coladas ao fim de parágrafos longos."""
    out: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        if len(s) >= 200:
            match = PROSE_CITATION_TAIL_RE.match(s)
            if match:
                out.append(match.group(1).rstrip())
                out.append(defang_citation_line(match.group(2).strip()))
                continue
        out.append(line)
    return "\n".join(out).strip()


def defang_citation_line(line: str) -> str:
    s = (line or "").strip()
    if not s or "publicado em" not in s.lower():
        return s
    s = re.sub(r",\s*publicado em\s+", " — ", s, flags=re.I)
    s = re.sub(r"(?<=[\d'\"»])\s+publicado em\s+", " — ", s, count=1, flags=re.I)
    s = re.sub(r"\bPublicado em\s+", " — ", s, count=1)
    return s


def defang_bibliographic_citations(body: str) -> str:
    """Citações de testemunho não devem imitar ficha §4.4-A."""
    out: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        if s and re.search(r"\bpublicado em\b", s, re.I):
            if len(s) > 150 and not GENERIC_PUB_RE.match(s):
                s = re.sub(
                    rf"({_CITATION_QUOTED}\s*,?\s*(?:n[º°]\s*\d+,\s*)?)publicado em\s+",
                    r"\1— ",
                    s,
                    flags=re.I,
                )
                s = re.sub(
                    r"((?:Revista|Coletânea|Terapia|Salvando|Mensagem)[^,]{0,80},\s*)publicado em\s+",
                    r"\1— ",
                    s,
                    flags=re.I,
                )
                s = re.sub(
                    r"(‘[^’]+’\s*,?\s*(?:n[º°]\s*\d+,\s*)?)publicado em\s+",
                    r"\1— ",
                    s,
                    flags=re.I,
                )
            elif len(s) <= 280 and (s[0] in "'\"«(" or re.match(r"^['\"«]", s) or s.startswith("—")):
                s = defang_citation_line(s)
        out.append(s if not line.strip() else line[: len(line) - len(line.lstrip())] + s)
    return "\n".join(out).strip()


def strip_redundant_bare_publication(body: str) -> str:
    """Remove «publicado em …» solto quando a data já consta na ficha."""
    pub_dates: set[str] = set()
    out: list[str] = []
    for line in body.splitlines():
        s = line.strip()
        if strict_is_ficha_line(s) and not GENERIC_PUB_RE.match(s):
            pub_dates.add(_ficha_date_key(s))
            out.append(line)
            continue
        if GENERIC_PUB_RE.match(s):
            key = _ficha_date_key(s)
            if key in pub_dates:
                continue
            pub_dates.add(key)
        out.append(line)
    return "\n".join(out).strip()


def polish_livros_pt_body(body: str, title_pt: str = "") -> str:
    body = strip_colophon_blocks(body, title_pt=title_pt)
    body = strip_redundant_bare_publication(body)
    body = split_prose_citation_tails(body)
    body = defang_bibliographic_citations(body)
    return body.strip()


def body_needs_production_reload(content: str) -> bool:
    stripped = [ln.strip() for ln in content.splitlines() if ln.strip()]
    if any(ln.startswith("...") for ln in stripped):
        return True
    for i, ln in enumerate(stripped):
        if GENERIC_PUB_RE.match(ln) and i > 2:
            tail = stripped[i + 1 : i + 5]
            if any(t.startswith("Formato") or t.startswith("Autor:") for t in tail):
                return True
    for i in range(1, len(stripped) - 1):
        if stripped[i] == stripped[0] and GENERIC_PUB_RE.match(stripped[i + 1]):
            return True
    return False


def load_production_pt_body(filename: str, title_pt: str) -> str | None:
    path = PT_PRODUCTION / filename
    if not path.is_file():
        return None
    raw = path.read_text(encoding="utf-8")
    title = parse_pt_title_from_raw(raw) or title_pt
    return strip_staging_pt_body(raw, title)


def extract_clean_pt_body(content: str, title_pt: str, title_jp: str = "") -> str:
    """Remove cabeçalho A4 duplicado, título JP e eco de título PT no corpo."""
    body = _strip_leading_header_attempt((content or "").strip())
    lines = body.splitlines()
    title_pt = (title_pt or "").strip()
    title_jp = (title_jp or "").strip()
    seen_ficha_dates: set[str] = set()
    i = 0
    while i < len(lines) and i < 18:
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        if title_jp and s == title_jp:
            i += 1
            continue
        if title_jp and len(s) <= 120 and CJK_LINE_RE.search(s) and len(s) == len(title_jp):
            i += 1
            continue
        if title_jp and s.startswith(title_jp[: min(len(title_jp), 40)]):
            if CJK_LINE_RE.search(s):
                i += 1
                continue
        if title_pt and s == title_pt:
            i += 1
            continue
        if strict_is_ficha_line(s) or GENERIC_PUB_RE.match(s):
            key = _ficha_date_key(s)
            if key in seen_ficha_dates:
                i += 1
                continue
            seen_ficha_dates.add(key)
            i += 1
            continue
        if COLOPHON_LINE_RE.match(s):
            i += 1
            continue
        break
    remaining = lines[i:]
    if remaining:
        head, tail = _peel_leading_body_line(remaining[0].strip())
        if head and tail:
            remaining[0] = tail
    body = "\n".join(remaining).strip()
    body = strip_colophon_blocks(body, title_pt=title_pt)
    if title_pt and len(title_pt) <= 95 and body.startswith(title_pt):
        body = body[len(title_pt) :].lstrip()
    elif title_pt:
        glued = re.match(rf"^{re.escape(title_pt)}\s+(?=\S)", body)
        if glued:
            body = body[glued.end() :].lstrip()
    bold = re.match(r"^\*\*(.+?)\*\*\s*", body)
    if bold and title_pt and bold.group(1).strip() == title_pt:
        body = body[bold.end() :].lstrip()
    if bold and title_pt and bold.group(1).strip() != title_pt:
        body = body[bold.end() :].lstrip()
    return body.strip()


def pick_pt_title(jp_meta: dict[str, str], pt_body: str, fields: dict[str, str]) -> str:
    entry_id = fields.get("entry_id", "")
    if entry_id in TITLE_PT_OVERRIDES:
        return TITLE_PT_OVERRIDES[entry_id]
    if entry_id in STAGING_PT_TITLE_OVERRIDES:
        return STAGING_PT_TITLE_OVERRIDES[entry_id]
    paired = clean_title(jp_meta.get("Paired Portuguese title") or fields.get("title_pt", ""))
    bold_match = re.search(r"\*\*([^*]{5,160}?)\*\*", pt_body[:3000])
    bold = clean_title(bold_match.group(1)) if bold_match else ""
    bad_paired = (
        len(paired) > 90
        or paired.startswith(("Meishu-Sama:", "No ano passado", "Em suma,", "Title:"))
        or "?" in paired[:3]
    )
    if bold and (bad_paired or not paired):
        return bold
    return paired or bold or clean_title(jp_meta.get("Title", ""))


def dedupe_ficha_lines(content: str) -> str:
    lines = content.splitlines()
    out: list[str] = []
    seen_ficha: set[str] = set()
    for line in lines:
        key = line.strip().lower()
        if "publicado em" in key:
            if key in seen_ficha:
                continue
            seen_ficha.add(key)
        out.append(line)
    return "\n".join(out).strip()


def _strip_orphan_title_echo(content: str, title_pt: str) -> str:
    """Remove linha-título errada colada antes da ficha (corrupção do catálogo)."""
    lines = content.splitlines()
    if len(lines) < 3:
        return content
    title_pt = (title_pt or "").strip()
    cleaned: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if (
            s
            and s != title_pt
            and "publicado em" not in s.lower()
            and not s.startswith("**")
            and len(s) < 120
            and (s.startswith("Meishu-Sama:") or s.startswith("Title:") or s.endswith("?"))
        ):
            i += 1
            continue
        cleaned.append(line)
        i += 1
    return "\n".join(cleaned).strip()


def rebuild_pt_content(
    article: Article,
    jp_article: Article,
    *,
    source_filename: str = "",
) -> tuple[str, list[str]]:
    entry_id = article.fields.get("entry_id", "")
    jp_path = f"data/publication_sources/jp/work/{entry_id}.txt"
    jp_raw = jp_article.meta + "\n\n" + jp_article.content if jp_article.meta else jp_article.content
    jp_meta = parse_jp_source_metadata(jp_raw)
    src_key = article.fields.get("source_file", jp_meta.get("Publication source", ""))
    label = PT_SOURCE_LABEL.get(src_key, src_key)
    if jp_meta:
        jp_meta["Publication source"] = label

    pt_body = article.content
    if not pt_body.strip():
        return "", ["empty_pt_body"]

    title_pt = pick_pt_title(jp_meta, pt_body, article.fields)
    title_jp = clean_title(jp_meta.get("Title", "") or article.fields.get("title_jp", ""))
    if LIVROS_WORK and source_filename and body_needs_production_reload(pt_body):
        fresh = load_production_pt_body(source_filename, title_pt)
        if fresh:
            pt_body = fresh
            title_pt = pick_pt_title(jp_meta, pt_body, article.fields)
    pt_body = strip_header_region(pt_body, prepend_orphans=False)[0]
    pt_body = extract_clean_pt_body(pt_body, title_pt, title_jp)
    if LIVROS_WORK:
        pt_body = polish_livros_pt_body(pt_body, title_pt=title_pt)
    jp_meta["Paired Portuguese title"] = title_pt

    header = build_a4_header_from_jp_metadata(jp_meta, jp_path=jp_path, jp_raw=jp_raw)
    if header:
        hlines = header.splitlines()
        hlines[0] = title_pt
        header = "\n".join(hlines)
        normalized = f"{header}\n\n{pt_body.strip()}"
    else:
        normalized = normalize_translation_header(jp_raw, pt_body, jp_path=jp_path)

    normalized = dedupe_ficha_lines(normalized)
    normalized = _strip_orphan_title_echo(normalized, title_pt)
    normalized = apply_label_fixes(normalized)
    normalized = normalize_dates_in_pt_text(normalized)

    issues = audit_translation_header(normalized, jp_raw=jp_raw, jp_path=jp_path)
    blocking = [i for i in issues if i not in {"header_unparsed", "glossary_residual_makyo", "body_before_header"}]
    return normalized, blocking


def build_pt_meta(article: Article, pt_content: str, jp_article: Article) -> str:
    jp_raw = jp_article.meta + "\n\n" + jp_article.content
    jp_meta = parse_jp_source_metadata(jp_raw)
    src_key = article.fields.get("source_file", "")
    label = PT_SOURCE_LABEL.get(src_key, src_key)
    title_pt = pick_pt_title(jp_meta, pt_content, article.fields)
    jp_meta["Publication source"] = label
    jp_meta["Paired Portuguese title"] = title_pt
    a4 = build_a4_header_from_jp_metadata(jp_meta, jp_path=f"data/publication_sources/jp/work/{article.fields.get('entry_id','')}.txt", jp_raw=jp_raw)
    if a4:
        lines = a4.splitlines()
        lines[0] = title_pt
        a4 = "\n".join(lines)

    lines = [
        f"Title: {title_pt}",
        f"Publication source: {label}",
        f"Original publication reference: {clean_reference(jp_meta.get('Original publication reference', ''))}",
        f"Date: {jp_meta.get('Date') or article.fields.get('sort_date', '')}",
        "Language: pt",
        f"Collection ID: {article.fields.get('paired_id') or article.fields.get('entry_id', '')}",
        f"Paired JP entry: {article.fields.get('entry_id', '')}",
    ]
    block = apply_label_fixes("\n".join(lines))
    return block


def format_article(fields: dict[str, str], meta: str, content: str) -> str:
    pre = "\n".join(f"{k}: {v}" for k, v in fields.items())
    parts = [ARTICLE_SEP, pre, "---"]
    if meta:
        parts.append(meta)
        parts.append("")
    parts.append(content.strip())
    parts.append("")
    return "\n".join(parts)


def process_pair(jp_path: Path, pt_path: Path) -> dict:
    jp_text = jp_path.read_text(encoding="utf-8")
    pt_text = pt_path.read_text(encoding="utf-8")
    jp_header, jp_blocks = split_file(jp_text)
    _, pt_blocks = split_file(pt_text)
    if len(jp_blocks) != len(pt_blocks):
        return {"file": jp_path.name, "error": "block_count_mismatch", "jp": len(jp_blocks), "pt": len(pt_blocks)}

    out_pt_blocks: list[str] = []
    stats = Counter()
    issues_all: list[dict] = []

    for jp_block, pt_block in zip(jp_blocks, pt_blocks):
        jp_art = parse_article(jp_block)
        pt_art = parse_article(pt_block)
        new_content, issues = rebuild_pt_content(pt_art, jp_art, source_filename=jp_path.name)
        if not new_content and not pt_art.content.strip():
            stats["empty_kept"] += 1
            out_pt_blocks.append(pt_block)
            continue
        if issues:
            stats["issues"] += 1
            issues_all.append({"entry_id": pt_art.fields.get("entry_id"), "issues": issues})
        else:
            stats["ok"] += 1
        new_meta = build_pt_meta(pt_art, new_content, jp_art)
        title_pt = pick_pt_title(
            parse_jp_source_metadata(jp_art.meta + "\n\n" + jp_art.content),
            new_content,
            pt_art.fields,
        )
        fields = dict(pt_art.fields)
        fields["title_pt"] = title_pt or fields.get("title_pt", "")
        out_pt_blocks.append(format_article(fields, new_meta, new_content))

    pt_path.write_text(jp_header.replace("/jp/", "/pt/") + "".join(out_pt_blocks), encoding="utf-8")
    return {"file": jp_path.name, "stats": dict(stats), "issues_sample": issues_all[:5], "issues_count": len(issues_all)}


def main() -> int:
    jp_dir = WORK_ROOT / "jp"
    pt_dir = WORK_ROOT / "pt"
    report: list[dict] = []
    totals = Counter()

    for jp_file in sorted(jp_dir.glob("*.txt")):
        pt_file = pt_dir / jp_file.name
        if not pt_file.exists():
            continue
        result = process_pair(jp_file, pt_file)
        report.append(result)
        if "stats" in result:
            totals["ok"] += result["stats"].get("ok", 0)
            totals["issues"] += result["stats"].get("issues", 0)
            totals["empty"] += result["stats"].get("empty_kept", 0)

    out = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "totals": dict(totals),
        "files": report,
    }
    report_path = WORK_ROOT / "HEADER_FIX_REPORT.json"
    report_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # quick audit
    audit = Counter()
    for pt_file in pt_dir.glob("*.txt"):
        text = pt_file.read_text(encoding="utf-8")
        for block in text.split(ARTICLE_SEP)[1:]:
            if "Publication source: Glória" in block or 'reference: ("Glória' in block:
                audit["gloria_in_meta"] += 1
            if re.search(r"^Glória n", block, re.M):
                audit["gloria_in_ficha"] += 1
            if "Publication source: Eiko\n" in block:
                audit["eiko_unaccented"] += 1
    out["post_audit"] = dict(audit)
    report_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({"totals": dict(totals), "post_audit": dict(audit), "report": str(report_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
