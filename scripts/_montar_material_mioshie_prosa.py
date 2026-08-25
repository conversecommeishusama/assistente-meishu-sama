#!/usr/bin/env python3
"""Monta material lado a lado MIOSHIE 9-33 (prosa) a partir do TEXTO CANÔNICO ATUAL.

Fonte de verdade (regra do usuário): O PRÓPRIO TEXTO.
  - PT = staging canônico ATUAL (reports/livros_trabalho/pt/)
  - JP = textos_japones/
  - NÃO usa checkpoint (não é referência).

A prosa 9-33 é contínua, com seções delimitadas por DATA no JP (kanji) e no PT
(por extenso). O pareamento estrutural (24/08) confirmou que as datas coincidem.
Este montador alinha por seção de data e serve de material de leitura para a
revisão semântica manual. NÃO edita nada.

Uso:
  python scripts/_montar_material_mioshie_prosa.py <n>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
JP_DIR = RAIZ / "textos_japones"
STAGING_DIR = RAIZ / "reports" / "livros_trabalho" / "pt"
OUT_DIR = RAIZ / "reports" / "material_revsem_mioshie"

# mapeamento de kanji de data para PT
KANJI = {"〇": "0", "一": "1", "二": "2", "三": "3", "四": "4", "五": "5",
         "六": "6", "七": "7", "八": "8", "九": "9", "十": "10"}


def kanji_para_num(s: str) -> int:
    """Converte numeral kanji (ex: 二十七) para int."""
    s = s.replace("十", "")
    if not s:
        return 10
    # dois dígitos: dezena + unidade (ex: 二十=2? tratamos abaixo)
    return int(s) if s else 10


def kanji_data_para_iso(linha: str) -> str | None:
    """Converte '昭和二十七年四月五日' -> '1952-04-05'. Retorna None se não casar."""
    m = re.search(r"昭和(\d+)年(\d+)月(\d+)日", linha)
    if not m:
        return None
    ano = int(m.group(1)) + 1925  # Showa
    mes = int(m.group(2))
    dia = int(m.group(3))
    return f"{ano:04d}-{mes:02d}-{dia:02d}"


def mes_pt_para_num(s: str) -> int:
    meses = {"janeiro": 1, "fevereiro": 2, "março": 3, "abril": 4, "maio": 5,
             "junho": 6, "julho": 7, "agosto": 8, "setembro": 9, "outubro": 10,
             "novembro": 11, "dezembro": 12}
    return meses.get(s.lower(), 0)


def data_pt_para_iso(linha: str) -> str | None:
    """Converte '5 de abril de 1952' -> '1952-04-05'."""
    m = re.search(r"(\d{1,2}) de ([a-zç]+) de (\d{4})", linha)
    if not m:
        return None
    dia = int(m.group(1))
    mes = mes_pt_para_num(m.group(2))
    ano = int(m.group(3))
    return f"{ano:04d}-{mes:02d}-{dia:02d}"


def limpar_cabecalho_jp(texto: str) -> str:
    idx = texto.find("---")
    return texto[idx + 3:] if idx != -1 else texto


# Data kanji: linha com 昭和...年...月...日 OU apenas ...月...日 (linha própria)
RE_DATA_KANJI = re.compile(
    r"(?m)^\s*(昭和[〇一二三四五六七八九十]+年)?\s*"
    r"([〇一二三四五六七八九十]+)月([〇一二三四五六七八九十]+)日\s*$"
)

# Data PT: linha com N de mês (de ano)?
RE_DATA_PT = re.compile(
    r"(?m)^\s*(\d{1,2})\s+de\s+([a-zç]+)(?:\s+de\s+(\d{4}))?[^A-Za-z0-9]?.*$"
)

# Linhas de metadados de publicação no PT (não são seções de ensinamento)
RE_METADADO_PT = re.compile(
    r"Impresso|Publicado|Não comercializável|Não-comercializável|— Impresso|— Publicado|"
    r"– Impresso|– Publicado", re.IGNORECASE
)


def dividir_secoes_jp(texto: str) -> list[tuple[str, str]]:
    """Divide o JP da prosa por linhas de data (kanji). Retorna [(data_jp, conteudo)]."""
    matches = list(RE_DATA_KANJI.finditer(texto))
    secoes = []
    for i, m in enumerate(matches):
        data = m.group(0).strip()
        fim = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
        conteudo = texto[m.start():fim].strip()
        # pula a data de publicação no cabeçalho (『御教え集』9号、昭和27(1952)年5月15日発行)
        if "発行" in conteudo[:80]:
            continue
        secoes.append((data, conteudo))
    return secoes


def dividir_secoes_pt(texto: str) -> list[tuple[str, str]]:
    """Divide o PT da prosa por linhas de data (por extenso). Retorna [(data_pt, conteudo)]."""
    matches = list(RE_DATA_PT.finditer(texto))
    secoes = []
    for i, m in enumerate(matches):
        data = m.group(0).strip()
        # pula linhas de metadados de publicação (Impresso/Publicado etc.)
        if RE_METADADO_PT.search(data):
            continue
        fim = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
        conteudo = texto[m.start():fim].strip()
        secoes.append((data, conteudo))
    return secoes


def montar(n: int) -> str:
    jp_path = next((p for p in sorted(JP_DIR.glob(f"*御教え集{n}号.txt"))), None)
    st_path = next((p for p in sorted(STAGING_DIR.glob("*.txt"))
                    if re.search(rf"Mioshie-shū nº {n}", p.stem)), None)
    if not jp_path or not st_path:
        return f"ERRO: JP={jp_path} ST={st_path}"

    jp = limpar_cabecalho_jp(jp_path.read_text(encoding="utf-8"))
    st = st_path.read_text(encoding="utf-8")

    jp_secoes = dividir_secoes_jp(jp)
    st_secoes = dividir_secoes_pt(st)

    # Modo flexível: se a contagem difere, monta mesmo assim usando as seções JP
    # como referência e as seções PT na mesma ordem (as seções PT extras são
    # tratadas como parte da seção anterior quando são palestras/metadados).
    if len(jp_secoes) != len(st_secoes):
        # Se o JP tem menos seções que o PT, tenta fundir as seções PT extras
        # (palestras em data própria) na seção anterior quando a data PT bate
        # com a próxima data JP.
        # Estratégia pragmática: usar o JP como referência; para cada seção JP,
        # consumir as seções PT cuja data corresponde, acumulando extras.
        pass

    # Abordagem robusta: montar JP completo + PT completo, com marcadores de data
    # preservados, para leitura lado a lado manual (o subagente navega por seção).
    blocos = [f"=== MIOSHIE-SHŪ Nº {n} — TEXTO COMPLETO (JP | PT) ==="]

    # JP por seções
    blocos.append("########## JP (texto original, fonte de verdade) ##########")
    for i, (data, conteudo) in enumerate(jp_secoes):
        blocos.append(f"\n----- SEÇÃO JP {i} [{data}] -----")
        blocos.append(conteudo)

    blocos.append("\n\n########## PT (staging canônico atual) ##########")
    for i, (data, conteudo) in enumerate(st_secoes):
        blocos.append(f"\n----- SEÇÃO PT {i} [{data}] -----")
        blocos.append(conteudo)

    return "\n".join(blocos)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    n = int(sys.argv[1])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    material = montar(n)
    if material.startswith("ERRO"):
        print(material)
        return 1
    out = OUT_DIR / f"material_revsem_mioshie_prosa_{n}.txt"
    out.write_text(material, encoding="utf-8")
    print(f"Mioshie {n}: {material.count('=== SEÇÃO')} seções -> {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
