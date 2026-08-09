"""Testa se o DeepSeek faz a minha auditoria — cego aos meus vereditos.

Pergunta do usuário: um agente DeepSeek faria esse trabalho melhor, comigo só
acompanhando? A resposta honesta é medir, não opinar.

Desenho: os mesmos achados que já auditei, com EXATAMENTE o contexto que eu
tive na mão quando decidi -- o japonês do artigo inteiro, o português em volta
do trecho, as entradas de glossário que tocam a passagem, o aviso quando o
trecho faz parte da âncora de segmentação, e a contagem no acervo das duas
formas (o que me fez derrubar «Uzu» e a correção de «Izunome»). Sem isso o
teste mediria falta de contexto, não capacidade.

Amostra estratificada de propósito: TODOS os que eu não aprovei (é onde a
divergência importa) mais uma fatia aleatória dos aprovados. A concordância
global e a concordância nos casos difíceis são reportadas em separado --
juntá-las esconderia justamente o que se quer saber.
"""

from __future__ import annotations

import json
import random
import re
import sys
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import verifica_fidelidade as V  # noqa: E402
import auditoria as A  # noqa: E402
from goshinsho.services import agentic_search as ag  # noqa: E402

DESTINO = RAIZ / "reports/varredura_padronizacao/TESTE_AUDITOR.json"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"
PT_FONTE = RAIZ / "livros_publicacao_pt_revisado"
MODELO = "deepseek-v4-flash"
MAX_TOKENS = 32768
PARALELISMO = 4
N_APROVADOS = 40
SEMENTE = 20260809

SYSTEM = """Você audita correções propostas a uma tradução do japonês para o
português, do acervo de Meishu-Sama (Igreja Messiânica Mundial). Leia o
japonês e o português LINHA A LINHA e decida.

Três vereditos, e só três:

APROVADO — o erro é real e a correção proposta está certa no sentido E na
forma (respeita o glossário, a romanização usada no acervo, e o protocolo).

RECUSADO — não há erro, ou a correção proposta está errada. Inclui o caso em
que o português atual já é aceitável e a proposta apenas troca por outra forma
igualmente válida.

REFORMAR — o erro é real, mas a correção proposta não serve como está: viola o
glossário, usa romanização que não é a do acervo, exige mover um turno inteiro
de diálogo, ou mexeria numa âncora de segmentação.

O QUE TEM DE FAZER VOCÊ RECUSAR:

· o japonês não sustentar a alegação
· a proposta ir contra o glossário do projeto (as decisões estão dadas abaixo
  quando existem; propor mudá-las nunca procede)
· a proposta usar uma forma que o acervo não usa, quando a contagem mostrar
  que existe forma dominante
· a tradução ser livre — este projeto traduz livremente por determinação, e
  «o japonês não diz exatamente isso» não é erro

O QUE TEM DE FAZER VOCÊ MARCAR REFORMAR EM VEZ DE APROVAR:

· o trecho fizer parte da ÂNCORA DE SEGMENTAÇÃO (será avisado): mudar o texto
  quebra a busca do site, e a correção teria de vir junto com a spec
· a correção exigir mover fala de um turno para outro (Interlocutor ↔
  Meishu-Sama): o mecanismo de aplicação troca trecho literal, não move turnos
· a correção enfiar kanji ou kana cru no português fora da exceção do
  protocolo (kanji só entre aspas com romaji entre parênteses)
· o sentido estar certo mas a forma proposta ser errada — nome próprio com
  romanização que o acervo não usa, concordância quebrada, termo fora do
  glossário

Responda UMA linha, nada mais:

<APROVADO|RECUSADO|REFORMAR> | <justificativa em uma frase, citando o japonês>
"""


def contexto_ancora(obra: str, trecho: str) -> str:
    sp = SPEC_DIR / f"{obra}.json"
    if not sp.exists():
        return ""
    arts = json.loads(sp.read_text(encoding="utf-8")).get("articles", [])
    for i, a in enumerate(arts):
        anc = a.get("pt_anchor", "")
        if anc and (trecho in anc or anc[:40] in trecho):
            return (f"\n*** ATENÇÃO: este trecho faz parte da ÂNCORA DE "
                    f"SEGMENTAÇÃO do artigo {i} desta obra. ***\n")
    return ""


def contagem_acervo(de: str, para: str) -> str:
    """Frequência das formas concorrentes -- foi o que derrubou «Uzu»."""
    def chave(s: str) -> str:
        # o termo distintivo: a palavra mais longa que difere entre as duas
        pd, pp = set(re.findall(r"[A-Za-zÀ-ÿ]{4,}", s)), set(re.findall(r"[A-Za-zÀ-ÿ]{4,}", para if s == de else de))
        dif = sorted(pd - pp, key=len, reverse=True)
        return dif[0] if dif else ""
    ka, kb = chave(de), chave(para)
    if not (ka and kb):
        return ""
    n = {}
    for k in (ka, kb):
        c = 0
        for p in PT_FONTE.glob("*.txt"):
            c += len(re.findall(rf"\b{re.escape(k)}\b", p.read_text(encoding="utf-8"), re.I))
        n[k] = c
    return (f"\nNO ACERVO INTEIRO: «{ka}» aparece {n[ka]}x · "
            f"«{kb}» aparece {n[kb]}x\n")


def julga(it: dict) -> dict:
    jp, pt = V.textos(it["obra"], it["artigo"])
    p = pt.find(it["de"])
    viz = pt[max(0, p - 900):p + len(it["de"]) + 900] if p >= 0 else it["de"]
    glos = V.glossario_do_trecho(it.get("jp_apoio", "") + it["de"], viz,
                                 it["para"] + it["motivo"])
    pedido = (
        f"{glos}{contagem_acervo(it['de'], it['para'])}"
        f"{contexto_ancora(it['obra'], it['de'])}"
        f"\n=== JAPONÊS (artigo inteiro) ===\n{jp[:14000]}\n"
        f"\n=== PORTUGUÊS (em volta do trecho) ===\n{viz}\n"
        f"\n=== CORREÇÃO PROPOSTA ===\n"
        f"trecho atual: {it['de']}\n"
        f"viraria:      {it['para']}\n"
        f"alegação:     {it['motivo']}\n\n"
        f"Seu veredito?")
    r = ag._client().chat.completions.create(
        model=MODELO, max_tokens=MAX_TOKENS,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": pedido}])
    txt = (r.choices[0].message.content or "").strip()
    prim = next((l for l in txt.splitlines() if l.strip()), "")
    ver = prim.split("|")[0].strip().upper().strip("<>")
    ver = {"APROVADO": "aprovado", "RECUSADO": "recusado",
           "REFORMAR": "reformar"}.get(ver, "?")
    u = r.usage
    return {"chave": A.chave(it), "deepseek": ver,
            "razao": prim.split("|", 1)[1].strip() if "|" in prim else prim,
            "tokens": (u.prompt_tokens or 0) + (u.completion_tokens or 0)}


def main() -> None:
    meus = A.carrega()
    proc = {A.chave(r): r for r in A.procedentes()}
    dificeis = [k for k, v in meus.items()
                if v["veredito"] != "aprovado" and k in proc]
    faceis = [k for k, v in meus.items()
              if v["veredito"] == "aprovado" and k in proc]
    amostra = dificeis + random.Random(SEMENTE).sample(
        faceis, min(N_APROVADOS, len(faceis)))
    itens = [proc[k] for k in amostra]
    print(f"{len(itens)} achados: {len(dificeis)} que eu NÃO aprovei "
          f"+ {len(itens) - len(dificeis)} aprovados\n", flush=True)

    feitos, trava, n = [], threading.Lock(), [0]

    def trabalho(it):
        try:
            r = julga(it)
        except Exception as exc:
            r = {"chave": A.chave(it), "deepseek": "erro", "razao": repr(exc)[:120]}
        with trava:
            feitos.append(r)
            n[0] += 1
            if n[0] % 10 == 0:
                print(f"  [{n[0]}/{len(itens)}]", flush=True)

    with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
        list(pool.map(trabalho, itens))

    for r in feitos:
        r["meu"] = meus[r["chave"]]["veredito"]
        r["minha_nota"] = meus[r["chave"]]["nota"]
    DESTINO.write_text(json.dumps(feitos, ensure_ascii=False, indent=1),
                       encoding="utf-8")

    ok = [r for r in feitos if r["deepseek"] != "erro"]
    dif = [r for r in ok if r["meu"] != "aprovado"]
    fac = [r for r in ok if r["meu"] == "aprovado"]
    def conc(g): return sum(1 for r in g if r["meu"] == r["deepseek"])
    print(f"\nCONCORDÂNCIA GLOBAL   {conc(ok)}/{len(ok)} = {conc(ok)/max(1,len(ok)):.0%}")
    print(f"  nos que eu aprovei   {conc(fac)}/{len(fac)} = {conc(fac)/max(1,len(fac)):.0%}")
    print(f"  nos DIFÍCEIS         {conc(dif)}/{len(dif)} = {conc(dif)/max(1,len(dif)):.0%}")
    print(f"\nmatriz (meu -> dele): {Counter((r['meu'], r['deepseek']) for r in ok).most_common()}")
    tk = sum(r.get("tokens", 0) for r in ok)
    print(f"custo US${tk/1e6*0.242:.4f} para {len(ok)} julgamentos "
          f"(US${tk/1e6*0.242/max(1,len(ok)):.5f} cada)")


if __name__ == "__main__":
    main()
