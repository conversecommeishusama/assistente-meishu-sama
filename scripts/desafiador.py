"""Desafiador de consenso — o «diferencial do Claude» como tarefa explícita.

Pergunta do usuário em 2026-08-10: dá para um agente DeepSeek dedicado fazer
só aquilo que o Claude acrescenta?

O dia sugere que sim. Toda vez que identificamos algo que só o Claude pegava,
viramos em instrução ou em código e o DeepSeek passou a pegar: a âncora virou
verificação em código, o sentido do glossário virou regra. O diferencial não
parece capacidade fixa, e sim o resíduo do que ainda não foi nomeado.

A tarefa aqui é DIFERENTE de auditar. Auditar leva dois DeepSeek à mesma
conclusão em 92% dos casos -- eles convergem porque compartilham o modo de
ler. O pedido aqui inverte o incentivo: dado que dois auditores concordaram,
procurar a razão mais forte para os DOIS estarem errados juntos.

O teste é cego: o desafiador NÃO vê o parecer do Claude. Se chegar sozinho à
posição dele na maioria dos 23 casos em que DS1=DS2≠Claude, o diferencial é
encodável.

    python3 scripts/desafiador.py --teste     # os 23 casos, cego
    python3 scripts/desafiador.py --resumo
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

DESTINO = RAIZ / "reports/varredura_padronizacao/DESAFIADOR.json"
MODELO = "deepseek-v4-flash"
MAX_TOKENS = 32768
PARALELISMO = 4

SYSTEM = """Dois auditores independentes examinaram esta correção proposta a
uma tradução do japonês para o português e chegaram ao MESMO veredito. Seu
trabalho não é auditar de novo — é procurar por que os dois podem estar
errados juntos.

Consenso entre dois leitores parecidos não é prova. Eles podem repetir o mesmo
engano, e neste projeto isso já aconteceu: dois auditores recusaram uma
correção porque o glossário fixa 曇り → «nuvens espirituais», sem perceber que
ali a palavra estava num exame de saúde e significava sombra no pulmão. A
entrada de glossário até trazia a ressalva; os dois passaram por cima.

ONDE PROCURAR — os modos conhecidos de erro compartilhado:

· Aplicar entrada de glossário a uma ocorrência da palavra em SENTIDO COMUM.
  A entrada vale para o sentido doutrinário: 曇り como mácula do corpo
  espiritual, não sombra de raio-X; 理 como princípio, não «Caminho Perfeito»
  (que é 道理); 教修 como o curso, não uma palestra qualquer.
· Aceitar como certa a forma DOMINANTE no acervo. Erro repetido continua erro:
  重吉 não se lê "Shigekatsu", 伊都能売 é Izunome mesmo onde escreveram outra
  coisa.
· Corrigir o SENTIDO e deixar a forma portuguesa quebrada — concordância de
  gênero ou número, termo fora do glossário, romanização que o acervo não usa.
· Tratar como erro uma distinção que o japonês marca e o português não marca
  sem ficar artificial: 〜て貰う, 〜てあげる, direção de honorífico.
· Não reparar que o trecho é ÂNCORA DE SEGMENTAÇÃO (o dossiê avisa) ou que já
  não existe no arquivo atual.
· Ler o japonês certo e errar quem é o sujeito de uma oração encaixada, ou
  qual substantivo um adjetivo qualifica.

REGRA DE HONESTIDADE

Se depois de procurar você não achar razão real para os dois estarem errados,
diga isso. Consenso correto é o caso comum, e inventar objeção para justificar
sua existência é pior que não achar nada. Objeção sem apoio no japonês do
dossiê não vale.

Responda UMA linha:

SUSTENTA | <por que o consenso está certo, em uma frase>
DERRUBA | <APROVADO|RECUSADO|REFORMAR> | <o que os dois erraram, citando o japonês>
"""


def julga(k: str) -> dict:
    d1, d2 = T._le(T.DS1), T._le(T.DS2)
    pedido = (A.dossie(k) +
              f"\n=== O CONSENSO DOS DOIS AUDITORES ===\n"
              f"\nAmbos disseram: {d1[k]['veredito'].upper()}\n"
              f"  auditor 1: {d1[k]['nota']}\n"
              f"  auditor 2: {d2[k]['nota']}\n"
              f"\nEles podem estar errados juntos?")
    r = ag._client().chat.completions.create(
        model=MODELO, max_tokens=MAX_TOKENS,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": pedido}])
    txt = (r.choices[0].message.content or "").strip()
    prim = next((l for l in txt.splitlines() if l.strip()), "")
    partes = [x.strip() for x in prim.split("|")]
    derruba = partes[0].upper().startswith("DERRUBA")
    v = ""
    if derruba and len(partes) > 1:
        v = {"APROVADO": "aprovado", "RECUSADO": "recusado",
             "REFORMAR": "reformar"}.get(partes[1].upper().strip("<>"), "")
    u = r.usage
    return {"derruba": derruba, "veredito": v, "razao": partes[-1],
            "tokens": (u.prompt_tokens or 0) + (u.completion_tokens or 0)}


def carrega() -> dict:
    return json.loads(DESTINO.read_text(encoding="utf-8")) if DESTINO.exists() else {}


def resumo() -> None:
    d, c = carrega(), A.carrega()
    ok = [k for k, v in d.items() if "erro" not in v]
    if not ok:
        print("nada julgado ainda")
        return
    der = [k for k in ok if d[k]["derruba"]]
    # chegou sozinho à posição do Claude, sem tê-la visto?
    igual = [k for k in der if k in c and d[k]["veredito"] == c[k]["veredito"]]
    print(f"{len(ok)} casos de consenso DS1=DS2 desafiados às cegas")
    print(f"  sustentou o consenso   {len(ok)-len(der)}")
    print(f"  derrubou               {len(der)}")
    print(f"  e ao derrubar, chegou à posição do Claude sem vê-la: "
          f"{len(igual)}/{len(der) or 1} = {len(igual)/max(1,len(der)):.0%}")
    print(f"  cobertura da posição do Claude no total: {len(igual)}/{len(ok)} = "
          f"{len(igual)/len(ok):.0%}")
    tk = sum(d[k].get("tokens", 0) for k in ok)
    print(f"  custo US${tk/1e6*0.242:.3f}")


def alvos_pilha_a() -> list[str]:
    """Onde ninguém está olhando: os casos em que os auditores já concordam.

    A pilha A é aplicada automaticamente, então é justamente ali que um erro
    compartilhado passaria sem ser visto. Custa US$0,002 por caso.
    """
    d1, d2 = T._le(T.DS1), T._le(T.DS2)
    return [k for k in d1 if k in d2
            and d1[k]["veredito"] == d2[k]["veredito"]
            and d1[k]["veredito"] in ("aprovado", "recusado", "reformar")]


def main() -> None:
    if "--resumo" in sys.argv:
        resumo()
        return
    if "--pilhaA" in sys.argv:
        feitos = carrega()
        alvo = [k for k in alvos_pilha_a() if k not in feitos]
        print(f"{len(alvo)} casos de consenso a desafiar\n", flush=True)
        trava, n = threading.Lock(), [0]
        def trabalho(k):
            try:
                r = julga(k)
            except Exception as exc:
                r = {"erro": repr(exc)[:110]}
            with trava:
                feitos[k] = r
                n[0] += 1
                if n[0] % 25 == 0:
                    print(f"  [{n[0]}/{len(alvo)}]", flush=True)
                    DESTINO.write_text(json.dumps(feitos, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
        with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
            list(pool.map(trabalho, alvo))
        DESTINO.write_text(json.dumps(feitos, ensure_ascii=False, indent=1),
                           encoding="utf-8")
        resumo()
        return
    ds2v = json.loads((RAIZ / "reports/varredura_padronizacao/TESTE_DS2.json")
                      .read_text(encoding="utf-8"))
    d1, c = T._le(T.DS1), A.carrega()
    alvo = [k for k in ds2v
            if k in d1 and k in c
            and ds2v[k]["veredito"] == d1[k]["veredito"] != c[k]["veredito"]]
    feitos = carrega()
    alvo = [k for k in alvo if k not in feitos]
    print(f"{len(alvo)} casos de DS1=DS2≠Claude, desafiados às cegas\n", flush=True)
    trava = threading.Lock()

    def trabalho(k):
        try:
            r = julga(k)
        except Exception as exc:
            r = {"erro": repr(exc)[:110]}
        with trava:
            feitos[k] = r
            DESTINO.write_text(json.dumps(feitos, ensure_ascii=False, indent=1),
                               encoding="utf-8")

    with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
        list(pool.map(trabalho, alvo))
    resumo()


if __name__ == "__main__":
    main()
