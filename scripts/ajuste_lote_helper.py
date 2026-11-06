"""Apoio de leitura para o ajuste manual caso a caso (AJUSTE_LOTE*.json).

Não escreve nada. Só localiza o trecho no PT, mostra o parágrafo real e o
artigo japonês correspondente, para a decisão ser tomada lendo JP e PT lado
a lado (protocolo dos 213).

Uso:
    python3 scripts/ajuste_lote_helper.py mapa <lote.json>
    python3 scripts/ajuste_lote_helper.py caso <lote.json> <indice> [--jp]
    python3 scripts/ajuste_lote_helper.py jp <obra> <artigo> [ini] [fim]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

PT_FONTE = RAIZ / "livros_publicacao_pt_revisado"
PT_STAGING = RAIZ / "reports/livros_trabalho/pt"
JP_DIR = RAIZ / "reports/livros_trabalho/jp"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"


def spec(obra: str) -> dict:
    p = SPEC_DIR / f"{obra}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def jp_janelas(obra: str) -> list[tuple[int, int, str]]:
    """(ini, fim, titulo) de cada artigo no JP, pelas jp_anchor do spec."""
    texto = (JP_DIR / obra).read_text(encoding="utf-8")
    arts = spec(obra).get("articles", [])
    if not arts:
        return [(0, len(texto), "")]
    ini = []
    cur = 0
    for a in arts:
        anc = a.get("jp_anchor", "")
        p = texto.find(anc, cur) if anc else -1
        if p < 0:
            p = texto.find(anc) if anc else -1
        ini.append(p)
        if p >= 0:
            cur = p + len(anc)
    out = []
    for i, a in enumerate(arts):
        s = ini[i]
        e = next((ini[j] for j in range(i + 1, len(arts)) if ini[j] >= 0), len(texto))
        out.append((s, e, a.get("title_jp") or a.get("title_pt") or ""))
    return out


def paragrafo_de(texto: str, pos: int) -> tuple[int, int]:
    ini = texto.rfind("\n\n", 0, pos)
    ini = 0 if ini < 0 else ini + 2
    fim = texto.find("\n\n", pos)
    fim = len(texto) if fim < 0 else fim
    return ini, fim


def ocorrencias(texto: str, alvo: str) -> list[int]:
    out, i = [], 0
    while True:
        p = texto.find(alvo, i)
        if p < 0:
            return out
        out.append(p)
        i = p + 1


def cmd_mapa(lote: Path) -> None:
    casos = json.loads(lote.read_text(encoding="utf-8"))
    for i, c in enumerate(casos):
        pt = (PT_FONTE / c["obra"]).read_text(encoding="utf-8")
        nde = len(ocorrencias(pt, c["de"]))
        npara = len(ocorrencias(pt, c["para"]))
        print(f"{i:4d} de={nde} para={npara} {c['tipo'][:4]} {c['chave'][-24:]}")


def cmd_caso(lote: Path, idx: int, comjp: bool) -> None:
    casos = json.loads(lote.read_text(encoding="utf-8"))
    c = casos[idx]
    obra = c["obra"]
    pt = (PT_FONTE / obra).read_text(encoding="utf-8")
    print(f"### CASO {idx} [{c['tipo']}] {c['chave']}")
    print(f"DE  : {c['de']}")
    print(f"PARA: {c['para']}")
    print(f"LIM : {c['lim']}")
    occ = ocorrencias(pt, c["de"])
    print(f"ocorrencias de 'de': {len(occ)} em {occ}")
    print(f"ocorrencias de 'para': {len(ocorrencias(pt, c['para']))}")
    for p in occ:
        a, b = paragrafo_de(pt, p)
        print(f"\n--- PT parágrafo [{a}:{b}] (offset do 'de' = {p})")
        print(pt[a:b])
    if comjp:
        art = int(c["chave"].split("|")[1])
        jt = (JP_DIR / obra).read_text(encoding="utf-8")
        jw = jp_janelas(obra)
        if 0 <= art < len(jw):
            s, e, t = jw[art]
            print(f"\n=== JP artigo {art} [{s}:{e}] {t}")
            print(jt[s:e])


def cmd_jp(obra: str, art: int, ini: int | None, fim: int | None) -> None:
    jt = (JP_DIR / obra).read_text(encoding="utf-8")
    jw = jp_janelas(obra)
    s, e, t = jw[art]
    if ini is not None:
        s2 = s + ini
        e2 = s + fim if fim is not None else e
        print(f"=== JP artigo {art} [{s}+{ini}] {t}")
        print(jt[s2:e2])
    else:
        print(f"=== JP artigo {art} [{s}:{e}] len={e-s} {t}")
        print(jt[s:e])


if __name__ == "__main__":
    if sys.argv[1] == "mapa":
        cmd_mapa(Path(sys.argv[2]))
    elif sys.argv[1] == "caso":
        cmd_caso(Path(sys.argv[2]), int(sys.argv[3]), "--jp" in sys.argv)
    elif sys.argv[1] == "jp":
        a = sys.argv[4:]
        cmd_jp(sys.argv[2], int(sys.argv[3]),
               int(a[0]) if len(a) > 0 else None,
               int(a[1]) if len(a) > 1 else None)
