"""Pilha B — o Claude argumenta, o DeepSeek decide.

Desenho determinado pelo usuário em 2026-08-10. Quando os dois DeepSeek
concordam e o Claude discorda, o Claude escreve um contraponto e a palavra
final é do DeepSeek. Isso resolve o conflito de interesse que o usuário
apontou: quem desempata Claude contra DeepSeek não pode ser o Claude.

O risco desta peça é o oposto do anterior. O DeepSeek já julgou o caso duas
vezes; pedir que reconsidere convida a repetir o próprio parecer só porque é
seu. O prompt trata isso de frente -- mudar de posição diante de argumento bom
é o comportamento correto, não fraqueza; e manter a posição diante de
argumento fraco também é. O que não pode é decidir pela autoria.

    python3 scripts/contraponto.py --pendentes [N]
    python3 scripts/contraponto.py --dossie "<chave>"
    python3 scripts/contraponto.py --escrever "<chave>" "<contraponto>"
    python3 scripts/contraponto.py --decidir          # o DeepSeek fecha
    python3 scripts/contraponto.py --resumo
"""

from __future__ import annotations

import json
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import auditoria as A  # noqa: E402
import triagem as T  # noqa: E402
from goshinsho.services import agentic_search as ag  # noqa: E402

DESTINO = RAIZ / "reports/varredura_padronizacao/CONTRAPONTO.json"
MODELO = "deepseek-v4-flash"
MAX_TOKENS = 32768
PARALELISMO = 4

SYSTEM = """Você deu o veredito final sobre uma correção proposta a uma
tradução do japonês para o português, no acervo de Meishu-Sama.

Este caso já foi julgado duas vezes por auditores independentes que chegaram ao
MESMO veredito, e uma terceira vez por um auditor que discordou. Esse terceiro
escreveu um contraponto, que você recebe abaixo. Sua decisão encerra o caso.

COMO PESAR O CONTRAPONTO

O contraponto é informação nova, não uma autoridade. Trate-o como trataria um
argumento de colega: verifique cada afirmação dele contra o japonês que está no
dossiê, e aceite o que se sustentar.

Dois erros simétricos a evitar, e os dois são igualmente ruins:

· Manter o veredito anterior só porque é o seu, ou porque dois auditores já
  concordaram com ele. Dois pareceres iguais podem repetir o mesmo engano --
  já aconteceu neste projeto, quando dois auditores aplicaram uma entrada de
  glossário a uma ocorrência da palavra em sentido comum. Mudar de posição
  diante de argumento bom é o comportamento certo.
· Ceder porque o contraponto é longo, detalhado ou confiante. Argumento
  elaborado que não se sustenta no japonês continua não se sustentando.

Se o contraponto apontar um fato verificável no dossiê -- a leitura de um
kanji, uma partícula, um aviso de âncora, uma entrada de glossário --, o fato
decide. Se apontar uma preferência de estilo, não decide.

REGRAS QUE CONTINUAM VALENDO

· ÂNCORA DE SEGMENTAÇÃO avisada no dossiê: o veredito é REFORMAR, mesmo com a
  correção perfeita.
· Trecho que já não existe no arquivo atual: RECUSADO.
· Entrada de glossário vale para o SENTIDO DOUTRINÁRIO do termo. A mesma
  palavra em sentido comum não recebe a forma fixa; ali aplicá-la é o erro.
· Contagem no acervo é contexto, nunca autoridade: forma errada dominante
  continua errada.
· A tradução é livre por determinação do projeto. Distinção que o japonês marca
  e o português não marca sem ficar artificial -- 〜て貰う, 〜てあげる, direção de
  honorífico -- não é erro: se a diferença não sobrevive à tradução, RECUSADO
  porque não muda nada.
· Decisão de CONVENÇÃO é do usuário do projeto, não sua: citação bíblica,
  palavra-travesseiro em poesia, ordem de nome próprio. REFORMAR, dizendo que
  depende dele.

Responda UMA linha:

<APROVADO|RECUSADO|REFORMAR> | <MANTIVE|MUDEI> | <por quê, citando o japonês>
"""


def carrega() -> dict:
    return json.loads(DESTINO.read_text(encoding="utf-8")) if DESTINO.exists() else {}


def grava(d: dict) -> None:
    DESTINO.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")


def dossie(k: str) -> str:
    c, d1, d2 = A.carrega(), T._le(T.DS1), T._le(T.DS2)
    return (A.dossie(k) +
            f"\n=== OS TRÊS PARECERES ===\n"
            f"\nAuditor 1 — {d1[k]['veredito']}\n  {d1[k]['nota']}\n"
            f"\nAuditor 2 — {d2[k]['veredito']}\n  {d2[k]['nota']}\n"
            f"\nAuditor 3 (discordou) — {c[k]['veredito']}\n  {c[k]['nota']}\n")


def pendentes(n: int = 20) -> list[str]:
    feitos = carrega()
    return [k for k in T.pilhas()["B"]
            if k not in feitos or "contraponto" not in feitos[k]][:n]


def escrever(k: str, texto: str) -> None:
    d = carrega()
    d.setdefault(k, {})["contraponto"] = texto
    grava(d)
    print(f"contraponto gravado para {k}")


def decide(k: str, contraponto: str) -> dict:
    pedido = (dossie(k) +
              f"\n=== CONTRAPONTO DO AUDITOR 3 ===\n{contraponto}\n\n"
              f"Sua decisão final?")
    r = ag._client().chat.completions.create(
        model=MODELO, max_tokens=MAX_TOKENS,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": pedido}])
    txt = (r.choices[0].message.content or "").strip()
    prim = next((l for l in txt.splitlines() if l.strip()), "")
    partes = [x.strip() for x in prim.split("|")]
    v = partes[0].upper().strip("<>")
    v = {"APROVADO": "aprovado", "RECUSADO": "recusado",
         "REFORMAR": "reformar"}.get(v, "?")
    u = r.usage
    return {"final": v,
            "mudou": "MUDEI" in (partes[1].upper() if len(partes) > 1 else ""),
            "razao": partes[-1] if len(partes) > 2 else prim,
            "tokens": (u.prompt_tokens or 0) + (u.completion_tokens or 0)}


def decidir_todos() -> None:
    d = carrega()
    alvo = [k for k, v in d.items() if "contraponto" in v and "final" not in v]
    if not alvo:
        print("nenhum caso com contraponto à espera de decisão")
        return
    print(f"{len(alvo)} casos para o DeepSeek fechar\n", flush=True)
    trava = threading.Lock()

    def trabalho(k):
        try:
            r = decide(k, d[k]["contraponto"])
        except Exception as exc:
            r = {"final": "erro", "razao": repr(exc)[:110]}
        with trava:
            d[k].update(r)
            grava(d)

    with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
        list(pool.map(trabalho, alvo))
    resumo()


def resumo() -> None:
    d = carrega()
    com = [v for v in d.values() if "final" in v and v["final"] != "erro"]
    if not com:
        print(f"{len(d)} com contraponto, nenhum decidido ainda")
        return
    c, dd = A.carrega(), T._le(T.DS1)
    mud = sum(1 for v in com if v.get("mudou"))
    venceu_claude = sum(1 for k, v in d.items()
                        if v.get("final") and k in c and v["final"] == c[k]["veredito"])
    print(f"{len(com)} decididos pelo DeepSeek após contraponto")
    print(f"  mudou de posição   {mud} ({mud/len(com):.0%})")
    print(f"  ficou com o Claude {venceu_claude} ({venceu_claude/len(com):.0%})")
    print(f"  vereditos finais   {dict(Counter(v['final'] for v in com))}")
    tk = sum(v.get("tokens", 0) for v in com)
    print(f"  custo US${tk/1e6*0.242:.3f}")


def main() -> None:
    if "--dossie" in sys.argv:
        print(dossie(sys.argv[sys.argv.index("--dossie") + 1]))
    elif "--escrever" in sys.argv:
        i = sys.argv.index("--escrever")
        escrever(sys.argv[i + 1], sys.argv[i + 2])
    elif "--decidir" in sys.argv:
        decidir_todos()
    elif "--resumo" in sys.argv:
        resumo()
    else:
        n = int(sys.argv[sys.argv.index("--pendentes") + 1]) if len(sys.argv) > 2 else 20
        p = pendentes(n)
        print(f"{len(T.pilhas()['B'])} na pilha B; {len(p)} sem contraponto:\n")
        for k in p:
            print(f"  {k}")


if __name__ == "__main__":
    main()
