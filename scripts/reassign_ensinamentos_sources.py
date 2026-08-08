#!/usr/bin/env python3
"""Reassign Ensinamentos diversos articles to their identified source files."""

from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORK = Path("/var/www/goshinsho/reports/periodicos_trabalho")
ARTICLE_SEP = "=== ARTIGO ==="

PT_FICHA = {
    "Medicina do Amanhã": "Medicina do Amanhã",
    "Tijotengoku": "Paraíso na Terra",
    "Kyusei": "Kyusei",
    "Movimento Kannon": "Movimento Kannon",
    "Fenômenos da Transição Noite-Dia": "Fenômenos da Transição Noite-Dia",
    "Ensinamentos diversos": "Ensinamentos diversos",
}

PT_MONTHS = {
    "janeiro": 1, "fevereiro": 2, "março": 3, "marco": 3, "abril": 4,
    "maio": 5, "junho": 6, "julho": 7, "agosto": 8, "setembro": 9,
    "outubro": 10, "novembro": 11, "dezembro": 12,
}

# target file stem -> (source_file label for ficha, jp Publication source)
FILE_META = {
    "Medicina_do_Amanha": ("Medicina do Amanhã", "Medicina do Amanhã"),
    "Tijotengoku": ("Tijotengoku", "Tijotengoku"),
    "Kyusei": ("Kyusei", "Kyusei"),
    "Ensinamentos_diversos": ("Ensinamentos diversos", None),  # varies per article
}

MOVES = {
    "publication-jp-1445": {
        "target": "Medicina_do_Amanha",
        "source_file": "Medicina do Amanhã",
        "pub_source_jp": "Medicina do Amanhã",
        "ref": "（「明日の医術」#昭和十一年六月十九日）",
        "sort_date": "19 de junho de 1936",
        "date": "19 de junho de 1936",
        "title_pt": "A Criação do Ser Humano",
    },
    "publication-jp-1383": {
        "target": "Medicina_do_Amanha",
        "source_file": "Medicina do Amanhã",
        "pub_source_jp": "Medicina do Amanhã",
        "ref": "（「日本医術講義録」#昭和十年）",
        "sort_date": "",
        "date": "",
        "title_pt": "A Causa das Doenças e a Impureza do Pecado",
    },
    "publication-jp-1472": {
        "target": "Medicina_do_Amanha",
        "source_file": "Medicina do Amanhã",
        "pub_source_jp": "Medicina do Amanhã",
        "ref": "（「明日の医術」#昭和十四年二月二十四日）",
        "sort_date": "24 de fevereiro de 1953",
        "date": "24 de fevereiro de 1953",
        "title_pt": "O que é a Morte?",
    },
    "publication-jp-1433": {
        "target": "Medicina_do_Amanha",
        "source_file": "Medicina do Amanhã",
        "pub_source_jp": "Medicina do Amanhã",
        "ref": "（「明日の医術」#昭和二十三年十月二十日）",
        "sort_date": "20 de outubro de 1948",
        "date": "20 de outubro de 1948",
        "title_pt": "Quem é o Messias?",
    },
    "publication-jp-1471": {
        "target": "Medicina_do_Amanha",
        "source_file": "Medicina do Amanhã",
        "pub_source_jp": "Medicina do Amanhã",
        "ref": "（「明日の医術」#昭和十一年六月十九日）",
        "sort_date": "19 de junho de 1936",
        "date": "19 de junho de 1936",
        "title_pt": "Morte Natural e Morte Não Natural",
    },
    "publication-jp-1467": {
        "target": "Medicina_do_Amanha",
        "source_file": "Medicina do Amanhã",
        "pub_source_jp": "Medicina do Amanhã",
        "ref": "（「明日の医術」#昭和十一年四月十三日）",
        "sort_date": "13 de abril de 1936",
        "date": "13 de abril de 1936",
        "title_pt": "Doença e a Natureza Humana",
    },
    "publication-jp-1316": {
        "target": "Medicina_do_Amanha",
        "source_file": "Medicina do Amanhã",
        "pub_source_jp": "Medicina do Amanhã",
        "ref": "（「明日の医術」#昭和十年）",
        "sort_date": "",
        "date": "",
        "title_pt": "A Verdadeira Natureza da Doença é a Alma",
    },
    "publication-jp-1324": {
        "target": "Medicina_do_Amanha",
        "source_file": "Medicina do Amanhã",
        "pub_source_jp": "Medicina do Amanhã",
        "ref": "（「明日の医術」#昭和十年）",
        "sort_date": "",
        "date": "",
        "title_pt": "Terapia Natural",
    },
    "publication-jp-1531": {
        "target": "Medicina_do_Amanha",
        "source_file": "Medicina do Amanhã",
        "pub_source_jp": "Medicina do Amanhã",
        "ref": "（「明日の医術」#昭和十年）",
        "sort_date": "",
        "date": "",
        "title_pt": "Alimentação e Nutrição",
    },
    "publication-jp-0953": {
        "target": "Tijotengoku",
        "source_file": "Tijotengoku",
        "pub_source_jp": "Tijotengoku",
        "ref": "（「地上天国」#昭和二十六年九月二十三日）",
        "sort_date": "23 de setembro de 1951",
        "date": "23 de setembro de 1951",
        "title_pt": "Bodhisattva Kannon",
    },
    "publication-jp-0954": {
        "target": "Tijotengoku",
        "source_file": "Tijotengoku",
        "pub_source_jp": "Tijotengoku",
        "ref": "（「地上天国」#昭和二十六年十月一日）",
        "sort_date": "1 de outubro de 1951",
        "date": "1 de outubro de 1951",
        "title_pt": "Miroku San-e",
    },
    "publication-jp-1815": {
        "target": "Kyusei",
        "source_file": "Kyusei",
        "pub_source_jp": "Kyusei",
        "ref": "（「浮世絵の栞」はしがき#昭和二十八年五月）",
        "sort_date": "maio de 1953",
        "date": "maio de 1953",
        "title_pt": "Guia das Gravuras Ukiyo-e — Prefácio",
    },
}

KEEP_UPDATES = {
    "publication-jp-1435": {
        "source_file": "Movimento Kannon",
        "pub_source_jp": "Movimento Kannon",
        "ref": "(「病貧争絶無の世界を作る観音運動とは何？」#昭和十年九月十亓日)",
    },
    "publication-jp-0948": {
        "source_file": "Fenômenos da Transição Noite-Dia",
        "pub_source_jp": "Fenômenos da Transição Noite-Dia",
        "ref": "（「夜昼転換の事象」#昭和三十八年六月十亓日）",
    },
    "publication-jp-1051": {
        "source_file": "Ensinamentos diversos",
        "pub_source_jp": "Ensinamentos diversos",
        "ref": "（NHK放送御対談#昭和二十四年七月十七日）",
    },
    "publication-jp-1057": {
        "source_file": "Ensinamentos diversos",
        "pub_source_jp": "Ensinamentos diversos",
        "ref": "（「実談・虚談」神がかりな話#昭和二十七年十月十五日）",
    },
    "publication-jp-1147": {
        "source_file": "Ensinamentos diversos",
        "pub_source_jp": "Ensinamentos diversos",
        "ref": "（#昭和二十四年）",
    },
    "publication-jp-1366": {
        "source_file": "Ensinamentos diversos",
        "pub_source_jp": "Ensinamentos diversos",
        "ref": "（#昭和二十七年）",
        "title_pt": "Doenças Femininas",
        "sort_date": "",
        "date": "",
    },
}


def parse_sort_key(text: str) -> tuple:
    text = (text or "").strip().lower()
    if not text:
        return (9999, 12, 31)
    m = re.search(
        r"(\d{1,2})\s+de\s+(\w+)\s+(?:de\s+)?(?:do\s+ano\s+\d+\s+da\s+era\s+showa\s+\()?(\d{4})",
        text,
    )
    if m:
        return (int(m.group(3)), PT_MONTHS.get(m.group(2), 99), int(m.group(1)))
    m = re.search(r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})", text)
    if m:
        return (int(m.group(3)), PT_MONTHS.get(m.group(2), 99), int(m.group(1)))
    m = re.search(r"(\w+)\s+de\s+(\d{4})", text)
    if m:
        return (int(m.group(2)), PT_MONTHS.get(m.group(1), 99), 1)
    m = re.search(r"(\d{4})", text)
    if m:
        return (int(m.group(1)), 1, 1)
    return (9999, 12, 31)


def split_file(text: str) -> tuple[str, list[str]]:
    parts = text.split(ARTICLE_SEP)
    header = parts[0]
    blocks = [ARTICLE_SEP + p for p in parts[1:] if p.strip()]
    return header, blocks


def get_field(block: str, name: str) -> str:
    m = re.search(rf"^{re.escape(name)}: (.*)$", block, re.M)
    return m.group(1).strip() if m else ""


def set_field(block: str, name: str, value: str) -> str:
    pat = re.compile(rf"^{re.escape(name)}: .*$", re.M)
    if pat.search(block):
        return pat.sub(f"{name}: {value}", block, count=1)
    pre, post = block.split("---", 1)
    return pre.rstrip() + f"\n{name}: {value}\n---" + post


def set_meta_line(block: str, prefix: str, value: str) -> str:
    pat = re.compile(rf"^{re.escape(prefix)}.*$", re.M)
    if pat.search(block):
        return pat.sub(prefix + value, block, count=1)
    return block


def ficha_date_phrase(sort_date: str, existing_body: str) -> str:
    if sort_date:
        m = re.search(
            r"publicado em (.+?)(?:\n|$)",
            existing_body,
        )
        if m and sort_date in m.group(1):
            return m.group(1).strip()
        # rebuild from sort_date when possible
        sm = re.search(
            r"(\d{1,2})\s+de\s+(\w+)\s+de\s+(\d{4})",
            sort_date,
            re.I,
        )
        if sm:
            day, month, year = int(sm.group(1)), sm.group(2), int(sm.group(3))
            showa = year - 1925
            return f"{day} de {month} do ano {showa} da Era Showa ({year})"
        sm = re.search(r"(\w+)\s+de\s+(\d{4})", sort_date, re.I)
        if sm:
            month, year = sm.group(1), int(sm.group(2))
            showa = year - 1925
            return f"{month} do ano {showa} da Era Showa ({year})"
    m = re.search(r"publicado em (.+?)(?:\n|$)", existing_body)
    if m:
        return m.group(1).strip()
    return "data desconhecida"


def update_jp_block(block: str, cfg: dict) -> str:
    block = set_field(block, "source_file", cfg["source_file"])
    if cfg.get("sort_date") is not None:
        block = set_field(block, "sort_date", cfg.get("sort_date", ""))
    if cfg.get("title_pt"):
        block = set_field(block, "title_pt", cfg["title_pt"])
        block = set_meta_line(block, "Paired Portuguese title: ", cfg["title_pt"])
    block = set_meta_line(block, "Publication source: ", cfg["pub_source_jp"])
    if cfg.get("ref"):
        block = set_meta_line(block, "Original publication reference: ", cfg["ref"])
    if cfg.get("date") is not None:
        block = set_meta_line(block, "Date: ", cfg["date"])
    return block


def update_pt_block(block: str, cfg: dict) -> str:
    source_file = cfg["source_file"]
    pub_pt = PT_FICHA.get(source_file, source_file)
    title_pt = cfg.get("title_pt") or get_field(block, "title_pt")
    sort_date = cfg.get("sort_date") if cfg.get("sort_date") is not None else get_field(block, "sort_date")
    date = cfg.get("date") if cfg.get("date") is not None else get_field(block, "Date")

    block = set_field(block, "source_file", source_file)
    block = set_field(block, "title_pt", title_pt)
    if sort_date is not None:
        block = set_field(block, "sort_date", sort_date)
    block = set_meta_line(block, "Title: ", title_pt)
    block = set_meta_line(block, "Publication source: ", pub_pt)
    if cfg.get("ref"):
        block = set_meta_line(block, "Original publication reference: ", cfg["ref"])
    if date is not None:
        block = set_meta_line(block, "Date: ", date)

    if "---" not in block:
        return block
    pre, post = block.split("---", 1)
    lines = post.splitlines()
    meta_end = 0
    for i, line in enumerate(lines):
        if line.strip().startswith(("Title:", "Publication source:", "Original publication", "Date:", "Language:", "Collection ID:", "Paired ")):
            meta_end = i + 1
            continue
        if meta_end and not line.strip():
            meta_end = i + 1
            continue
        if meta_end:
            break
    body_lines = lines[meta_end:]
    body = "\n".join(body_lines)
    phrase = ficha_date_phrase(sort_date or "", body)
    ficha_prefix = pub_pt + ", publicado em "
    out_body: list[str] = []
    title_done = ficha_done = False
    for line in body_lines:
        s = line.strip()
        if not title_done and s and not s.startswith(pub_pt):
            out_body.append(title_pt)
            title_done = True
            if s == title_pt:
                continue
        if s.startswith(ficha_prefix) or (not ficha_done and "publicado em" in s and title_done):
            out_body.append(f"{pub_pt}, publicado em {phrase}")
            ficha_done = True
            continue
        if not title_done and not s:
            out_body.append(line)
            continue
        out_body.append(line)
    if not title_done:
        out_body.insert(0, title_pt)
        out_body.insert(1, "")
    if not ficha_done:
        idx = 1 if out_body and not out_body[0].strip() else 0
        out_body.insert(idx + 1, f"{pub_pt}, publicado em {phrase}")
        out_body.insert(idx + 1, "")
    return pre + "---\n" + "\n".join(lines[:meta_end]).strip() + "\n\n" + "\n".join(out_body).strip() + "\n"


def update_header_count(header: str, count: int, stem: str) -> str:
    header = re.sub(r"^# Artigos: \d+", f"# Artigos: {count}", header, flags=re.M)
    header = re.sub(r"^# Ficheiro de trabalho: \S+", f"# Ficheiro de trabalho: {stem}", header, flags=re.M)
    return header


def write_file(stem: str, blocks: list[str]) -> None:
    for side in ("jp", "pt"):
        path = WORK / side / f"{stem}.txt"
        header, _ = split_file(path.read_text(encoding="utf-8"))
        header = update_header_count(header, len(blocks), stem)
        path.write_text(header + "".join(blocks), encoding="utf-8")


def insert_sorted(blocks: list[str], new_jp: str, new_pt: str) -> list[tuple[str, str]]:
    pairs = []
    for jb, pb in zip(blocks, blocks):  # placeholder
        pass
    return []


def load_pairs(stem: str) -> list[tuple[str, str]]:
    jp_blocks = split_file((WORK / "jp" / f"{stem}.txt").read_text(encoding="utf-8"))[1]
    pt_blocks = split_file((WORK / "pt" / f"{stem}.txt").read_text(encoding="utf-8"))[1]
    if len(jp_blocks) != len(pt_blocks):
        raise RuntimeError(f"Mismatch {stem}: jp={len(jp_blocks)} pt={len(pt_blocks)}")
    return list(zip(jp_blocks, pt_blocks))


def save_pairs(stem: str, pairs: list[tuple[str, str]]) -> None:
    jp_blocks = [p[0] for p in pairs]
    pt_blocks = [p[1] for p in pairs]
    write_file_blocks(stem, jp_blocks, pt_blocks)


def write_file_blocks(stem: str, jp_blocks: list[str], pt_blocks: list[str]) -> None:
    for side, blocks in (("jp", jp_blocks), ("pt", pt_blocks)):
        path = WORK / side / f"{stem}.txt"
        header, _ = split_file(path.read_text(encoding="utf-8"))
        header = update_header_count(header, len(blocks), stem)
        path.write_text(header + "".join(blocks), encoding="utf-8")


def main() -> None:
    ens_pairs = load_pairs("Ensinamentos_diversos")
    by_id = {get_field(jp, "entry_id"): (jp, pt) for jp, pt in ens_pairs}

    moved: dict[str, list[tuple[str, str]]] = {}
    remaining: list[tuple[str, str]] = []

    for eid, (jp, pt) in by_id.items():
        if eid in MOVES:
            cfg = MOVES[eid]
            nj = update_jp_block(jp, cfg)
            np = update_pt_block(pt, cfg)
            moved.setdefault(cfg["target"], []).append((nj, np))
        else:
            cfg = KEEP_UPDATES.get(eid, {})
            if cfg:
                jp = update_jp_block(jp, cfg)
                pt = update_pt_block(pt, cfg)
            remaining.append((jp, pt))

    for target, new_pairs in moved.items():
        existing = load_pairs(target)
        combined = existing + new_pairs
        combined.sort(key=lambda p: parse_sort_key(get_field(p[0], "sort_date")))
        save_pairs(target, combined)

    save_pairs("Ensinamentos_diversos", remaining)

    counts = {}
    for side in ("jp", "pt"):
        for path in sorted((WORK / side).glob("*.txt")):
            n = len(split_file(path.read_text(encoding="utf-8"))[1])
            counts[path.stem] = n

    manifest_path = WORK / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    key_map = {
        "Medicina_do_Amanha": "Medicina_do_Amanha",
        "Ensinamentos_diversos": "Ensinamentos_diversos",
        "Tijotengoku": "Tijotengoku",
        "Kyusei": "Kyusei",
    }
    for k in manifest["output_files"]:
        if k in counts:
            manifest["output_files"][k] = counts[k]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readme = WORK / "README.txt"
    text = readme.read_text(encoding="utf-8")
    text = re.sub(r"Artigos incluídos: \d+", f"Artigos incluídos: {manifest['kept']}", text)
    note = "- Reclassificação de fontes: 12 artigos saíram de Ensinamentos_diversos (Medicina 9, Tijotengoku 2, Kyusei 1); 6 permanecem em Ensinamentos\n"
    if "Reclassificação de fontes" not in text:
        text = text.replace("- Ensinamentos sem periódico claro:", note + "- Ensinamentos sem periódico claro:")
    readme.write_text(text, encoding="utf-8")

    zip_path = WORK / "periodicos_trabalho.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(WORK.rglob("*")):
            if path.is_file() and path.name != zip_path.name:
                zf.write(path, path.relative_to(WORK).as_posix())

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "moved": {k: [get_field(j, "entry_id") for j, _ in v] for k, v in moved.items()},
        "ensinamentos_remaining": [get_field(j, "entry_id") for j, _ in remaining],
        "output_files": manifest["output_files"],
    }
    (WORK / "REASSIGN_ENSINAMENTOS.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
