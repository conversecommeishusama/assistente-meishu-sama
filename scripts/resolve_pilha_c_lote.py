"""Resolve, de forma semântica e caso a caso, os 555 achados das decisões 12
e 13 (a maior parte da pilha C) -- pedido explícito do usuário em 2026-08-10,
depois de eu ter mostrado que rotular esses 555 como "duas decisões de
política" era enganoso: cada um é uma disputa factual específica sobre o
japonês, não uma convenção que se resolve de uma vez.

Nada aqui usa palavra-chave ou regra mecânica para decidir o mérito -- é
obrigação explícita do usuário que a leitura seja semântica em TODOS os
casos. O que É mecânico é só a orquestração (montar o dossiê, gravar,
verificar containment) -- o julgamento em si é sempre do modelo, lendo o
japonês.

Desenho: dois leitores independentes, cada um vendo o dossiê COMPLETO (o
japonês do artigo inteiro, a vizinhança em português, e as 3 opiniões
anteriores -- DS1, DS2, desafiador) e decidindo:

  RESOLVIDO        -- o texto final correto, com justificativa
  PRECISA_USUARIO  -- ambiguidade genuína, não decidir sozinho

Os dois só contam como resolvido se CONVERGIREM no mesmo sentido (mesmo
veredito E texto final semanticamente equivalente, julgado por um terceiro
passe comparador) -- divergência ou qualquer PRECISA_USUARIO vai para a
mesa do usuário. Isso não é o mesmo desenho do DS1/DS2 original (que liam
só a alegação, sem o contraditório) -- aqui os dois já veem as 3 leituras
anteriores, então convergirem é mais exigente: têm de concordar mesmo
depois de examinar onde os anteriores discordaram.

A escrita do texto final no corpus é sempre feita pelo DeepSeek (nunca por
mim digitando PT diretamente) e sempre passa pela mesma guarda de
containment já usada em aplicar_semantico.py antes de gravar.

    python3 scripts/resolve_pilha_c_lote.py              # roda os 2 leitores
    python3 scripts/resolve_pilha_c_lote.py --relatorio
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
import verifica_fidelidade as V  # noqa: E402
from goshinsho.services import agentic_search as ag  # noqa: E402

R = RAIZ / "reports/varredura_padronizacao"
DECISOES = json.loads((R / "DECISOES.json").read_text(encoding="utf-8"))
DEST1 = R / "RESOLVE_C_1.json"
DEST2 = R / "RESOLVE_C_2.json"
MODELO = "deepseek-v4-flash"
PARALELISMO = 16
# Teto medido no próprio projeto: leitura_fidelidade precisou de 65536 para não
# estourar o orçamento de raciocínio antes do texto útil sair -- aqui a tarefa é
# igualmente pesada (lê JP inteiro + 3 opiniões anteriores antes de responder).
# Com 4096 a resposta saiu vazia (raciocínio consumiu tudo, confirmado testando).
MAX_TOKENS = 32768
CONTEXTO = 900
# 40000, não 14000: com o teto antigo, 32 dos 555 casos foram julgados contra um
# japonês CORTADO -- e três deles responderam literalmente «o trecho não consta
# do artigo fornecido», que eu quase levei ao usuário como ambiguidade genuína.
# Não era: era truncamento meu. O maior artigo do lote tem 38.522 caracteres.
# Mesmo bug já registrado no projeto para a leitura de fidelidade.
MAX_JP = 40000

ALVO_DECISOES = {12, 13}   # as duas decisões que o usuário pediu para resolver

SYSTEM = """Você julga, lendo o japonês, qual é a forma final CORRETA de um
trecho de tradução -- não se a proposta de outra pessoa está certa, mas qual
é o texto certo, ponto final. Sua inclinação deve ser PRECISA_USUARIO: só
responda RESOLVIDO quando, depois de ler o japonês com cuidado, você tiver
certeza real, não uma leitura plausível entre outras.

CONTEXTO DO PROJETO

O acervo é de Meishu-Sama (Igreja Messiânica Mundial). A tradução é
deliberadamente livre (protocolo §3): reagrupa frases, expande o que o
japonês deixa implícito. "Poderia ser dito de outro jeito" não é motivo
para RESOLVIDO -- só decida quando o texto atual (ou a proposta em disputa)
afirma algo que o japonês não sustenta: sujeito trocado, sentido invertido,
conteúdo omitido ou inventado, número/data errados, atribuição de fala
errada, termo doutrinário trocado.

Regras de forma do protocolo, aplicam-se à sua resposta também:
  · nunca usar kanji/kana no português, salvo entre aspas com romaji entre
    parênteses (exceção só quando o próprio trecho japonês está sendo
    explicado como objeto, não usado como vocabulário)
  · termo com forma fixa no glossário do projeto (fornecido abaixo, quando
    houver) sempre vence sinônimo -- nunca proponha variante para um termo
    já glossariado
  · não acrescente nem remova conteúdo que a correção não pede
  · se o trecho for âncora de segmentação (avisado abaixo, quando for o
    caso), a resposta ainda pode alterar o texto -- a atualização da spec é
    feita depois por outro passo; não recuse por causa disso

VOCÊ RECEBE

O japonês do artigo inteiro, o português ao redor do trecho, a proposta de
correção original, e as leituras de até três auditores anteriores
(incluindo, quando existir, um desafiador que tentou derrubar o consenso
dos dois primeiros). Eles podem estar certos, errados, ou cada um certo em
parte -- não presuma que o mais recente tem razão. Releia o japonês você
mesmo antes de decidir; não vote na leitura mais convincente sem verificar.

RESPONDA UMA ÚNICA LINHA:

RESOLVIDO | <o trecho final correto em português, pronto para substituir o
             trecho atual dentro do parágrafo> | <por que, citando o
             japonês que sustenta>
PRECISA_USUARIO | <o que exatamente está em aberto e por quê>
"""

COMPARA_SYSTEM = """Você recebe dois textos finais propostos, independentemente,
para o mesmo trecho de tradução. Diga se eles resolvem a disputa da MESMA
forma -- mesmo sentido, mesmo conteúdo -- ainda que com palavras diferentes.
Pequena diferença de estilo que não muda o sentido conta como concordância.

Responda uma única linha:
CONCORDAM | <em uma frase, o que os dois preservam em comum>
DIVERGEM | <em uma frase, no que exatamente diferem>
"""


def casos_alvo() -> list[dict]:
    proc = {A.chave(r): r for r in A.procedentes()}
    d1, d2, ds = T._le(T.DS1), T._le(T.DS2), T._le(T.DES)
    pilha_c = set(T.pilhas()["C"])
    out = []
    for k, at in DECISOES["atribuicoes"].items():
        if at.get("decisao") not in ALVO_DECISOES or k not in pilha_c or k not in proc:
            continue
        it = proc[k]
        notas = {"ds1": f"[{d1[k]['veredito']}] {d1[k]['nota']}",
                 "ds2": f"[{d2[k]['veredito']}] {d2[k]['nota']}",
                 "desafiador": ""}
        if k in ds and "erro" not in ds[k]:
            m = "DERRUBOU" if ds[k]["derruba"] else "sustentou"
            notas["desafiador"] = f"[{m}] {ds[k]['razao']}"
        out.append({"chave": k, "obra": it["obra"], "artigo": it["artigo"],
                    "grau": it.get("grau", ""), "de": it["de"], "para": it["para"],
                    "motivo": it.get("motivo", ""), "notas": notas,
                    "decisao_original": at["decisao"]})
    return out


def dossie(c: dict) -> str:
    jp, pt = V.textos(c["obra"], c["artigo"])
    p = pt.find(c["de"])
    viz = (pt[max(0, p - CONTEXTO):p + len(c["de"]) + CONTEXTO]
           if p >= 0 else c["de"])
    aviso = "" if p >= 0 else "\n*** o trecho não foi localizado literalmente no PT atual (pode já ter mudado) ***\n"

    sp = RAIZ / f"reports/livros_trabalho/segmentacao_manual/{c['obra']}.json"
    if sp.exists():
        arts = json.loads(sp.read_text(encoding="utf-8")).get("articles", [])
        for a in arts:
            anc = a.get("pt_anchor", "")
            if anc and (c["de"] in anc or anc[:40] in c["de"]):
                aviso += "\n*** trecho É âncora de segmentação — pode alterar, a spec é sincronizada depois ***\n"
                break

    glos = V.glossario_do_trecho(c["de"], viz, c["para"] + c["motivo"])
    return (f"OBRA: {c['obra']}  artigo {c['artigo']}  grau {c['grau']}\n{aviso}{glos}"
            f"\n=== JAPONÊS (artigo inteiro) ===\n{jp[:MAX_JP]}\n"
            f"\n=== PORTUGUÊS (vizinhança do trecho) ===\n{viz}\n"
            f"\n=== PROPOSTA ORIGINAL ===\ntrecho atual: {c['de']}\n"
            f"proposta:     {c['para']}\nalegação:     {c['motivo']}\n"
            f"\n=== LEITURA DS1 === {c['notas']['ds1']}"
            f"\n=== LEITURA DS2 === {c['notas']['ds2']}"
            + (f"\n=== DESAFIADOR === {c['notas']['desafiador']}" if c['notas']['desafiador'] else ""))


def le(c: dict) -> dict:
    d = dossie(c)
    r = ag._client().chat.completions.create(
        model=MODELO, max_tokens=MAX_TOKENS,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": d + "\n\nQual é a forma final correta?"}])
    texto = (r.choices[0].message.content or "").strip()
    primeira = next((l for l in texto.splitlines() if l.strip()), "")
    p = [x.strip() for x in primeira.split("|")]
    resolvido = p and p[0].upper().startswith("RESOLVIDO")
    return {**c, "resolvido": resolvido,
            "texto_final": p[1] if resolvido and len(p) > 1 else "",
            "razao": p[-1] if len(p) > 1 else primeira}


def roda(dest: Path) -> None:
    feitos: dict[str, dict] = json.loads(dest.read_text(encoding="utf-8")) if dest.exists() else {}
    cs = [c for c in casos_alvo() if c["chave"] not in feitos]
    print(f"{dest.name}: {len(cs)} a fazer ({len(feitos)} já feitos)", flush=True)
    trava, n = threading.Lock(), [0]

    def trabalho(c):
        try:
            r = le(c)
        except Exception as exc:
            r = {**c, "erro": repr(exc)[:140]}
        with trava:
            feitos[c["chave"]] = r
            n[0] += 1
            if n[0] % 25 == 0:
                dest.write_text(json.dumps(feitos, ensure_ascii=False, indent=1), encoding="utf-8")
                res = sum(1 for x in feitos.values() if x.get("resolvido"))
                print(f"  [{n[0]}/{len(cs)}] {res} resolvidos até aqui", flush=True)

    if cs:
        with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
            list(pool.map(trabalho, cs))
    dest.write_text(json.dumps(feitos, ensure_ascii=False, indent=1), encoding="utf-8")


def relatorio() -> None:
    if not (DEST1.exists() and DEST2.exists()):
        print("faltam rodadas")
        return
    d1 = json.loads(DEST1.read_text(encoding="utf-8"))
    d2 = json.loads(DEST2.read_text(encoding="utf-8"))
    comuns = set(d1) & set(d2)
    ambos_resolvido = [k for k in comuns if d1[k].get("resolvido") and d2[k].get("resolvido")]
    print(f"{len(comuns)} casos com as 2 leituras\n")
    print(f"  {sum(1 for k in comuns if d1[k].get('resolvido'))} resolvido na leitura 1")
    print(f"  {sum(1 for k in comuns if d2[k].get('resolvido'))} resolvido na leitura 2")
    print(f"  {len(ambos_resolvido)} resolvido nas DUAS -- candidatos a comparação/aplicação")
    print(f"  {sum(1 for k in comuns if not d1[k].get('resolvido') and not d2[k].get('resolvido'))} PRECISA_USUARIO nas duas")


def main() -> None:
    if "--relatorio" in sys.argv:
        relatorio()
        return
    roda(DEST1)
    roda(DEST2)
    relatorio()


if __name__ == "__main__":
    main()
