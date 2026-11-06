"""Contexto por caso do ajuste manual/semântico (protocolo dos 213).

Não altera nada: só mostra, para cada caso do lote, o parágrafo PT real onde o
`de` aparece e o trecho JP correspondente (mesmo artigo, janela proporcional),
para a leitura linha a linha JP<->PT ser feita à mão.

Uso:
    python3 scripts/ajuste_ctx.py <lote.json> <indice_inicial> [quantos]
    python3 scripts/ajuste_ctx.py <lote.json> --chave "<chave>"
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from implanta_semantico_v2 import (  # noqa: E402
    paragrafo, PT_FONTE, JP_DIR, carrega_jp_por_obra,
)
from aplica_no_artigo import janelas  # noqa: E402

_CACHE_JP: dict[str, list[str] | None] = {}
_CACHE_PT: dict[str, str] = {}


def pt(obra: str) -> str:
    if obra not in _CACHE_PT:
        _CACHE_PT[obra] = (PT_FONTE / obra).read_text(encoding="utf-8")
    return _CACHE_PT[obra]


def jp(obra: str) -> list[str] | None:
    if obra not in _CACHE_JP:
        _CACHE_JP[obra] = carrega_jp_por_obra(obra)
    return _CACHE_JP[obra]


def artigo_da_chave(chave: str) -> int | None:
    partes = chave.split("|")
    if len(partes) < 2:
        return None
    try:
        return int(partes[1])
    except ValueError:
        return None


def mostra(caso: dict, idx: int, jp_win: int = 1400) -> None:
    obra, de = caso["obra"], caso["de"]
    print("=" * 100)
    print(f"[{idx}] {caso['chave']}  ({caso['tipo']})")
    print(f"DE  : {de}")
    print(f"PARA: {caso['para']}")
    texto = pt(obra)
    n = texto.count(de)
    print(f"-- ocorrências de `de` no arquivo inteiro: {n}")
    art = artigo_da_chave(caso["chave"])
    jan = janelas(obra, texto)
    lim = None
    if jan and art is not None and art < len(jan):
        ini, fim = jan[art]
        lim = paragrafo(texto, ini, fim, de)
    if lim is None and n:
        p = texto.find(de)
        ini_p = texto.rfind("\n", 0, p) + 1
        fim_p = texto.find("\n", p)
        lim = (ini_p, fim_p if fim_p > 0 else len(texto))
    # o artigo REAL é aquele cuja janela contém o parágrafo achado -- o índice
    # da chave veio de uma segmentação anterior e pode ter deslocado
    if jan and lim:
        for i, (a, b) in enumerate(jan):
            if a <= lim[0] < b:
                if i != art:
                    print(f"-- artigo da chave={art}, artigo REAL pela posição={i}")
                art = i
                break
    if lim is None:
        print("!! `de` NÃO ENCONTRADO no PT")
    else:
        print(f"--- PARÁGRAFO PT [{lim[0]},{lim[1]}] ---")
        print(texto[lim[0]:lim[1]])
    jp_bruto = (JP_DIR / obra).read_text(encoding="utf-8")
    # 1) obras numeradas (senryū etc.): o número do parágrafo PT casa exato
    # número do item: o do PRÓPRIO trecho `de` quando a linha dele tem um,
    # senão o do início do parágrafo
    m = None
    if lim:
        par = texto[lim[0]:lim[1]]
        off = par.find(de)
        ini_ln = par.rfind("\n", 0, off) + 1 if off >= 0 else 0
        m = re.match(r"\s*(\d{1,5})\s*[,.]", par[ini_ln:]) or re.match(r"\s*(\d{1,5})\s*[,.]", par)
    if m:
        alvo = re.compile(r"^%s\s*,|^%s\s*、" % (m.group(1), m.group(1)), re.M)
        mm = alvo.search(jp_bruto)
        if mm:
            print(f"--- JP por número {m.group(1)} ---")
            print(jp_bruto[max(0, mm.start() - 200):mm.start() + 500])
            return
    # 2) senão, janela proporcional sobre o arquivo JP inteiro
    frac = (lim[0] / len(texto)) if lim else 0.0
    c = int(frac * len(jp_bruto))
    a0 = max(0, c - jp_win // 2)
    a1 = min(len(jp_bruto), c + jp_win)
    print(f"--- JP proporcional (frac={frac:.4f}) janela [{a0},{a1}] de {len(jp_bruto)} ---")
    print(jp_bruto[a0:a1])


def main() -> None:
    lote = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    if sys.argv[2] == "--chave":
        alvo = sys.argv[3]
        for i, c in enumerate(lote):
            if c["chave"] == alvo:
                mostra(c, i)
        return
    ini = int(sys.argv[2])
    qtd = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    for i in range(ini, min(ini + qtd, len(lote))):
        mostra(lote[i], i)


if __name__ == "__main__":
    main()
