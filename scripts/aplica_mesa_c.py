"""Aplica as 135 decisões da mesa (A/B/OUTRO/MANTER) sobre os 143 casos residuais
da pilha C -- as que já foram lidas por mim (Claude), não pelo DeepSeek.

Reaproveita inteiramente o mecanismo de `aplicar_semantico.py`: o DeepSeek
reescreve o PARÁGRAFO (ajustando concordância ao redor da correção), o script
só contém -- a diferença tem de caber no vão do trecho, o parágrafo não pode
inchar, a âncora é revalidada e a obra inteira é revertida se a contagem de
artigos mudar.

A fonte da correção (de/para) é `DECIDIDO_MESA_C.json`, cruzado com
`dossies_mesa_c.casos()` para obra/artigo/texto original:

    A      -> de = caso["de"], para = caso["t1"] (redação do 1º leitor)
    B      -> de = caso["de"], para = caso["t2"] (redação do 2º leitor)
    OUTRO  -> de = decisão["de"] ou caso["de"], para = decisão["texto"] (meu)
    MANTER -> ignorado (nada a aplicar)
    USUARIO-> ignorado (fica para a mesa do usuário)

    python3 scripts/aplica_mesa_c.py             # ensaio, nada gravado
    python3 scripts/aplica_mesa_c.py --aplicar
"""

from __future__ import annotations

import json
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import dossies_mesa_c as D  # noqa: E402
from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402
from aplica_no_artigo import janelas  # noqa: E402
from aplicar_semantico import (SPEC_DIR, PT_FONTE, PT_STAGING,  # noqa: E402
                               contido, emenda, paragrafo)

R = RAIZ / "reports/varredura_padronizacao"
DECIDIDO = R / "DECIDIDO_MESA_C.json"
REGISTRO = R / "APLICADO_MESA_C.json"


def pendentes() -> list[dict]:
    dec = json.loads(DECIDIDO.read_text(encoding="utf-8"))
    cs = {c["chave"]: c for c in D.casos()}
    feitos = set(json.loads(REGISTRO.read_text(encoding="utf-8"))
                 if REGISTRO.exists() else [])
    out = []
    for chave, v in dec.items():
        if chave in feitos or v["decisao"] in ("MANTER", "USUARIO"):
            continue
        c = cs.get(chave)
        if not c:
            continue
        de = v.get("de") or c["de"]
        if v["decisao"] == "A":
            para = c["t1"]
        elif v["decisao"] == "B":
            para = c["t2"]
        elif v["decisao"] == "OUTRO":
            para = v["texto"]
        else:
            continue
        if not para.strip() or para.strip() == de.strip():
            continue
        out.append({"chave": chave, "obra": c["obra"], "artigo": c["artigo"],
                    "de": de, "para": para})
    return out


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    itens = pendentes()
    por_obra: dict[str, list[dict]] = {}
    for it in itens:
        por_obra.setdefault(it["obra"], []).append(it)
    print(f"{len(itens)} decisões a aplicar, em {len(por_obra)} obras\n", flush=True)

    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    aplicadas: list[str] = []
    recusadas: list[tuple[str, str]] = []

    pedidos, textos, jp_por_obra = [], {}, {}
    for obra, lst in sorted(por_obra.items()):
        f = PT_FONTE / obra
        if not f.exists():
            recusadas += [(x["chave"], "obra inexistente") for x in lst]
            continue
        textos[obra] = f.read_text(encoding="utf-8")
        try:
            spj = json.loads((SPEC_DIR / f"{obra}.json").read_text(encoding="utf-8"))
            jp_por_obra[obra] = split_by_anchors(
                clean_body((RAIZ / f"reports/livros_trabalho/jp/{obra}").read_text(encoding="utf-8")),
                [a["jp_anchor"] for a in spj["articles"]], label=obra)
        except Exception:
            jp_por_obra[obra] = None
        jan0 = janelas(obra, textos[obra])
        for it in lst:
            if jan0 is None or it["artigo"] >= len(jan0):
                recusadas.append((it["chave"], "janela do artigo indeterminável"))
                continue
            ini, fim = jan0[it["artigo"]]
            lim = paragrafo(textos[obra], ini, fim, it["de"])
            if lim is None:
                recusadas.append((it["chave"], "trecho não está na janela do artigo"))
                continue
            par = textos[obra][lim[0]:lim[1]]
            if par.count(it["de"]) != 1:
                recusadas.append((it["chave"], f"{par.count(it['de'])} ocorrências no parágrafo"))
                continue
            jpb = jp_por_obra[obra]
            jp = jpb[it["artigo"]] if jpb and it["artigo"] < len(jpb) else ""
            pedidos.append((obra, it, par, jp))

    emendas: dict[str, str] = {}
    trava, feito = threading.Lock(), [0]

    def calcula(arg):
        obra, it, par, jp = arg
        try:
            novo = emenda(jp, par, it["de"], it["para"])
        except Exception as exc:
            with trava:
                recusadas.append((it["chave"], f"erro de API: {exc!r}"[:70]))
            return
        motivo = contido(par, novo, it["de"], it["para"])
        with trava:
            feito[0] += 1
            if motivo:
                recusadas.append((it["chave"], motivo))
            else:
                emendas[it["chave"]] = novo
            if feito[0] % 25 == 0:
                print(f"  [{feito[0]}/{len(pedidos)}] {len(emendas)} aceitas, "
                      f"{len(recusadas)} recusadas", flush=True)

    if pedidos:
        with ThreadPoolExecutor(max_workers=12) as pool:
            list(pool.map(calcula, pedidos))
    print(f"\ncálculo: {len(emendas)} aceitas, {len(recusadas)} recusadas\n", flush=True)

    for obra, lst in sorted(por_obra.items()):
        if obra not in textos:
            continue
        texto, antes, n = textos[obra], textos[obra], 0
        feitas_obra = []
        for it in [x for x in lst if x["chave"] in emendas]:
            jan = janelas(obra, texto)
            if jan is None or it["artigo"] >= len(jan):
                recusadas.append((it["chave"], "janela perdida durante a gravação"))
                break
            ini, fim = jan[it["artigo"]]
            lim = paragrafo(texto, ini, fim, it["de"])
            if lim is None or texto[lim[0]:lim[1]].count(it["de"]) != 1:
                recusadas.append((it["chave"], "parágrafo mudou desde o cálculo"))
                continue
            texto = texto[:lim[0]] + emendas[it["chave"]] + texto[lim[1]:]
            feitas_obra.append(it["chave"])
            n += 1
        if not n:
            continue
        if not aplicar:
            print(f"  {obra[:44]:<46} {n:>3} emendadas (ensaio)")
            continue
        f = PT_FONTE / obra
        shutil.copy(f, f.with_suffix(f".txt.bak_mesaC_{carimbo}"))
        f.write_text(texto, encoding="utf-8")
        (PT_STAGING / obra).write_text(texto, encoding="utf-8")
        sp = SPEC_DIR / f"{obra}.json"
        if sp.exists():
            anc = [x.get("pt_anchor", "") for x in
                   json.loads(sp.read_text(encoding="utf-8")).get("articles", [])]
            if len(anc) > 1 and all(anc):
                try:
                    if len(split_by_anchors(clean_body(texto), anc, label=obra)) != len(anc):
                        raise ValueError("contagem")
                except ValueError:
                    print(f"  *** ÂNCORA QUEBRADA — REVERTENDO {obra}")
                    f.write_text(antes, encoding="utf-8")
                    (PT_STAGING / obra).write_text(antes, encoding="utf-8")
                    continue
        aplicadas += feitas_obra
        print(f"  {obra[:44]:<46} {n:>3} aplicadas")

    print(f"\n{len(aplicadas)} aplicadas, {len(recusadas)} recusadas pela verificação")
    for k, m in recusadas[:40]:
        print(f"  {k.split('|')[0][:26]} art{k.split('|')[1]}: {m}")
    if aplicar and aplicadas:
        ja = json.loads(REGISTRO.read_text(encoding="utf-8")) if REGISTRO.exists() else []
        REGISTRO.write_text(json.dumps(sorted(set(ja) | set(aplicadas)),
                                       ensure_ascii=False, indent=1), encoding="utf-8")
    if not aplicar:
        print("(ensaio — nada gravado; rode com --aplicar)")


if __name__ == "__main__":
    main()
