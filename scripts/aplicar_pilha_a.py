"""Aplica a pilha A — as correções em que os três auditores concordaram.

Só grava o que os TRÊS julgaram `aprovado`. Os `recusado` da pilha A não têm o
que fazer, e os `reformar` vão para uma lista à parte: o erro é real mas a
correção proposta não serve, então reescrevê-la é trabalho novo, não aplicação.

Cada salvaguarda aqui existe por causa de um dano real deste projeto, não por
precaução genérica:

· TRECHO LITERAL, nunca regex. Em 2026-08-07 um script contava por artigo e
  gravava com `texto.replace()` no arquivo inteiro: 76 trocas aprovadas viraram
  ~545 aplicadas, "coração" virou "cnorito", e 120 depoimentos passaram a dizer
  que a pessoa recebeu uma Imagem quando o japonês diz outra.
· ÚNICO DENTRO DA JANELA DO ARTIGO, não do arquivo. A troca foi decidida lendo
  um artigo; num livro de 200 depoimentos o mesmo trecho repete e a guarda por
  arquivo descartava trocas legítimas -- 54 de 159 numa passada.
· NUNCA EM ÂNCORA. Verificado em código antes de gravar, e não por julgamento:
  19 aprovações minhas mexiam em âncora e teriam quebrado a segmentação de sete
  obras. Um caso desses na pilha A é sinal de falha da triagem, e aborta.
· BACKUP POR ARQUIVO e ÂNCORAS REVALIDADAS depois de cada obra, com reversão
  automática se a contagem não bater.
· VARREDURA DE DANO ao final: a assinatura de termo escrito por cima de si
  mesmo ("proteções divinas divinas") só apareceu porque alguém procurou.

    python3 scripts/aplicar_pilha_a.py             # diagnóstico, nada grava
    python3 scripts/aplicar_pilha_a.py --aplicar
    python3 scripts/aplicar_pilha_a.py --reformar  # a lista que fica pendente
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import auditoria as A  # noqa: E402
import triagem as T  # noqa: E402
from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402
from aplica_no_artigo import janelas  # noqa: E402

PT_FONTE = RAIZ / "livros_publicacao_pt_revisado"
PT_STAGING = RAIZ / "reports/livros_trabalho/pt"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"
REGISTRO = RAIZ / "reports/varredura_padronizacao/APLICADO.json"
REPETE = re.compile(r"\b((?:[A-Za-zÀ-ÿ()º°]+)(?:\s+[A-Za-zÀ-ÿ()º°]+){0,4})\s+\1\b", re.I)


def e_ancora(obra: str, trecho: str) -> int | None:
    sp = SPEC_DIR / f"{obra}.json"
    if not sp.exists():
        return None
    for i, a in enumerate(json.loads(sp.read_text(encoding="utf-8")).get("articles", [])):
        anc = a.get("pt_anchor", "")
        if anc and (trecho in anc or anc[:40] in trecho):
            return i
    return None


def a_aplicar() -> dict[str, list[dict]]:
    """Só os `aprovado` da pilha A, agrupados por obra."""
    d1 = T._le(T.DS1)
    proc = {A.chave(r): r for r in A.procedentes()}
    feitos = set(json.loads(REGISTRO.read_text(encoding="utf-8"))
                 if REGISTRO.exists() else [])
    por_obra: dict[str, list[dict]] = defaultdict(list)
    for k in T.pilhas()["A"]:
        if k in feitos or d1[k]["veredito"] != "aprovado" or k not in proc:
            continue
        it = proc[k]
        por_obra[it["obra"]].append(
            {"chave": k, "artigo": it["artigo"], "de": it["de"], "para": it["para"]})
    return por_obra


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    if "--reformar" in sys.argv:
        d1 = T._le(T.DS1)
        r = [k for k in T.pilhas()["A"] if d1[k]["veredito"] == "reformar"]
        print(f"{len(r)} casos de pilha A em que os três disseram REFORMAR.\n"
              f"O erro é real, a correção proposta não serve — reescrevê-la é\n"
              f"trabalho novo, e fica pendente:\n")
        for k in r[:40]:
            print(f"  {k}")
        return

    por_obra = a_aplicar()
    tot = sum(len(v) for v in por_obra.values())
    print(f"{tot} correções a aplicar, em {len(por_obra)} obras\n")
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    feitas, pulos = [], []

    for obra, itens in sorted(por_obra.items()):
        f = PT_FONTE / obra
        if not f.exists():
            pulos += [(i["chave"], "obra ausente") for i in itens]
            continue
        texto = f.read_text(encoding="utf-8")
        jan = janelas(obra, texto)
        antes, n = texto, 0

        for it in itens:
            idx = e_ancora(obra, it["de"])
            if idx is not None:
                # a triagem não devia ter deixado passar: aborta este item
                pulos.append((it["chave"], f"É ÂNCORA do artigo {idx} — falha de triagem"))
                continue
            if jan is None:
                pulos.append((it["chave"], "janela do artigo não determinável"))
                continue
            if it["artigo"] >= len(jan):
                pulos.append((it["chave"], "índice de artigo fora da janela"))
                continue
            ini, fim = jan[it["artigo"]]
            bloco = texto[ini:fim]
            if bloco.count(it["de"]) != 1:
                pulos.append((it["chave"],
                              f"{bloco.count(it['de'])} ocorrências na janela do artigo"))
                continue
            texto = texto[:ini] + bloco.replace(it["de"], it["para"]) + texto[fim:]
            jan = janelas(obra, texto) or jan       # posições mudaram
            feitas.append(it["chave"])
            n += 1

        if not n:
            continue
        print(f"  {obra[:46]:<48} {n:>3} aplicadas")
        if not aplicar:
            continue

        shutil.copy(f, f.with_suffix(f".txt.bak_pilhaA_{carimbo}"))
        f.write_text(texto, encoding="utf-8")
        (PT_STAGING / obra).write_text(texto, encoding="utf-8")

        sp = SPEC_DIR / f"{obra}.json"
        if sp.exists():
            anc = [a.get("pt_anchor", "") for a in
                   json.loads(sp.read_text(encoding="utf-8")).get("articles", [])]
            if len(anc) > 1 and all(anc):
                try:
                    if len(split_by_anchors(clean_body(texto), anc, label=obra)) != len(anc):
                        raise ValueError("contagem")
                except ValueError as exc:
                    print(f"     *** ÂNCORA QUEBRADA ({exc}) — REVERTENDO {obra}")
                    f.write_text(antes, encoding="utf-8")
                    (PT_STAGING / obra).write_text(antes, encoding="utf-8")
                    feitas = [x for x in feitas if x not in {i["chave"] for i in itens}]
                    continue

        # dano de termo escrito por cima de si mesmo
        for m in REPETE.finditer(texto):
            if len(m.group(1).strip()) >= 5 and m.group(1).strip() not in antes:
                print(f"     *** REPETIÇÃO NOVA {m.group(1)!r} — REVERTENDO {obra}")
                f.write_text(antes, encoding="utf-8")
                (PT_STAGING / obra).write_text(antes, encoding="utf-8")
                feitas = [x for x in feitas if x not in {i["chave"] for i in itens}]
                break

    print(f"\n{len(feitas)} aplicadas, {len(pulos)} puladas")
    for k, m in pulos[:25]:
        print(f"  PULADO {k.split('|')[0][:30]} art{k.split('|')[1]}: {m}")
    if aplicar and feitas:
        ja = json.loads(REGISTRO.read_text(encoding="utf-8")) if REGISTRO.exists() else []
        REGISTRO.write_text(json.dumps(sorted(set(ja) | set(feitas)),
                                       ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"registro atualizado: {len(set(ja) | set(feitas))} aplicadas no total")
    if not aplicar:
        print("(diagnóstico apenas — rode com --aplicar)")


if __name__ == "__main__":
    main()
