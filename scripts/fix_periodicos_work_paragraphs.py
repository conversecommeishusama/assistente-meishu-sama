#!/usr/bin/env python3
"""Alinha parágrafos PT aos blocos do JP (§4.4-F) nos ficheiros periodicos_trabalho."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from html import escape
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
DEPLOY_SCRIPTS = Path("/var/www/goshinsho/scripts")
if DEPLOY_SCRIPTS.is_dir() and str(DEPLOY_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(DEPLOY_SCRIPTS))

from build_periodicos_work_files import TITLE_PT_OVERRIDES  # noqa: E402
from fix_periodicos_work_headers import (  # noqa: E402
    ARTICLE_SEP,
    build_pt_meta,
    extract_clean_pt_body,
    format_article,
    parse_article,
    parse_jp_source_metadata,
    pick_pt_title,
    rebuild_pt_content,
    split_file,
)
from translation_protocol_core import (  # noqa: E402
    JP_SPEAKER_RE,
    normalize_pt_speaker_markers,
    reflow_pt_by_jp_blocks,
    split_collapsed_speaker_paragraph,
    split_jp_prose_paragraphs,
)

from acervo_work_paths import work_root  # noqa: E402

WORK_ROOT = work_root()

# Títulos JP com sufixo たれ (imperativo) → PT moderno
TARE_TITLE_PT: dict[str, str] = {
    "大乗たれ": "Seja Daijo",
    "世界人たれ": "Sejam Cidadãos do Mundo",
    "新人たれ": "Seja uma Pessoa Nova",
    "全部療病者たれ": "Que Todos Sejam Curadores",
    "宗教は世界的たれ": "Que a Religião Seja Mundial",
}

TITLE_ECHO_RE = re.compile(
    r"^(?:"
    r"Sede do Daijo \(Daijō nare\)"
    r"|Sê Daijo \(Daijō nare\)"
    r"|Sede Cidadãos do Mundo \(Sekaijin tare\)"
    r"|Sede do Grande Veículo \(Daijō nare\)"
    r")\s*",
    re.IGNORECASE,
)
BODY_PATCHES: dict[str, callable] = {}


def fix_dialogue_1836(body: str) -> str:
    """Recompõe diálogo Okada/Musei: 12 blocos alinhados ao JP."""
    _ = body  # entrada ignorada — reconstrução completa a partir do JP
    blocks = [
        (
            "Este diálogo entre Meishu-Sama e Tokugawa Musei foi publicado na revista "
            "Shukan Asahi. A parte inicial foi omitida por não ter relação direta com a arte."
        ),
        (
            "Okada: Ao ver pinturas falsificadas, sinto imediatamente um desconforto. "
            "Percebe-se na hora."
        ),
        (
            "Musei: Depende da força de cada pintor, mas nas obras-primas há algo impregnado. "
            "Algo que nos toca profundamente."
        ),
        (
            "Okada: As pinturas chinesas das dinastias Song e Yuan, de novecentos a mil anos "
            "atrás, possuem energia espiritual. Ao observar as obras-primas em nanquim de "
            "Mokkei e de Ryo Kai, somos atraídos de uma forma indescritível. As obras dos "
            "modernos não têm nada disso. Portanto, há uma lógica em se valorizar as obras das "
            "dinastias Song e Yuan. Há dois ou três dias, fui ao museu ver a exposição de "
            "Sotatsu e Korin. Ao contemplá-las, fiquei sem palavras."
        ),
        (
            "Musei: Outro dia, uma pessoa de Kyoto trouxe uma pintura de Sotatsu e me mostrou. "
            "Era um bambu com pardais. Realmente, era maravilhosa."
        ),
        (
            "Okada: Existem muitas falsificações de Sotatsu também, mas eu as identifico "
            "imediatamente pela energia espiritual."
        ),
        (
            "Musei: Sotatsu e Korin são realmente grandiosos. Dizem que, depois de ver uma "
            "exposição de Matisse, não se sente vontade de ver mais nada. Parece que Matisse "
            "aprendeu com eles."
        ),
        (
            "Okada: Matisse, em geral, tirou a sensibilidade de Korin e a técnica de Sharaku. "
            "O que ele fez foi pegar Sharaku e Korin e simplificá-los de forma moderna. Quanto "
            "às pinturas a óleo de Matisse, não as admiro tanto. Na pintura a óleo, mesmo os "
            "pós-impressionistas têm obras superiores. No entanto, seus desenhos são realmente "
            "notáveis."
        ),
        (
            "Musei: Existe aquele retrato da filha de Matisse (da coleção do Museu de Arte de "
            "Ohara). Todos o elogiam, mas eu não o entendo. No entanto, outro dia, fui à casa "
            "do Sr. Nomura Kodo e vi um desenho de Matisse (uma jovem). Esse eu entendi. Era "
            "realmente maravilhoso."
        ),
        (
            "Okada: É porque, com linhas simples, ele expressa muito bem a individualidade."
        ),
        (
            "Musei: Há uma pintura de Mokkei ou Ryo Kai que mostra Hotei observando galos "
            "brigando. Essa cena também aparece em uma pintura de Musashi. No original, há uma "
            "árvore ao fundo, mas na versão de Musashi, a árvore não está presente. A propósito, "
            "falando em pinturas de Musashi, esta também é uma história espiritual. Eu estava "
            "falando muito sobre Miyamoto Musashi em transmissões de rádio e pensava que precisava "
            "ter uma obra dele. Então, um antiquário a trouxe. Era uma pintura de gansos "
            "selvagens, mas eram gansos bastante rechonchudos. Eram gansos estranhamente gordos. "
            "Como era cara, desisti de comprar. Então, dois ou três dias depois, o Sr. Yoshikawa "
            "Eiji veio inesperadamente com sua esposa. Era a primeira vez que vinham à minha casa. "
            'Ele disse: "Bem, hoje vim para lhe dar um presente". E me deu uma pintura de '
            "Musashi. Deve ter havido algo no mundo espiritual que determinou que a pintura de "
            "Musashi viesse para minha casa."
        ),
        (
            "Okada: Ou seja, o mundo espiritual ficou muito feliz por você estar divulgando "
            "Musashi e sentiu que precisava retribuir de alguma forma... (Risos) "
            "*(Enquanto apreciavam um par de rolos de Sotatsu representando \"Dragão\" e "
            "\"Tigre\", de propriedade do Sr. Okada, e um prato quadrado de Kenzan com a pintura "
            "de \"Pinheiro e Cerejeira da Montanha\", a conversa sobre pintura e arte se estendeu "
            "ainda mais. Ou seja, discutiram sobre Picasso, Umehara Ryuzaburo, Yasui Sotaro, "
            "Koide Narashige, Kishida Ryusei, e também sobre Seiho, Taikan, Kokei, entre outros. "
            "Desenvolveu-se, de fato, um grande debate sobre arte, mas, infelizmente, foi omitido.)*"
        ),
    ]
    return "\n\n".join(blocks)


BODY_PATCHES["publication-jp-1836"] = fix_dialogue_1836


TITLE_ECHO_PARA_RE = re.compile(
    r"^(?:"
    r"Sede do Daijo \(Daijō nare\)"
    r"|Sê Daijo \(Daijō nare\)"
    r"|Sede Cidadãos do Mundo \(Sekaijin tare\)"
    r"|Sede do Grande Veículo \(Daijō nare\)"
    r")\s*$",
    re.IGNORECASE,
)


def resolve_pt_title(jp_meta: dict[str, str], pt_body: str, fields: dict[str, str]) -> str:
    entry_id = fields.get("entry_id", "")
    if entry_id in TITLE_PT_OVERRIDES:
        return TITLE_PT_OVERRIDES[entry_id]
    title_jp = clean_title_jp(jp_meta.get("Title", "") or fields.get("title_jp", ""))
    if title_jp in TARE_TITLE_PT:
        return TARE_TITLE_PT[title_jp]
    title = pick_pt_title(jp_meta, pt_body, fields)
    return fix_bad_tare_title(title, title_jp)


def clean_title_jp(title: str) -> str:
    return (title or "").strip()


def fix_bad_tare_title(title_pt: str, title_jp: str) -> str:
    title_pt = (title_pt or "").strip()
    if title_jp in TARE_TITLE_PT:
        return TARE_TITLE_PT[title_jp]
    if re.match(r"^(Sede|Sê)\b", title_pt, re.I):
        if "daijo" in title_pt.lower() or "大乗" in title_jp:
            return "Seja Daijo"
        if "cidad" in title_pt.lower() or "世界人" in title_jp:
            return "Sejam Cidadãos do Mundo"
    if title_pt.rstrip(":").lower() in {"okada", "musei"}:
        return TITLE_PT_OVERRIDES.get(
            "publication-jp-1836", "Diálogo Meishu-Sama e Tokugawa Musei (Arte)"
        )
    return title_pt


def apply_body_lexical_fixes(body: str) -> str:
    body = body.replace("Tokugawa Musume", "Tokugawa Musei")
    body = body.replace("Musume foi publicado", "Musei foi publicado")
    # 教え / 本教: «Doutrina» → «Igreja» quando se refere à organização
    body = re.sub(
        r"\bobstáculo para a Doutrina\b",
        "obstáculo para a nossa Igreja",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"\bpara a Doutrina\b(?!\s+Absoluta)",
        "para a nossa Igreja",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"\bna Doutrina\b(?!\s+Absoluta)",
        "na nossa Igreja",
        body,
        flags=re.IGNORECASE,
    )
    body = re.sub(
        r"\bda Doutrina\b(?!\s+Absoluta)",
        "da nossa Igreja",
        body,
        flags=re.IGNORECASE,
    )
    return body


def split_glued_speaker_paragraphs(body: str) -> str:
    """Separa parágrafos com múltiplos rótulos de falante na mesma linha."""
    paras = [p for p in re.split(r"\n\s*\n", body) if p.strip()]
    out: list[str] = []
    for para in paras:
        markers = len(
            re.findall(
                r"(?:^|\s)(?:Okada|Musei|Meishu-Sama|Interlocutor|Apresentador):",
                para,
                re.I,
            )
        )
        if markers >= 2:
            out.extend(split_collapsed_speaker_paragraph(para))
        else:
            out.append(para.strip())
    return "\n\n".join(out)


def merge_dangling_paragraphs(body: str) -> str:
    """Funde parágrafos partidos no meio de frase (artefacto de reflow por peso)."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    if len(paras) < 2:
        return body
    out: list[str] = []
    buf = ""
    for para in paras:
        if not buf:
            buf = para
            continue
        if not re.search(r'[.!?…»"]\s*$', buf):
            buf = f"{buf} {para}"
        else:
            out.append(buf)
            buf = para
    if buf:
        out.append(buf)
    return "\n\n".join(out)


def strip_orphan_speaker_labels(body: str) -> str:
    """Remove rótulos de falante sem texto (artefacto de staging)."""
    body = re.sub(r"^(?:Okada|Musei|Meishu-Sama|Interlocutor):\s*\n+", "", body, flags=re.I | re.M)
    paras = [p for p in re.split(r"\n\s*\n", body) if p.strip()]
    kept: list[str] = []
    for para in paras:
        stripped = para.strip()
        if re.fullmatch(r"(?:Okada|Musei|Meishu-Sama|Interlocutor):", stripped, re.I):
            continue
        if TITLE_ECHO_PARA_RE.match(stripped):
            continue
        kept.append(stripped)
    return "\n\n".join(kept)


def clean_header_title_echo(header: str, title_pt: str) -> str:
    if not header:
        return header
    paras = [p.strip() for p in re.split(r"\n\s*\n", header) if p.strip()]
    kept = [
        p
        for p in paras
        if not TITLE_ECHO_PARA_RE.match(p)
        and not re.fullmatch(r"(?:Okada|Musei|Meishu-Sama|Interlocutor):", p.strip(), re.I)
    ]
    return "\n\n".join(kept)


STRAY_OLD_TITLE_PT: dict[str, list[str]] = {
    "publication-jp-1431": ["Sobre o Ateísmo"],
    "publication-jp-1236": ["O Princípio da nossa terapia"],
}


def strip_stray_old_titles(body: str, entry_id: str) -> str:
    for old in STRAY_OLD_TITLE_PT.get(entry_id, []):
        if not old:
            continue
        body = re.sub(rf"^{re.escape(old)}\s+", "", body, flags=re.M)
        body = re.sub(rf"\n\n{re.escape(old)}\s*\n\n", "\n\n", body)
        body = re.sub(rf"\n\n{re.escape(old)}\s*\n", "\n\n", body)
    return body.strip()


def strip_body_title_echo(body: str, title_pt: str) -> str:
    body = (body or "").strip()
    if not body:
        return body
    body = TITLE_ECHO_RE.sub("", body)
    paras = [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]
    cleaned: list[str] = []
    for para in paras:
        if TITLE_ECHO_PARA_RE.match(para):
            continue
        if title_pt and para.strip() == title_pt.strip():
            continue
        cleaned.append(para)
    body = "\n\n".join(cleaned)
    for candidate in (title_pt, fix_bad_tare_title(title_pt, "")):
        if candidate and body.startswith(candidate):
            rest = body[len(candidate) :].lstrip(":-— \t")
            if rest:
                body = rest
    glued = re.match(
        rf"^{re.escape(title_pt)}\s+(?=[A-ZÁÉÍÓÚÀÂÊÔÃÕÇ\"])",
        body,
        re.IGNORECASE,
    )
    if glued:
        body = body[glued.end() :].lstrip()
    return body.strip()


def ensure_content_title_line(content: str, title_pt: str) -> str:
    """Garante linha de título A4 no corpo (após meta, antes/depois da ficha)."""
    title_pt = (title_pt or "").strip()
    if not title_pt or title_pt in content:
        return content
    parts = [p for p in re.split(r"\n\s*\n", content) if p.strip()]
    for idx, part in enumerate(parts):
        if "publicado em" in part.lower():
            parts.insert(idx, title_pt)
            return "\n\n".join(parts)
    return f"{title_pt}\n\n{content}"


def split_pt_header_body(normalized: str, title_pt: str, title_jp: str) -> tuple[str, str]:
    body = extract_clean_pt_body(normalized, title_pt, title_jp)
    body = strip_body_title_echo(body, title_pt)
    # Nota editorial (Revista Asahi etc.) não é fala de personagem
    body = re.sub(
        r"^Okada:\s*((?:Este diálogo entre Meishu-Sama).+?arte\.)",
        r"\1",
        body,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if body and body in normalized:
        header = normalized[: normalized.find(body)].strip()
        return header, body.strip()
    parts = [p for p in re.split(r"\n\s*\n", normalized) if p.strip()]
    if len(parts) >= 3:
        header = "\n\n".join(parts[:2]).strip()
        body = "\n\n".join(parts[2:]).strip()
        return header, strip_body_title_echo(body, title_pt)
    if len(parts) == 2:
        return parts[0].strip(), strip_body_title_echo(parts[1].strip(), title_pt)
    return "", strip_body_title_echo(normalized.strip(), title_pt)


def count_body_paragraphs(body: str) -> int:
    return len([p for p in re.split(r"\n\s*\n", body) if p.strip()])


def paragraph_mismatch(jp_body: str, pt_body: str) -> tuple[int, int]:
    jp_n = len(split_jp_prose_paragraphs(jp_body))
    pt_n = count_body_paragraphs(pt_body)
    return jp_n, pt_n


def reflow_pt_article(jp_art, pt_art) -> tuple[str, dict, str]:
    jp_raw = jp_art.meta + "\n\n" + jp_art.content
    jp_meta = parse_jp_source_metadata(jp_raw)
    title_jp = clean_title_jp(jp_meta.get("Title", "") or jp_art.fields.get("title_jp", ""))
    title_pt = resolve_pt_title(jp_meta, pt_art.content, jp_art.fields)

    normalized, issues = rebuild_pt_content(pt_art, jp_art)
    if not normalized.strip():
        return pt_art.content, {"skipped": "empty"}, title_pt

    header, pt_body = split_pt_header_body(normalized, title_pt, title_jp)
    if not pt_body.strip():
        return normalized, {"skipped": "empty_body"}, title_pt

    pt_body = apply_body_lexical_fixes(pt_body)
    entry_id = jp_art.fields.get("entry_id", "")
    patch = BODY_PATCHES.get(entry_id)
    if patch:
        reflowed_body = strip_orphan_speaker_labels(
            strip_stray_old_titles(strip_body_title_echo(patch(pt_body), title_pt), entry_id)
        )
    else:
        pt_body = merge_dangling_paragraphs(pt_body)
        pt_body = normalize_pt_speaker_markers(pt_body)
        reflowed_body = reflow_pt_by_jp_blocks(jp_art.content, pt_body, jp_raw=None).strip()
        reflowed_body = normalize_pt_speaker_markers(reflowed_body)
        reflowed_body = split_glued_speaker_paragraphs(reflowed_body)
        reflowed_body = strip_orphan_speaker_labels(reflowed_body)
        reflowed_body = strip_body_title_echo(reflowed_body, title_pt)
        reflowed_body = strip_stray_old_titles(reflowed_body, entry_id)

    header = clean_header_title_echo(header, title_pt)
    content = f"{header}\n\n{reflowed_body}" if header else reflowed_body
    content = ensure_content_title_line(content, title_pt)
    jp_n, pt_n = paragraph_mismatch(jp_art.content, reflowed_body)
    return content, {"jp_paras": jp_n, "pt_paras": pt_n, "issues": issues}, title_pt


def process_pair(jp_path: Path, pt_path: Path) -> dict:
    jp_text = jp_path.read_text(encoding="utf-8")
    pt_text = pt_path.read_text(encoding="utf-8")
    jp_header, jp_blocks = split_file(jp_text)
    _, pt_blocks = split_file(pt_text)
    if len(jp_blocks) != len(pt_blocks):
        return {"file": jp_path.name, "error": "block_count_mismatch"}

    out_blocks: list[str] = []
    stats = Counter()
    for jp_block, pt_block in zip(jp_blocks, pt_blocks):
        jp_art = parse_article(jp_block)
        pt_art = parse_article(pt_block)
        new_content, info, title_pt = reflow_pt_article(jp_art, pt_art)
        if info.get("skipped"):
            stats[info["skipped"]] += 1
            out_blocks.append(pt_block)
            continue

        jp_n = info.get("jp_paras", 0)
        pt_n = info.get("pt_paras", 0)
        if jp_n >= 3 and pt_n <= 1:
            stats["still_collapsed"] += 1
        elif jp_n > 0 and pt_n == jp_n:
            stats["aligned"] += 1
        elif abs(jp_n - pt_n) <= max(1, round(0.1 * jp_n)):
            stats["near_aligned"] += 1
        else:
            stats["misaligned"] += 1

        fields = dict(pt_art.fields)
        fields["title_pt"] = title_pt
        new_meta = build_pt_meta(pt_art, new_content, jp_art)
        out_blocks.append(format_article(fields, new_meta, new_content))

    pt_path.write_text(jp_header.replace("/jp/", "/pt/") + "".join(out_blocks), encoding="utf-8")
    return {"file": jp_path.name, "stats": dict(stats)}


def audit_corpus() -> dict:
    total = aligned = near = collapsed = misaligned = 0
    for jp_path in sorted((WORK_ROOT / "jp").glob("*.txt")):
        pt_path = WORK_ROOT / "pt" / jp_path.name
        for jb, pb in zip(
            split_file(jp_path.read_text(encoding="utf-8"))[1],
            split_file(pt_path.read_text(encoding="utf-8"))[1],
        ):
            total += 1
            jp_art = parse_article(jb)
            pt_art = parse_article(pb)
            jp_meta = parse_jp_source_metadata(jp_art.meta + "\n\n" + jp_art.content)
            title_pt = resolve_pt_title(jp_meta, pt_art.content, pt_art.fields)
            body = extract_clean_pt_body(
                pt_art.content, title_pt, jp_meta.get("Title", "")
            )
            jp_n, pt_n = paragraph_mismatch(jp_art.content, body)
            if jp_n >= 3 and pt_n <= 1:
                collapsed += 1
            elif jp_n > 0 and jp_n == pt_n:
                aligned += 1
            elif abs(jp_n - pt_n) <= max(1, round(0.1 * jp_n)):
                near += 1
            else:
                misaligned += 1
    return {
        "total": total,
        "exact_aligned": aligned,
        "near_aligned": near,
        "collapsed_body": collapsed,
        "misaligned": misaligned,
    }


def regenerate_amostra_html() -> None:
    sample_path = WORK_ROOT / "AMOSTRA_CONFERENCIA_JP_PT.json"
    if not sample_path.is_file():
        return
    data = json.loads(sample_path.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    toc_items: list[str] = []
    sections: list[str] = []

    for item in data["sample"]:
        entry_id = item["entry_id"]
        fname = item["file"]
        jp_file = WORK_ROOT / "jp" / f"{fname}.txt"
        pt_file = WORK_ROOT / "pt" / jp_file.name

        jp_block = pt_block = ""
        for jb in split_file(jp_file.read_text(encoding="utf-8"))[1]:
            if entry_id in jb:
                jp_block = jb
                break
        for pb in split_file(pt_file.read_text(encoding="utf-8"))[1]:
            if entry_id in pb:
                pt_block = pb
                break

        jp_art = parse_article(jp_block) if jp_block else None
        pt_art = parse_article(pt_block) if pt_block else None
        jp_body = jp_art.content if jp_art else ""
        pt_body = pt_art.content if pt_art else ""
        title_pt = (
            resolve_pt_title(
                parse_jp_source_metadata(jp_art.meta + "\n\n" + jp_art.content),
                pt_body,
                jp_art.fields,
            )
            if jp_art
            else item.get("title_pt", "")
        )
        jp_n, pt_n = paragraph_mismatch(jp_body, extract_clean_pt_body(pt_body, title_pt, item.get("title_jp", "")))

        n = item["n"]
        anchor = f"art-{n}"
        toc_items.append(
            f'<li><a href="#{anchor}">{escape(entry_id)}</a> '
            f'<span class="muted">({escape(fname)})</span></li>'
        )
        sort_date = (jp_art.fields.get("sort_date") if jp_art else "") or ""
        paired = (jp_art.fields.get("paired_id") if jp_art else "") or ""
        ref = ""
        if jp_art and jp_art.meta:
            m = re.search(r"Original publication reference: (.+)", jp_art.meta)
            ref = m.group(1).strip() if m else ""

        sections.append(
            f"""
<section class="article" id="{anchor}">
  <header class="article-head">
    <h2><a href="#{anchor}">#{n}</a> {escape(entry_id)}</h2>
    <dl class="meta-grid">
      <div><dt>Ficheiro</dt><dd>{escape(fname)}</dd></div>
      <div><dt>Fonte</dt><dd>{escape(item.get('source_file', fname))}</dd></div>
      <div><dt>Data</dt><dd>{escape(sort_date)}</dd></div>
      <div><dt>Par PT</dt><dd>{escape(paired)}</dd></div>
      <div><dt>Título JP</dt><dd lang="ja">{escape(item.get('title_jp', ''))}</dd></div>
      <div><dt>Título PT</dt><dd>{escape(title_pt)}</dd></div>
      <div class="wide"><dt>Referência</dt><dd>{escape(ref)}</dd></div>
      <div><dt>Chars JP</dt><dd>{len(jp_body):,}</dd></div>
      <div><dt>Chars PT</dt><dd>{len(pt_body):,}</dd></div>
      <div><dt>Parágrafos JP</dt><dd>{jp_n}</dd></div>
      <div><dt>Parágrafos PT (corpo)</dt><dd>{pt_n}</dd></div>
      <div><dt>Δ parágrafos</dt><dd>{pt_n - jp_n:+d}</dd></div>
    </dl>
  </header>
  <div class="columns">
    <div class="col jp"><h3>Japonês</h3><pre class="body">{escape(jp_body)}</pre></div>
    <div class="col pt"><h3>Português</h3><pre class="body">{escape(pt_body)}</pre></div>
  </div>
</section>"""
        )

    html = f"""<!DOCTYPE html>
<html lang="pt">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Conferência JP/PT — amostra 10 artigos</title>
  <style>
    :root {{
      --bg: #fafafa; --card: #fff; --border: #d8d8d8; --text: #1a1a1a;
      --muted: #666; --jp: #1e3a5f; --pt: #2d5016; --accent: #2563eb;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      font-family: "Segoe UI", system-ui, -apple-system, sans-serif;
      margin: 0; background: var(--bg); color: var(--text); line-height: 1.55;
    }}
    .page {{ max-width: 1600px; margin: 0 auto; padding: 1.5rem 1.25rem 3rem; }}
    h1 {{ font-size: 1.5rem; margin: 0 0 .25rem; }}
    .subtitle {{ color: var(--muted); margin: 0 0 1.25rem; font-size: .95rem; }}
    .toc {{
      background: var(--card); border: 1px solid var(--border); border-radius: 8px;
      padding: 1rem 1.25rem; margin-bottom: 2rem;
    }}
    .toc h2 {{ font-size: 1rem; margin: 0 0 .75rem; }}
    .toc ol {{ margin: 0; padding-left: 1.25rem; }}
    .toc li {{ margin: .35rem 0; }}
    .toc a {{ color: var(--accent); text-decoration: none; }}
    .toc a:hover {{ text-decoration: underline; }}
    .muted {{ color: var(--muted); font-size: .85em; }}
    .article {{
      background: var(--card); border: 1px solid var(--border); border-radius: 8px;
      margin-bottom: 2rem; overflow: hidden;
    }}
    .article-head {{
      padding: 1rem 1.25rem; border-bottom: 1px solid var(--border); background: #f3f4f6;
    }}
    .article-head h2 {{ margin: 0 0 .75rem; font-size: 1.1rem; }}
    .article-head h2 a {{ color: inherit; text-decoration: none; }}
    .meta-grid {{
      display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
      gap: .35rem .75rem; margin: 0; font-size: .82rem;
    }}
    .meta-grid div {{ display: contents; }}
    .meta-grid dt {{ font-weight: 600; color: var(--muted); }}
    .meta-grid dd {{ margin: 0; }}
    .meta-grid .wide {{ grid-column: 1 / -1; }}
    .columns {{ display: grid; grid-template-columns: 1fr 1fr; min-height: 200px; }}
    @media (max-width: 900px) {{ .columns {{ grid-template-columns: 1fr; }} }}
    .col {{ padding: 0; border-right: 1px solid var(--border); }}
    .col:last-child {{ border-right: none; }}
    .col h3 {{
      margin: 0; padding: .6rem 1rem; font-size: .85rem; text-transform: uppercase;
      letter-spacing: .04em; border-bottom: 1px solid var(--border); background: #f9fafb;
    }}
    .col.jp h3 {{ color: var(--jp); }}
    .col.pt h3 {{ color: var(--pt); }}
    pre.body {{
      margin: 0; padding: 1rem 1.1rem; white-space: pre-wrap; word-wrap: break-word;
      font-family: "Noto Sans JP", "Hiragino Sans", "Segoe UI", sans-serif;
      font-size: .88rem; line-height: 1.65; background: #fff; max-height: 70vh; overflow-y: auto;
    }}
    .col.jp pre.body {{ font-family: "Noto Sans JP", "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif; }}
  </style>
</head>
<body>
  <div class="page">
    <h1>Conferência final — comparativo JP / PT</h1>
    <p class="subtitle">Amostra aleatória de 10 artigos · seed {data.get('seed', '')} · {data.get('total_articles', 678)} artigos · gerado {now} · §4.4-F alinhado</p>
    <nav class="toc"><h2>Índice da amostra</h2><ol>{''.join(toc_items)}</ol></nav>
    {''.join(sections)}
  </div>
</body>
</html>"""
    (WORK_ROOT / "AMOSTRA_CONFERENCIA_JP_PT.html").write_text(html, encoding="utf-8")


def main() -> None:
    before = audit_corpus()
    print("Antes:", before)
    results = []
    for jp_path in sorted((WORK_ROOT / "jp").glob("*.txt")):
        pt_path = WORK_ROOT / "pt" / jp_path.name
        results.append(process_pair(jp_path, pt_path))
    after = audit_corpus()
    print("Depois:", after)
    report = {
        "generated": datetime.now(timezone.utc).isoformat(),
        "before": before,
        "after": after,
        "files": results,
    }
    out = WORK_ROOT / "REFLOW_PARAGRAFOS.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Relatório:", out)
    regenerate_amostra_html()
    print("Amostra HTML regenerada.")


if __name__ == "__main__":
    main()
