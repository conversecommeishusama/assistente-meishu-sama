"""Etapa 4 — leitura de fidelidade artigo a artigo, japonês e português lado a lado.

As etapas 1 a 3 fecharam: a varredura determinística está em zero e as 698
entradas de glossário foram julgadas. O que sobra é o que nenhuma contagem
alcança — sentido invertido, omissão, número trocado, fala atribuída a quem
não falou, e o calque de marcador discursivo.

Duas lições do dia 2026-08-08 estão embutidas no desenho:

1. **Regex não decide sentido.** Duas regras da varredura (E5 e G1) foram
   afinadas por muitas rodadas e terminaram reclassificadas para MODELO porque
   o corpus não é uniforme o bastante para contagem. Aqui não há detecção
   automática: o modelo lê os dois textos.

2. **Separar o que se corrige do que se anota.** Erro de sentido se corrige;
   nuance de estilo vira anotação para o usuário ler durante a revisão. Aplicar
   milhares de ajustes de nuance empurraria o texto para o literalismo, contra
   o §3 do protocolo de tradução — e é justamente onde o julgamento de quem lê
   vale mais que o de qualquer modelo.

Nada é gravado por este script. Ele lê e propõe; a aplicação passa por
auditoria contra o japonês e por `scripts/aplica_no_artigo.py`, que exige o
trecho literal e escopo de artigo.

Uso:
    python3 scripts/leitura_fidelidade.py                 # lê e propõe
    python3 scripts/leitura_fidelidade.py --resumo        # o que já saiu
"""

from __future__ import annotations

import json
import re
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import reaplica_semantico as R  # noqa: E402
from goshinsho.services import agentic_search as ag  # noqa: E402

DESTINO = RAIZ / "reports/varredura_padronizacao/LEITURA_FIDELIDADE.json"
MODELO = "deepseek-v4-flash"
PARALELISMO = 8
# Medido em 2026-08-08 neste mesmo artigo (10.054 caracteres de português
# contra 3.962 de japonês):
#
#     teto  8.192 -> raciocínio 7.999, resposta VAZIA
#     teto 16.000 -> resposta VAZIA
#     teto 32.000 -> resposta VAZIA (116.542 tokens em 3 tentativas)
#     teto 65.536 -> raciocínio 43.770, finish=stop, resposta com 3 achados reais
#
# `reasoning_tokens` batendo exatamente no teto é a assinatura de "parou no
# meio", não de "não tinha o que dizer" -- e `finish=stop` no último caso
# confirma que ele terminou por conta própria. Era falta de espaço para
# raciocinar, não tarefa grande demais: a hipótese de fatiar o artigo estava
# errada e foi descartada (ver alvos()).
MAX_TOKENS = 65536

SYSTEM = """Você é revisor de tradução japonês→português do acervo de Meishu-Sama (Igreja Messiânica Mundial).

Recebe UM artigo em japonês e o MESMO artigo em português. Leia os dois frase a frase, do início ao fim, e relate o que estiver errado. Isto NÃO é revisão de terminologia — o glossário já foi conferido. É leitura de fidelidade e de português.

═══ O QUE PROCURAR ═══

GRAVE — muda o que o texto diz. Sempre proponha correção:
  · sentido invertido (afirmação virou negação, causa virou efeito)
  · sujeito trocado (quem faz a ação)
  · FALA ATRIBUÍDA A QUEM NÃO FALOU — pergunta do interlocutor apresentada
    como resposta de Meishu-Sama, ou o contrário. Confira os turnos.
  · omissão de trecho com conteúdo (frase, cláusula, item de lista)
  · acréscimo que o japonês não sustenta
  · número, data, idade ou ordem de grandeza errados. CUIDADO ESPECIAL:
    万 = 10.000 e 億 = 100.000.000 — 万分の一 é "um décimo-milésimo", não
    "um milionésimo"; 億 é "cem milhões", não "bilhão"
  · nome próprio trocado ou romanizado de forma irreconhecível

MÉDIO — o leitor entende outra coisa. Proponha correção:
  · nuance invertida (dúvida virou certeza, permissão virou ordem)
  · restrição perdida ("só nesse caso" desaparecendo)
  · concordância, regência ou pontuação que muda a leitura

LEVE — anote, NÃO corrija. Vai para a lista de leitura do usuário:
  · escolha de palavra defensável mas melhorável
  · repetição, cacofonia, ritmo
  · registro (formal demais, coloquial demais)

═══ CALQUE DE MARCADOR DISCURSIVO — classifique como MÉDIO ═══

O japonês encadeia 実は, 実に, 実際, 本当に, やはり, つまり, 結局, そこで,
なるほど a cada duas frases. Traduzidos um a um por reflexo, produzem português
empolado, e às vezes colidem com o substantivo ao lado:

  実は真理なんだから真理というものは…
  → "é, na verdade, a verdade. A verdade é…"   ← 実は é o marcador, 真理 é o
    substantivo; o português repetiu a mesma palavra e criou uma redundância
    que o original não tem

  実に…どうかしている。実際、本当の迷信ですね。
  → "Realmente… está estranha. Na verdade, é uma verdadeira superstição."
    ← três marcadores distintos achatados em três sinônimos em cadeia

Marcador discursivo traduz-se pelo que a frase pede em português — e muitas
vezes se OMITE. Proponha a forma natural.

MAS CUIDADO: quando a repetição é o argumento de Meishu-Sama, ela FICA. Em
真理のようなもんで実は真理じゃない ("é como a verdade, mas não é a verdade")
ele está explicando o termo 真如 — o jogo de palavras é o conteúdo.

═══ O QUE NÃO É ERRO ═══

· expansão: o português naturalmente ocupa 2 a 3 vezes o espaço do japonês
· reagrupamento de frase e de parágrafo, quando o conteúdo e a ordem se mantêm
· termo do glossário já fixado (Johrei, Ohikari, Meishu-Sama, Kannon-Sama,
  Paraíso Terrestre, norito, Divindades malignas, nuvens espirituais…)
· kanji visível quando o texto discute o próprio caractere
· «Caminho» (道) e «示» (shimesu): as duas ordens de glosa valem
· marcador de turno (Pergunta)/(Resposta Divina) nos volumes do 浄霊法講座 —
  ali o rótulo fecha o bloco anterior, por decisão registrada do usuário

═══ FORMATO — uma linha por achado, nada mais ═══

<GRAVE|MEDIO|LEVE> | <trecho português exato, 4 a 15 palavras> | <o trecho corrigido, ou "-" se for LEVE> | <o que está errado, em uma frase>

O trecho tem de existir LITERALMENTE no português dado — vou conferir. Se
houver ocorrências iguais no artigo, cite com palavras vizinhas suficientes
para distinguir. Se a tradução estiver correta, escreva apenas:

NADA
"""


def _fatia(texto: str, n: int) -> list[str]:
    """Divide em n pedaços aproximados, sempre em fronteira de parágrafo."""
    if n <= 1:
        return [texto]
    paras = re.split(r"(\n\s*\n+)", texto)
    blocos = ["".join(paras[i:i + 2]) for i in range(0, len(paras), 2)]
    alvo = len(texto) / n
    saida, atual = [], ""
    for b in blocos:
        if atual and len(atual) + len(b) > alvo and len(saida) < n - 1:
            saida.append(atual)
            atual = b
        else:
            atual += b
    if atual:
        saida.append(atual)
    while len(saida) < n:
        saida.append("")
    return saida[:n]


def alvos() -> list[dict]:
    saida = []
    for p in sorted(R.PT_FONTE.glob("*.txt")):
        obra = p.name
        ajp = R.artigos(R.JP_DIR / obra, "jp_anchor", obra)
        apt = R.artigos(p, "pt_anchor", obra)
        if not ajp or len(ajp) != len(apt):
            continue
        for i, (jp, pt) in enumerate(zip(ajp, apt)):
            if len(jp.strip()) < 60 or len(pt.strip()) < 60:
                continue                      # cabeçalho/fragmento, não há o que ler
            # NÃO fatiar: os dois lados têm estrutura de parágrafo diferente
            # e o corte independente desalinha. Medido -- num artigo de 3.962
            # caracteres o pedaço 0 do japonês saiu com 4 caracteres (só o
            # título) contra 2.268 do português. O artigo vai inteiro, e o que
            # resolveu a resposta vazia foi o orçamento de saída, não o corte.
            saida.append({"obra": obra, "artigo": i, "parte": 0,
                          "jp": jp[:16000], "pt": pt[:16000]})
    return saida


def julga(item: dict) -> dict:
    pedido = (f"ORIGEM: {item['obra']} (artigo {item['artigo']}, "
              f"parte {item.get('parte', 0) + 1})\n\n"
              f"=== JAPONÊS ===\n{item['jp']}\n\n"
              f"=== PORTUGUÊS ===\n{item['pt']}")
    texto, tokens, tent = "", 0, 0
    while not texto.strip() and tent < 3:
        tent += 1
        extra = "\n\nIMPORTANTE: responda DIRETAMENTE no formato." if tent > 1 else ""
        r = ag._client().chat.completions.create(
            model=MODELO, max_tokens=MAX_TOKENS,
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": pedido + extra}])
        u = r.usage
        tokens += (u.prompt_tokens or 0) + (u.completion_tokens or 0)
        texto = r.choices[0].message.content or ""

    achados = []
    for ln in texto.splitlines():
        partes = [x.strip() for x in ln.split("|")]
        if len(partes) < 4:
            continue
        grau = partes[0].strip().upper()
        if grau not in ("GRAVE", "MEDIO", "MÉDIO", "LEVE"):
            continue
        de, para, motivo = partes[1], partes[2], partes[3]
        # o trecho tem de existir LITERALMENTE -- a salvaguarda que impediu o
        # desastre de 07/08 de se repetir
        if not de or de not in item["pt"]:
            continue
        achados.append({"grau": "MEDIO" if grau == "MÉDIO" else grau,
                        "de": de, "para": para, "motivo": motivo})
    return {"obra": item["obra"], "artigo": item["artigo"],
            "parte": item.get("parte", 0), "achados": achados,
            "tokens": tokens, "bruto": texto[:4000]}


def resumo() -> None:
    d = json.loads(DESTINO.read_text(encoding="utf-8"))
    c = Counter(a["grau"] for r in d for a in r.get("achados", []))
    err = sum(1 for r in d if "erro" in r)
    tk = sum(r.get("tokens", 0) for r in d)
    print(f"{len(d)} artigos lidos | {sum(c.values())} achados | {err} erros de API")
    for k, v in c.most_common():
        print(f"  {k:<6} {v}")
    print(f"  {tk:,} tokens | ~US$ {tk / 1e6 * 0.0424:.3f}")
    piores = Counter(r["obra"] for r in d
                     for a in r.get("achados", []) if a["grau"] == "GRAVE")
    if piores:
        print("\nobras com mais achados GRAVE:")
        for o, n in piores.most_common(10):
            print(f"  {n:>4}  {o[:48]}")


def main() -> None:
    if "--resumo" in sys.argv:
        resumo()
        return
    itens = alvos()
    feitos = []
    if DESTINO.exists():
        feitos = [r for r in json.loads(DESTINO.read_text(encoding="utf-8"))
                  if "erro" not in r]
        vistos = {(r["obra"], r["artigo"], r.get("parte", 0)) for r in feitos}
        itens = [i for i in itens
                 if (i["obra"], i["artigo"], i.get("parte", 0)) not in vistos]
        print(f"retomando: {len(feitos)} lidos, {len(itens)} restantes", flush=True)
    print(f"{len(itens)} artigos a ler\n", flush=True)

    trava, n = threading.Lock(), [0]

    def trabalho(it):
        try:
            r = julga(it)
        except Exception as exc:
            r = {"obra": it["obra"], "artigo": it["artigo"],
                 "parte": it.get("parte", 0),
                 "erro": repr(exc)[:140], "achados": []}
        with trava:
            feitos.append(r)
            n[0] += 1
            if n[0] % 25 == 0:
                g = sum(1 for x in feitos for a in x.get("achados", [])
                        if a["grau"] == "GRAVE")
                print(f"[{n[0]:>4}/{len(itens)}] {r['obra'][:30]:<32} "
                      f"{sum(len(x.get('achados', [])) for x in feitos)} achados "
                      f"({g} graves)", flush=True)
            DESTINO.write_text(json.dumps(feitos, ensure_ascii=False, indent=1),
                               encoding="utf-8")

    with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
        list(pool.map(trabalho, itens))
    resumo()


if __name__ == "__main__":
    main()
