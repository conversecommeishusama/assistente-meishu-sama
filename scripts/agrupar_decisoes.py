"""Agrupa a pilha C por DECISÃO, não por natureza do erro.

O agrupador anterior classificava por palavra-chave na justificativa e jogava
metade dos casos em «outros» — a mesma técnica que falhou cinco vezes neste
projeto. E mesmo os grupos que acertava eram inúteis para o usuário: «sujeito
ou agente, 98 casos» não é uma decisão, são 98 passagens distintas.

O que forma lote é a PERGUNTA compartilhada. «Como tratar palavra-travesseiro
em poesia?» resolve dezenas de poemas de uma vez. «幽世大神 fica Mundo Oculto ou
entra no glossário?» resolve todas as ocorrências. O usuário decide a classe,
não o caso.

Duas passadas, porque uma taxonomia inventada antes de ler os dados seria
adivinhação:

  1. o modelo lê uma amostra larga das justificativas e PROPÕE as decisões
     distintas que o usuário precisa tomar
  2. cada caso é atribuído a uma delas, ou marcado como individual quando não
     couber em nenhuma — casos individuais são resultado legítimo, não falha

    python3 scripts/agrupar_decisoes.py            # roda as duas passadas
    python3 scripts/agrupar_decisoes.py --relatorio
"""

from __future__ import annotations

import json
import random
import sys
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import auditoria as A  # noqa: E402
import triagem as T  # noqa: E402
from goshinsho.services import agentic_search as ag  # noqa: E402

DESTINO = RAIZ / "reports/varredura_padronizacao/DECISOES.json"
MODELO = "deepseek-v4-flash"
AMOSTRA = 90
# Teto medido, não arbitrado: na taxonomia o raciocínio sozinho consumiu 17.007
# tokens e o texto útil foram 4.003. Com o teto de 16.384 que estava aqui, o
# raciocínio estourava o orçamento e a resposta vinha VAZIA -- a mesma falha já
# documentada neste projeto para a leitura de fidelidade, que precisou de 65.536.
TETO_TAXONOMIA = 65536
TETO_ATRIBUI = 8192
PARALELISMO = 8

SYS_TAXONOMIA = """Você lê justificativas de auditoria de uma tradução do
japonês para o português e identifica quais DECISÕES distintas o responsável
pelo projeto precisa tomar.

O objetivo não é classificar por tipo de erro. «Sujeito trocado» não é uma
decisão — são muitas passagens diferentes, cada uma com sua resposta. Uma
DECISÃO é uma pergunta cuja resposta resolve vários casos de uma vez:

  · «palavra-travesseiro (makura-kotoba) em poesia: traduzir ou omitir?»
  · «幽世大神 — qual forma canônica, e entra no glossário?»
  · «citação bíblica: forma canônica em português ou tradução literal do
     japonês que Meishu-Sama cita?»
  · «topônimo histórico: romanização da leitura de época ou a moderna?»

Repare que são perguntas de CONVENÇÃO ou de GLOSSÁRIO — coisas que valem para
o acervo inteiro. Divergências que dependem só de ler aquela passagem não
formam grupo, e é correto deixá-las de fora.

Proponha entre 8 e 25 decisões. Para cada uma:

DECISAO | <a pergunta, em uma linha, como o responsável a leria> | <como reconhecer os casos que caem nela>

Nada além dessas linhas.
"""

SYS_ATRIBUI = """Você atribui um caso de auditoria a uma das decisões listadas,
ou marca como individual.

Marque INDIVIDUAL sem hesitar quando o caso depender de ler aquela passagem
específica e não de uma convenção que valha para o acervo. A maioria dos casos
é individual, e forçá-los num grupo produziria lotes falsos — o responsável
aprovaria em bloco coisas que precisavam de leitura.

Responda UMA linha:

<número da decisão> | <por que cabe nela>
INDIVIDUAL | <por que não cabe em nenhuma>
"""


def casos() -> list[dict]:
    d1, d2, ds = T._le(T.DS1), T._le(T.DS2), T._le(T.DES)
    proc = {A.chave(r): r for r in A.procedentes()}
    out = []
    for k in T.pilhas()["C"]:
        if k not in proc:
            continue
        notas = [d1[k]["nota"], d2[k]["nota"]]
        if k in ds and "erro" not in ds[k]:
            notas.append(ds[k]["razao"])
        out.append({"chave": k, "obra": proc[k]["obra"],
                    "de": proc[k]["de"], "para": proc[k]["para"],
                    "v1": d1[k]["veredito"], "v2": d2[k]["veredito"],
                    "notas": notas})
    return out


def taxonomia(cs: list[dict]) -> list[dict]:
    am = random.Random(20260810).sample(cs, min(AMOSTRA, len(cs)))
    corpo = "\n\n".join(
        f"[{i}] {c['de'][:90]} -> {c['para'][:90]}\n    " +
        "\n    ".join(n[:170] for n in c["notas"]) for i, c in enumerate(am))
    r = ag._client().chat.completions.create(
        model=MODELO, max_tokens=TETO_TAXONOMIA,
        messages=[{"role": "system", "content": SYS_TAXONOMIA},
                  {"role": "user", "content":
                   f"{len(am)} casos de uma pilha de {len(cs)}:\n\n{corpo}\n\n"
                   f"Quais decisões distintas o responsável precisa tomar?"}])
    dec = []
    for l in (r.choices[0].message.content or "").splitlines():
        p = [x.strip() for x in l.split("|")]
        if len(p) >= 3 and p[0].upper().startswith("DECISAO"):
            dec.append({"pergunta": p[1], "criterio": p[2]})
    return dec


def atribui(c: dict, dec: list[dict]) -> dict:
    lista = "\n".join(f"{i+1}. {d['pergunta']}  ({d['criterio']})"
                      for i, d in enumerate(dec))
    r = ag._client().chat.completions.create(
        model=MODELO, max_tokens=TETO_ATRIBUI,
        messages=[{"role": "system", "content": SYS_ATRIBUI},
                  {"role": "user", "content":
                   f"DECISÕES:\n{lista}\n\nCASO:\n{c['de'][:200]}\n-> {c['para'][:200]}\n" +
                   "\n".join(n[:220] for n in c["notas"])}])
    prim = next((l for l in (r.choices[0].message.content or "").splitlines()
                 if l.strip()), "")
    p = [x.strip() for x in prim.split("|")]
    if p and p[0].isdigit() and 1 <= int(p[0]) <= len(dec):
        return {"decisao": int(p[0]), "razao": p[-1]}
    return {"decisao": None, "razao": p[-1] if len(p) > 1 else prim}


def relatorio() -> None:
    d = json.loads(DESTINO.read_text(encoding="utf-8"))
    dec, at = d["decisoes"], d["atribuicoes"]
    g = Counter(v["decisao"] for v in at.values())
    ind = g.get(None, 0)
    print(f"{len(at)} casos da pilha C\n")
    print(f"  {len(at)-ind} cabem em {sum(1 for i in g if i)} decisões de lote")
    print(f"  {ind} individuais — precisam de leitura caso a caso\n")
    for i, x in enumerate(dec, 1):
        n = g.get(i, 0)
        if n:
            print(f"  {n:>4}  {x['pergunta'][:96]}")


def main() -> None:
    if "--relatorio" in sys.argv:
        relatorio()
        return
    cs = casos()
    print(f"{len(cs)} casos na pilha C\n", flush=True)
    dec = taxonomia(cs)
    # Sem esta parada, a versão anterior seguiu com a lista VAZIA e gastou 781
    # chamadas classificando cada caso contra nada, produzindo «781 individuais»
    # -- um resultado que parecia conclusão e era ausência de taxonomia.
    if len(dec) < 3:
        print(f"ABORTADO: a taxonomia devolveu {len(dec)} decisões. Sem pelo "
              f"menos 3 não há em que classificar, e seguir gastaria "
              f"{len(cs)} chamadas para nada.")
        sys.exit(1)
    print(f"{len(dec)} decisões propostas:\n")
    for i, x in enumerate(dec, 1):
        print(f"  {i}. {x['pergunta'][:100]}")
    print(flush=True)

    at, trava, n = {}, threading.Lock(), [0]

    def trabalho(c):
        try:
            r = atribui(c, dec)
        except Exception as exc:
            r = {"decisao": None, "razao": f"erro: {exc!r}"[:80]}
        with trava:
            at[c["chave"]] = r
            n[0] += 1
            if n[0] % 50 == 0:
                print(f"  [{n[0]}/{len(cs)}]", flush=True)

    with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
        list(pool.map(trabalho, cs))
    DESTINO.write_text(json.dumps({"decisoes": dec, "atribuicoes": at},
                                  ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    relatorio()


if __name__ == "__main__":
    main()
