"""Parseia o Rokkan (天国の礎, 六巻) em entradas estruturadas: categoria,
titulo, posicao, corpo (JP) e citacao da fonte original (periodico/livro +
edicao + data). Fonte: arquivo de referencia protegido por direitos
autorais, usado so para extrair a atribuicao -- nunca redistribuido.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import docx

SRC = Path("/var/www/goshinsho/referencia_zenshu_rokkan_DIREITOS_AUTORAIS_APAGAR_DEPOIS/0_rokkan-1-6-jap (1).docx")
OUT = Path("/var/www/goshinsho/reports/periodicos_trabalho/ROKKAN_PARSED.json")

TITLE_RE = re.compile(r"^(?P<title>.+?)\s*（(?P<categoria>[^\d　]+)\s*タイトル\s*(?P<pos>[0-9０-９]+)）$")
CIT_RE = re.compile(
    r"^（「?(?P<fonte>[^」』\d#]+)」?『?\s*(?P<edicao>[0-9０-９〇一二三四五六七八九十百千亓]*号?)\s*#?"
    r"昭和(?P<ano>[0-9０-９〇一二三四五六七八九十百千亓]+)年(?P<mes>[0-9０-９〇一二三四五六七八九十百千亓]+)月(?P<dia>[0-9０-９〇一二三四五六七八九十百千亓]+)日）$"
)

KANJI_NUM = {"〇": 0, "一": 1, "二": 2, "三": 3, "四": 4, "亓": 5, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def kanji_to_int(s: str) -> int | None:
    s = s.strip().rstrip("号")
    if not s:
        return None
    if s.isdigit():
        return int(s)
    if all(c in "0123456789０１２３４５６７８９" for c in s):
        return int(s.translate(str.maketrans("０１２３４５６７８９", "0123456789")))
    # kanji numeral (up to thousands), traditional style e.g. 百八十二
    total = 0
    section = 0
    num = 0
    for ch in s:
        if ch in KANJI_NUM:
            num = KANJI_NUM[ch]
        elif ch == "十":
            section += (num or 1) * 10
            num = 0
        elif ch == "百":
            section += (num or 1) * 100
            num = 0
        elif ch == "千":
            section += (num or 1) * 1000
            num = 0
        else:
            continue
    total = section + num
    return total if total else None


def showa_to_iso(ano_k: str, mes_k: str, dia_k: str) -> str | None:
    ano = kanji_to_int(ano_k)
    mes = kanji_to_int(mes_k)
    dia = kanji_to_int(dia_k)
    if ano is None or mes is None or dia is None:
        return None
    year = 1925 + ano
    try:
        return f"{year:04d}-{mes:02d}-{dia:02d}"
    except Exception:
        return None


def main() -> None:
    d = docx.Document(str(SRC))
    texts = [p.text.strip() for p in d.paragraphs]

    entries = []
    current = None
    body_lines: list[str] = []

    for t in texts:
        if not t:
            continue
        m_title = TITLE_RE.match(t)
        m_cit = CIT_RE.match(t)
        if m_title:
            if current is not None:
                current["body_jp"] = "\n".join(body_lines).strip()
                entries.append(current)
            current = {
                "title_jp": m_title.group("title").strip(),
                "categoria": m_title.group("categoria").strip(),
                "posicao": m_title.group("pos"),
                "fonte": None,
                "edicao": None,
                "data_iso": None,
                "data_kanji": None,
                "body_jp": "",
            }
            body_lines = []
        elif m_cit and current is not None:
            current["fonte"] = m_cit.group("fonte").strip()
            current["edicao"] = kanji_to_int(m_cit.group("edicao"))
            current["data_iso"] = showa_to_iso(m_cit.group("ano"), m_cit.group("mes"), m_cit.group("dia"))
            current["data_kanji"] = f"昭和{m_cit.group('ano')}年{m_cit.group('mes')}月{m_cit.group('dia')}日"
        elif current is not None:
            body_lines.append(t)

    if current is not None:
        current["body_jp"] = "\n".join(body_lines).strip()
        entries.append(current)

    OUT.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Total entradas: {len(entries)}")
    sem_citacao = sum(1 for e in entries if not e["fonte"])
    print(f"Sem citacao reconhecida: {sem_citacao}")
    from collections import Counter
    fontes = Counter(e["fonte"] for e in entries if e["fonte"])
    for fonte, n in fontes.most_common(30):
        print(f"  {n:4d}  {fonte}")
    print(f"\nSalvo em: {OUT}")


if __name__ == "__main__":
    main()
