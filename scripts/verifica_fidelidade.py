"""Verificação adversarial dos achados da etapa 4.

O leitor (`leitura_fidelidade.py`) tem incentivo a achar: recebe dois textos e
a pergunta "o que está errado". Aqui o incentivo é o oposto -- cada achado
chega a um leitor novo, sem saber quem o escreveu, com a tarefa de DERRUBÁ-LO
contra o japonês. Na dúvida, cai.

Por que isso importa neste corpus: a tradução é livre por determinação do
protocolo (§3), então "o japonês não diz exatamente isso" é verdade em quase
toda frase e não é erro. O que sobrevive tem de ser sentido trocado, não
escolha de palavra.

Só GRAVE e MEDIO passam por aqui. LEVE nunca é aplicado -- vira anotação para
a leitura do usuário -- e não vale o custo de verificar.

O japonês vai INTEIRO (é ~40% do tamanho do português neste corpus, cabe), e o
português vai só na vizinhança do trecho: o verificador precisa do contexto
para julgar o sujeito de uma frase, não do artigo todo.

Uso:
    python3 scripts/verifica_fidelidade.py            # verifica
    python3 scripts/verifica_fidelidade.py --resumo
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

import leitura_fidelidade as L  # noqa: E402
from goshinsho.services import agentic_search as ag  # noqa: E402

ORIGEM = RAIZ / "reports/varredura_padronizacao/LEITURA_FIDELIDADE.json"
DESTINO = RAIZ / "reports/varredura_padronizacao/VERIFICACAO_FIDELIDADE.json"
MODELO = "deepseek-v4-flash"
PARALELISMO = 5   # baixo: a leitura roda em paralelo com 12
MAX_TOKENS = 16384          # aqui a resposta é curta; o teto alto era do leitor
CONTEXTO = 700              # caracteres de português de cada lado do trecho
MAX_JP = 12000

SYSTEM = """Você julga se uma correção proposta a uma tradução do japonês para
o português é PROCEDENTE. Sua inclinação é derrubá-la.

O acervo é de Meishu-Sama (Igreja Messiânica Mundial). A tradução é
DELIBERADAMENTE LIVRE, por determinação do protocolo do projeto: reagrupa
frases, expande o que em japonês fica implícito, e ocupa 2 a 3 vezes o espaço
do original. Portanto "o japonês não diz exatamente isso" NÃO é motivo para
proceder — quase toda frase do acervo cabe nessa descrição.

PROCEDE apenas se o português afirma algo que o japonês não sustenta:

· sujeito ou objeto trocado — quem faz vira quem sofre
· sentido invertido — afirma onde nega, expele onde atrai, sobe onde desce
· número, data, idade ou unidade diferente do original
· fala atribuída a quem não falou
· conteúdo que existe no japonês e sumiu, ou que aparece sem estar lá
· nome próprio ou termo doutrinário trocado por outro de sentido diferente

NÃO PROCEDE:

· sinônimo, registro, fluência, ordem das palavras, tamanho da frase
· nuance que o português deixou implícita ou explicitou
· o japonês ser mais vago ou mais específico que o português
· termo já fixado no glossário do projeto — Johrei, Ohikari, Meishu-Sama,
  Kannon-Sama, Paraíso Terrestre, norito, Divindades malignas, nuvens
  espirituais, Byōbu Kannon (sem artigo), destino predeterminado/mutável
· 教修 → «curso (aula) de preparação para receber o Ohikari (kyoshu)»: o
  «(kyoshu)» fecha a expressão toda e não qualifica «Ohikari»
· a linha de citação da fonte («Eikō nº 167, publicado em…») é metadado do
  projeto, não tradução: não existe no japonês e isso nunca é erro
· marcador (Pergunta)/(Resposta Divina) nos volumes do 浄霊法講座
· a correção proposta ser apenas OUTRA forma igualmente válida de dizer

Se você não localizar no japonês a passagem correspondente, NÃO PROCEDE — a
ausência de prova é motivo para derrubar, nunca para confirmar.

Responda em uma única linha:

PROCEDE | <a frase japonesa que sustenta, copiada> | <por quê, em uma frase>
NAO | <por quê, em uma frase>
"""


def pendentes() -> list[dict]:
    lidos = [r for r in json.loads(ORIGEM.read_text(encoding="utf-8"))
             if "erro" not in r]
    itens = []
    for r in lidos:
        for k, a in enumerate(r.get("achados", [])):
            if a["grau"] == "LEVE":
                continue
            itens.append({"obra": r["obra"], "artigo": r["artigo"],
                          "parte": r.get("parte", 0), "i": k, **a})
    return itens


# O português precisa ser remontado: `L.alvos()` devolve o artigo longo em
# pedaços, e o trecho citado pode estar em qualquer um deles. Guardar só o
# primeiro faria a busca do contexto falhar em todo artigo fatiado.
_cache: dict[tuple[str, int], tuple[str, str]] = {}
_trava_cache = threading.Lock()


def textos(obra: str, artigo: int) -> tuple[str, str]:
    with _trava_cache:
        if not _cache:
            junta: dict[tuple[str, int], list] = {}
            for x in L.alvos():
                junta.setdefault((x["obra"], x["artigo"]), []).append(x)
            for k, v in junta.items():
                v.sort(key=lambda y: y.get("parte", 0))
                _cache[k] = (v[0]["jp"], "".join(y["pt"] for y in v))
    return _cache.get((obra, artigo), ("", ""))


# Listar termos à mão no prompt nunca cobriria as 703 entradas: um achado
# procedente chegou a propor reverter `日月地大神 -> Miroku Ōkami`, decisão
# registrada do usuário que o corpus já aplica em 21 lugares. Aqui as entradas
# que de fato aparecem no trecho entram no pedido, vindas do arquivo.
_glos: dict[str, str] = {}


def glossario_do_trecho(jp: str, pt: str, alegacao: str) -> str:
    global _glos
    if not _glos:
        _glos = json.loads((RAIZ / "glossario_traducao.json").read_text(
            encoding="utf-8"))
    campo = jp + pt + alegacao
    achou = []
    for k, v in _glos.items():
        if not isinstance(v, str) or len(k) < 2:
            continue
        if k in campo or (len(v) > 4 and v.lower() in campo.lower()):
            achou.append(f"  {k} -> {v}")
    if not achou:
        return ""
    return ("\n=== GLOSSÁRIO DO PROJETO (decisões já tomadas; propor mudá-las "
            "NUNCA procede) ===\n" + "\n".join(achou[:25]) + "\n")


def julga(it: dict) -> dict:
    jp, pt = textos(it["obra"], it["artigo"])
    p = pt.find(it["de"])
    trecho = (pt[max(0, p - CONTEXTO):p + len(it["de"]) + CONTEXTO]
              if p >= 0 else it["de"])

    glos = glossario_do_trecho(it.get("jp_apoio", "") + it["de"], trecho,
                               it["para"] + it["motivo"])
    pedido = (
        f"{glos}\n=== JAPONÊS (artigo inteiro) ===\n{jp[:MAX_JP]}\n\n"
        f"=== PORTUGUÊS (vizinhança do trecho) ===\n{trecho}\n\n"
        f"=== CORREÇÃO PROPOSTA ===\n"
        f"trecho:    {it['de']}\n"
        f"viraria:   {it['para']}\n"
        f"alegação:  {it['motivo']}\n\n"
        f"A alegação procede?")

    r = ag._client().chat.completions.create(
        model=MODELO, max_tokens=MAX_TOKENS,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": pedido}])
    texto = (r.choices[0].message.content or "").strip()
    u = r.usage

    primeira = next((l for l in texto.splitlines() if l.strip()), "")
    partes = [x.strip() for x in primeira.split("|")]
    procede = partes[0].upper().startswith("PROCEDE")
    return {**it,
            "procede": procede,
            "jp_apoio": partes[1] if procede and len(partes) > 1 else "",
            "razao": partes[-1] if len(partes) > 1 else primeira,
            "tokens": (u.prompt_tokens or 0) + (u.completion_tokens or 0)}


def resumo() -> None:
    d = json.loads(DESTINO.read_text(encoding="utf-8"))
    ok = [r for r in d if "erro" not in r]
    c = Counter((r["grau"], r["procede"]) for r in ok)
    tk = sum(r.get("tokens", 0) for r in ok)
    print(f"{len(ok):,} achados verificados ({len(d) - len(ok)} erros)")
    for grau in ("GRAVE", "MEDIO"):
        s, n = c[(grau, True)], c[(grau, False)]
        if s + n:
            print(f"  {grau:<6} {s:>4} procedem, {n:>4} derrubados "
                  f"({s / (s + n):.0%} sobrevivem)")
    print(f"  {tk / 1e6:.1f} M tokens ~ US${tk / 1e6 * 0.242:.2f}")


def main() -> None:
    if "--resumo" in sys.argv:
        resumo()
        return
    itens = pendentes()
    feitos = []
    if DESTINO.exists():
        feitos = [r for r in json.loads(DESTINO.read_text(encoding="utf-8"))
                  if "erro" not in r]
        vistos = {(r["obra"], r["artigo"], r["parte"], r["i"]) for r in feitos}
        itens = [x for x in itens
                 if (x["obra"], x["artigo"], x["parte"], x["i"]) not in vistos]
    print(f"{len(itens):,} achados a verificar\n", flush=True)

    trava, n = threading.Lock(), [0]

    def trabalho(it):
        try:
            r = julga(it)
        except Exception as exc:
            r = {**it, "erro": repr(exc)[:140], "procede": False}
        with trava:
            feitos.append(r)
            n[0] += 1
            viv = sum(1 for x in feitos if x.get("procede"))
            if n[0] % 10 == 0 or n[0] == len(itens):
                print(f"[{n[0]:>5}/{len(itens)}] {viv} procedem "
                      f"({viv / n[0]:.0%})", flush=True)
                DESTINO.write_text(json.dumps(feitos, ensure_ascii=False, indent=1),
                                   encoding="utf-8")

    with ThreadPoolExecutor(max_workers=PARALELISMO) as pool:
        list(pool.map(trabalho, itens))
    DESTINO.write_text(json.dumps(feitos, ensure_ascii=False, indent=1),
                       encoding="utf-8")
    resumo()


if __name__ == "__main__":
    main()
