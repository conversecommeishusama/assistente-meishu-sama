"""Segundo auditor, em DeepSeek, sobre a mesma fila — parecer independente.

Não substitui a auditoria em `claude -p`: corre ao lado dela, sobre os mesmos
achados e com o MESMO dossiê (`auditoria.dossie`), para que a divergência
signifique divergência de julgamento e não de informação.

O valor não está em somar dois pareceres — está no desacordo. No teste cego de
2026-08-09, os 43 casos de concordância eram triviais e os 18 de divergência
continham tudo o que importava: três âncoras que eu aprovei por engano, dois
nomes próprios que ele entregou ao erro dominante do acervo, um achado
obsoleto e uma decisão de convenção que é do usuário.

Uso:
    python3 scripts/auditor_deepseek.py              # audita a fila
    python3 scripts/auditor_deepseek.py --comparar   # divergência medida
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
from goshinsho.services import agentic_search as ag  # noqa: E402

DESTINO = RAIZ / "reports/varredura_padronizacao/AUDITORIA_DEEPSEEK.json"
MODELO = "deepseek-v4-flash"
MAX_TOKENS = 32768
PARALELISMO = 4

SYSTEM = """Você audita correções propostas a uma tradução do japonês para o
português, do acervo de Meishu-Sama (Igreja Messiânica Mundial). Leia o
japonês e o português LINHA A LINHA. Nada é gravado no corpus por você — só o
veredito.

Três vereditos, e só três:

APROVADO — o erro é real e a correção está certa no sentido E na forma.
RECUSADO — não há erro; ou a correção está errada; ou apenas troca uma forma
           válida por outra igualmente válida.
REFORMAR — o erro é real, mas a correção não serve como está.

REGRAS QUE VIERAM DE ERRO REAL:

· O dossiê avisa em maiúsculas quando o trecho é ÂNCORA DE SEGMENTAÇÃO. Nesse
  caso o veredito é sempre REFORMAR, mesmo com a correção perfeita: mudar o
  texto quebra a busca do site e a spec teria de mudar junto.
· O dossiê avisa quando o trecho JÁ NÃO EXISTE no arquivo atual. Aí é
  RECUSADO — o achado veio de leitura anterior a um conserto.
· Contagem no acervo, quando aparecer, é CONTEXTO e nunca autoridade. Forma
  errada dominante continua errada: 重吉 não se lê "Shigekatsu" por mais que o
  acervo repita, e 伊都能売 é Izunome mesmo onde escreveram "Itsu no Me".
· A tradução é LIVRE por determinação do projeto. "O japonês não diz
  exatamente isso" não é erro. Só procede sentido trocado: sujeito ou objeto
  invertido, polaridade invertida, número/data/unidade diferente, fala
  atribuída a quem não falou, conteúdo omitido ou inventado, nome próprio ou
  termo doutrinário trocado.
· Glossário: o dossiê traz as entradas que tocam o trecho. Propor mudar uma
  decisão registrada nunca procede.
· Se a correção exigir mover fala entre Interlocutor: e Meishu-Sama:, é
  REFORMAR — a aplicação troca trecho literal, não move turnos.
· Kanji ou kana no português só entre aspas com romaji entre parênteses (ou o
  inverso). Fora disso, REFORMAR.
· Decisão de CONVENÇÃO é do usuário, não sua — citação bíblica, tratamento de
  palavra-travesseiro em poesia, ordem de nome próprio. Marque REFORMAR e diga
  que depende dele.
· Nome próprio e topônimo: confira a leitura de verdade. Se a correção propõe
  uma leitura que os kanji não sustentam, é REFORMAR mesmo que o texto atual
  também esteja errado.

Responda UMA linha:

<APROVADO|RECUSADO|REFORMAR> | <justificativa em uma frase, citando o japonês>
"""


def julga(k: str) -> dict:
    dos = A.dossie(k)
    r = ag._client().chat.completions.create(
        model=MODELO, max_tokens=MAX_TOKENS,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": dos + "\n\nSeu veredito?"}])
    txt = (r.choices[0].message.content or "").strip()
    prim = next((l for l in txt.splitlines() if l.strip()), "")
    v = prim.split("|")[0].strip().upper().strip("<>")
    v = {"APROVADO": "aprovado", "RECUSADO": "recusado",
         "REFORMAR": "reformar"}.get(v, "?")
    u = r.usage
    return {"veredito": v,
            "nota": prim.split("|", 1)[1].strip() if "|" in prim else prim,
            "tokens": (u.prompt_tokens or 0) + (u.completion_tokens or 0)}


def carrega() -> dict:
    return json.loads(DESTINO.read_text(encoding="utf-8")) if DESTINO.exists() else {}


def comparar() -> None:
    meu, dele = A.carrega(), carrega()
    comuns = [k for k in dele if k in meu]
    if not comuns:
        print("nenhum achado com os dois pareceres ainda")
        return
    conc = sum(1 for k in comuns if meu[k]["veredito"] == dele[k]["veredito"])
    print(f"{len(comuns)} achados com os dois pareceres")
    print(f"CONCORDÂNCIA {conc}/{len(comuns)} = {conc/len(comuns):.0%}")
    m = Counter((meu[k]["veredito"], dele[k]["veredito"]) for k in comuns)
    print(f"matriz (claude -> deepseek): {m.most_common()}")
    div = [k for k in comuns if meu[k]["veredito"] != dele[k]["veredito"]]
    if div:
        print(f"\n--- {len(div)} divergências, que é onde alguém precisa olhar ---")
        for k in div[:20]:
            print(f"\n  {k.split('|')[0][:34]} art{k.split('|')[1]}")
            print(f"    claude   [{meu[k]['veredito']:<9}] {meu[k]['nota'][:110]}")
            print(f"    deepseek [{dele[k]['veredito']:<9}] {dele[k]['nota'][:110]}")
    tk = sum(v.get("tokens", 0) for v in dele.values())
    print(f"\ncusto DeepSeek: US${tk/1e6*0.242:.4f} por {len(dele)} julgamentos")


def main() -> None:
    if "--comparar" in sys.argv:
        comparar()
        return
    feitos = carrega()
    # audita o que o outro auditor já julgou (para medir) e o que está na fila
    alvo = [A.chave(r) for r in A.procedentes() if A.chave(r) not in feitos]
    if "--so-comparaveis" in sys.argv:
        meu = A.carrega()
        alvo = [k for k in alvo if k in meu]
    lim = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else len(alvo)
    alvo = alvo[:lim]
    print(f"{len(alvo)} a julgar\n", flush=True)

    trava, n = threading.Lock(), [0]

    def trabalho(k):
        try:
            r = julga(k)
        except Exception as exc:
            r = {"veredito": "erro", "nota": repr(exc)[:120]}
        with trava:
            feitos[k] = r
            n[0] += 1
            if n[0] % 20 == 0:
                print(f"  [{n[0]}/{len(alvo)}]", flush=True)
                DESTINO.write_text(json.dumps(feitos, ensure_ascii=False, indent=1),
                                   encoding="utf-8")

    with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
        list(pool.map(trabalho, alvo))
    DESTINO.write_text(json.dumps(feitos, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    comparar()


if __name__ == "__main__":
    main()
