"""Segunda passada semântica: as quatro decisões de 2026-08-08.

Mesma disciplina da primeira (`reaplica_semantico.py`), que existe porque os
scripts de substituição produziram 355 erros em 1.292 alterações:

    "TODO O TRABALHO DEVE SER FEITO LINHA A LINHA COMPARANDO JP PT DE FORMA
     SEMÂNTICA."

Nada aqui nasce de busca-e-troca. O modelo lê o artigo japonês e o português
lado a lado e devolve trecho a trecho. Cada proposta é conferida contra o
português antes de gravar, e só grava se o trecho for único no arquivo.

Só entra o artigo em que o japonês traz a chave MAIS vezes do que o português
traz a forma canônica -- assim uma obra já correta não gasta leitura.

Uso:
    python3 scripts/reaplica_semantico2.py            # lê e propõe
    python3 scripts/reaplica_semantico2.py --aplicar  # grava o já lido
"""

from __future__ import annotations

import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import reaplica_semantico as R  # noqa: E402  (reaproveita artigos/aplicar)
from goshinsho.services import agentic_search as ag  # noqa: E402

DESTINO = RAIZ / "reports/varredura_padronizacao/REAPLICACAO_SEMANTICA5.json"
MODELO = "deepseek-v4-flash"
PARALELISMO = 8

# (rótulo, regex no japonês, regex da forma canônica no português)
# Os lookbehind excluem os compostos que já têm decisão própria e diferente.
GATILHOS = [
    # resíduo: o gatilho por contagem não pega o artigo que JÁ tem a forma
    # canônica num ponto e a perífrase noutro -- aqui o alvo é a perífrase
    ("御屏風観音", r"御\s*屏\s*風\s*観\s*音", r"(?!x)x"),
    ("邪神", r"邪\s*神", r"(?!x)x"),
]

SYSTEM = """Você é revisor de tradução japonês→português do acervo de Meishu-Sama (Igreja Messiânica Mundial).

Recebe UM artigo em japonês e o MESMO artigo em português. Duas formas ficaram para trás numa passada anterior e é só isso que você procura aqui.

御屏風観音様 / 御屏風観音 → "Byōbu Kannon", SEM ARTIGO.
    A perífrase "a Kannon do biombo" / "a imagem de Kannon do biombo" / "o
    biombo com a imagem de Kannon" deve virar "Byōbu Kannon".
    A GLOSA "(Kannon do biombo)" vai SÓ na 1ª menção deste artigo. Se o
    artigo já traz "Byōbu Kannon (Kannon do biombo)" em algum ponto, as
    demais ocorrências ficam só "Byōbu Kannon", sem glosa.
    Preposição contraída vira simples: "diante DA" → "diante DE";
    "cultuando A Kannon do biombo" → "cultuando Byōbu Kannon".

邪神 → "Divindades malignas" (plural) / "Divindade maligna" (singular).
    Nunca "deuses malignos" nem "deus maligno".
    CUIDADO: 悪霊 é "espíritos malignos" e 正神 é "divindades corretas" --
    termos DIFERENTES, que não mudam.

REGRAS DE OURO:
1. Só proponha troca se o japonês DAQUELE ponto trouxer a chave.
2. Preserve a gramática: gênero, número, artigo, preposição contraída.
3. O trecho que você citar precisa existir LITERALMENTE no português dado.
4. Se houver mais de uma ocorrência igual no artigo, cite cada uma com
   palavras vizinhas suficientes para distingui-las.

FORMATO — uma linha por ocorrência, nada mais:

TROCA | <trecho português exato, 4 a 12 palavras> | <o mesmo trecho corrigido>

Se o artigo não precisar de nenhuma mudança:

NADA
"""


def alvos() -> list[dict]:
    """Só o artigo que de fato tem resíduo -- perífrase ou forma proibida."""
    saida = []
    for p in sorted(R.PT_FONTE.glob("*.txt")):
        obra = p.name
        ajp = R.artigos(R.JP_DIR / obra, "jp_anchor", obra)
        apt = R.artigos(p, "pt_anchor", obra)
        if not ajp or len(ajp) != len(apt):
            continue
        for i, (jp, pt) in enumerate(zip(ajp, apt)):
            residuo = (("御屏風観音" in jp and re.search(r"(?<!\()Kannon do biombo", pt))
                       or ("邪神" in jp and "deuses malignos" in pt))
            if residuo:
                saida.append({"obra": obra, "artigo": i,
                              "jp": jp[:14000], "pt": pt[:14000]})
    return saida


def julga(item: dict) -> dict:
    pedido = (f"ORIGEM: {item['obra']} (artigo {item['artigo']})\n\n"
              f"=== JAPONÊS ===\n{item['jp']}\n\n"
              f"=== PORTUGUÊS ===\n{item['pt']}")
    texto, tokens, tent = "", 0, 0
    while not texto.strip() and tent < 3:
        tent += 1
        extra = "\n\nIMPORTANTE: responda DIRETAMENTE no formato." if tent > 1 else ""
        r = ag._client().chat.completions.create(
            model=MODELO, max_tokens=16000,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": pedido + extra}])
        u = r.usage
        tokens += (u.prompt_tokens or 0) + (u.completion_tokens or 0)
        texto = r.choices[0].message.content or ""
    trocas = []
    for ln in texto.splitlines():
        if not ln.strip().upper().startswith("TROCA"):
            continue
        partes = [x.strip() for x in ln.split("|")]
        if (len(partes) >= 3 and partes[1] and partes[2]
                and partes[1] != partes[2] and partes[1] in item["pt"]):
            trocas.append({"de": partes[1], "para": partes[2]})
    return {"obra": item["obra"], "artigo": item["artigo"],
            "trocas": trocas, "tokens": tokens, "bruto": texto[:4000]}


def main() -> None:
    if "--aplicar" in sys.argv:
        R.DESTINO = DESTINO          # reaproveita a gravação já endurecida
        R.aplicar()
        return
    itens = alvos()
    feitos = []
    if DESTINO.exists():
        feitos = [r for r in json.loads(DESTINO.read_text(encoding="utf-8"))
                  if "erro" not in r]
        vistos = {(r["obra"], r["artigo"]) for r in feitos}
        itens = [i for i in itens if (i["obra"], i["artigo"]) not in vistos]
        print(f"retomando: {len(feitos)} lidos, {len(itens)} restantes", flush=True)
    print(f"{len(itens)} artigos a ler\n", flush=True)

    trava, n = threading.Lock(), [0]

    def trabalho(it):
        try:
            r = julga(it)
        except Exception as exc:
            r = {"obra": it["obra"], "artigo": it["artigo"],
                 "erro": repr(exc)[:140], "trocas": []}
        with trava:
            feitos.append(r)
            n[0] += 1
            if n[0] % 25 == 0:
                print(f"[{n[0]:>4}/{len(itens)}] {r['obra'][:30]:<32} "
                      f"{sum(len(x.get('trocas', [])) for x in feitos)} trocas acumuladas",
                      flush=True)
            DESTINO.write_text(json.dumps(feitos, ensure_ascii=False, indent=1),
                               encoding="utf-8")

    with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
        list(pool.map(trabalho, itens))
    tk = sum(r.get("tokens", 0) for r in feitos)
    tot = sum(len(r.get("trocas", [])) for r in feitos)
    err = sum(1 for r in feitos if "erro" in r)
    print(f"\n{len(feitos)} artigos lidos | {tot} trocas propostas | {err} erros | "
          f"{tk:,} tokens | ~US$ {tk / 1e6 * 0.0424:.3f}")


if __name__ == "__main__":
    main()
