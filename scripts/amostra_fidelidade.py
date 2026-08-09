"""Amostra de 100 trechos curtos para medir o que a etapa 4 encontraria.

Pedido do usuário antes de decidir o escopo: quanto a leitura de fidelidade
contribuiria de fato para o corpus, e quanto custaria.

Por que trecho CURTO e artigo INTEIRO ao mesmo tempo: num artigo de até ~2.000
caracteres os dois lados cabem na mesma chamada sem precisar fatiar -- e
fatiar foi justamente o que desalinhou na primeira tentativa, porque o japonês
e o português têm estrutura de parágrafo diferente (num artigo de 3.962
caracteres o pedaço 0 do japonês saiu com 4 caracteres contra 2.268 do
português). Artigo curto elimina o problema em vez de contorná-lo.

Amostra aleatória com semente fixa, para ser reproduzível e para não haver
escolha temática -- o resultado tem de valer para o acervo, não para os livros
que eu suspeitasse estarem piores.

Registra `reasoning_tokens` por chamada: é ele que permite medir o custo real
e comparar com o saldo da conta, em vez de estimar por tabela de preço.

Uso:
    python3 scripts/amostra_fidelidade.py
    python3 scripts/amostra_fidelidade.py --resumo
"""

from __future__ import annotations

import json
import random
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import leitura_fidelidade as L  # noqa: E402
from goshinsho.services import agentic_search as ag  # noqa: E402

DESTINO = RAIZ / "reports/varredura_padronizacao/AMOSTRA_FIDELIDADE.json"
N = 100
SEMENTE = 20260808
MIN_CAR, MAX_CAR = 500, 2000
PARALELISMO = 6
MAX_TOKENS = 65536


def amostra() -> list[dict]:
    todos = [x for x in L.alvos() if MIN_CAR <= len(x["pt"]) <= MAX_CAR]
    r = random.Random(SEMENTE)
    return r.sample(todos, min(N, len(todos)))


def julga(item: dict) -> dict:
    pedido = (f"ORIGEM: {item['obra']} (artigo {item['artigo']})\n\n"
              f"=== JAPONÊS ===\n{item['jp']}\n\n"
              f"=== PORTUGUÊS ===\n{item['pt']}")
    r = ag._client().chat.completions.create(
        model=L.MODELO, max_tokens=MAX_TOKENS,
        messages=[{"role": "system", "content": L.SYSTEM},
                  {"role": "user", "content": pedido}])
    u = r.usage
    det = getattr(u, "completion_tokens_details", None)
    texto = r.choices[0].message.content or ""

    achados = []
    for ln in texto.splitlines():
        partes = [x.strip() for x in ln.split("|")]
        if len(partes) < 4:
            continue
        grau = partes[0].strip().upper().strip("<>")
        if grau not in ("GRAVE", "MEDIO", "MÉDIO", "LEVE"):
            continue
        de, para, motivo = partes[1], partes[2], partes[3]
        if not de or de not in item["pt"]:
            continue                        # trecho tem de existir literalmente
        achados.append({"grau": "MEDIO" if grau == "MÉDIO" else grau,
                        "de": de, "para": para, "motivo": motivo})
    return {
        "obra": item["obra"], "artigo": item["artigo"],
        "car_pt": len(item["pt"]), "car_jp": len(item["jp"]),
        "achados": achados,
        "tok_entrada": u.prompt_tokens or 0,
        "tok_saida": u.completion_tokens or 0,
        "tok_raciocinio": getattr(det, "reasoning_tokens", 0) or 0,
        "finish": r.choices[0].finish_reason,
        "bruto": texto[:3000],
    }


def resumo() -> None:
    d = json.loads(DESTINO.read_text(encoding="utf-8"))
    ok = [r for r in d if "erro" not in r]
    c = Counter(a["grau"] for r in ok for a in r.get("achados", []))
    com = sum(1 for r in ok if r.get("achados"))
    te = sum(r.get("tok_entrada", 0) for r in ok)
    ts = sum(r.get("tok_saida", 0) for r in ok)
    tr = sum(r.get("tok_raciocinio", 0) for r in ok)
    cortados = sum(1 for r in ok if r.get("finish") != "stop")

    print(f"{len(ok)} trechos lidos ({len(d) - len(ok)} erros de API)")
    print(f"  {com} com algum achado ({com / max(1, len(ok)):.0%})")
    for k, v in c.most_common():
        print(f"    {k:<6} {v}")
    print(f"\n  entrada {te:,} | saída {ts:,} (raciocínio {tr:,}, "
          f"{tr / max(1, ts):.0%}) | {cortados} cortados por teto")
    print(f"  média por trecho: {te / max(1, len(ok)):,.0f} entrada, "
          f"{ts / max(1, len(ok)):,.0f} saída")
    proj = (te + ts) / max(1, len(ok)) * 3776
    print(f"  projeção para os 3.776 artigos: {proj / 1e6:,.0f} milhões de tokens")
    print("  (o custo real sai da comparação com o saldo da conta)")

    graves = [(r, a) for r in ok for a in r["achados"] if a["grau"] == "GRAVE"]
    if graves:
        print(f"\n--- {len(graves)} GRAVES ---")
        for r, a in graves[:25]:
            print(f"  {r['obra'][:26]} art{r['artigo']}")
            print(f"    {a['de'][:74]!r}")
            print(f"    -> {a['para'][:74]!r}")
            print(f"    {a['motivo'][:100]}")


def main() -> None:
    if "--resumo" in sys.argv:
        resumo()
        return
    itens = amostra()
    feitos = []
    if DESTINO.exists():
        feitos = [r for r in json.loads(DESTINO.read_text(encoding="utf-8"))
                  if "erro" not in r]
        vistos = {(r["obra"], r["artigo"]) for r in feitos}
        itens = [i for i in itens if (i["obra"], i["artigo"]) not in vistos]
    print(f"{len(itens)} trechos a ler (amostra aleatória, semente {SEMENTE})\n",
          flush=True)

    trava, n = threading.Lock(), [0]

    def trabalho(it):
        try:
            r = julga(it)
        except Exception as exc:
            r = {"obra": it["obra"], "artigo": it["artigo"],
                 "erro": repr(exc)[:140], "achados": []}
        with trava:
            feitos.append(r)
            n[0] += 1
            g = sum(1 for x in feitos for a in x.get("achados", [])
                    if a["grau"] == "GRAVE")
            print(f"[{n[0]:>3}/{len(itens)}] {r['obra'][:28]:<30} "
                  f"{len(r.get('achados', []))} achados (total {g} graves)",
                  flush=True)
            DESTINO.write_text(json.dumps(feitos, ensure_ascii=False, indent=1),
                               encoding="utf-8")

    with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
        list(pool.map(trabalho, itens))
    resumo()


if __name__ == "__main__":
    main()
