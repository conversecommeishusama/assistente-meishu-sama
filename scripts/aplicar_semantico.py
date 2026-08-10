"""Aplica as correções aprovadas — o modelo escreve, o script contém.

O usuário observou, em 2026-08-10, que a emenda deve ser semântica. Está certo,
e a razão é o histórico: substituição mecânica deixa a costura quebrada.
Trocar «proteção divina» por «Ohikari» produz «a Ohikari»; trocar «orações» por
«norito» produz «as norito xintoístas». Foi parte do estrago de 07/08, e não se
resolve com regex — concordância se lê, não se detecta por padrão.

Mas deixar um modelo escrever livremente no corpus é o outro extremo, e foi
justamente o que a guarda mecânica passou a impedir. Então a divisão é:

    localizar artigo e trecho   -> script (posição, sem julgamento)
    reescrever o PARÁGRAFO      -> DeepSeek, lendo o japonês e o contexto
    verificar o que mudou       -> script
    gravar e revalidar âncora   -> script, revertendo se quebrar

A verificação é o que torna seguro deixar o modelo escrever: o parágrafo devolvido
é comparado com o original, e só é aceito se a diferença estiver contida na região
da correção -- prefixo e sufixo idênticos, crescimento limitado. O modelo tem
liberdade de redação dentro do parágrafo e nenhuma fora dele.

    python3 scripts/aplicar_semantico.py             # diagnóstico
    python3 scripts/aplicar_semantico.py --aplicar
"""

from __future__ import annotations

import json
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import auditoria as A  # noqa: E402
import triagem as T  # noqa: E402
from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402
from aplica_no_artigo import janelas  # noqa: E402
from goshinsho.services import agentic_search as ag  # noqa: E402

PT_FONTE = RAIZ / "livros_publicacao_pt_revisado"
PT_STAGING = RAIZ / "reports/livros_trabalho/pt"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"
REGISTRO = RAIZ / "reports/varredura_padronizacao/APLICADO.json"
MODELO = "deepseek-v4-flash"
CRESCIMENTO_MAX = 1.6      # o parágrafo não pode inchar além disto

SYSTEM = """Você aplica uma correção já aprovada a um parágrafo de tradução do
japonês para o português, do acervo de Meishu-Sama.

A decisão de corrigir já foi tomada por três auditores. Você não a rediscute:
seu trabalho é fazer a emenda caber no português, com a frase inteira
funcionando.

O QUE FAZER

Reescreva o parágrafo com a correção aplicada, ajustando o que a troca exigir:
concordância de gênero e número, artigo, preposição, ordem das palavras. Se a
correção troca «proteção divina» por «Ohikari», o artigo antes dela muda de «a»
para «o». Se troca singular por plural, o verbo acompanha.

O QUE NÃO FAZER

Não melhore o resto do parágrafo. Não reorganize frases que a correção não
toca. Não acrescente nem remova conteúdo. Tudo que estiver fora da região da
correção tem de sair EXATAMENTE como entrou, caractere por caractere — o
parágrafo devolvido é comparado com o original e recusado se você mexer noutro
lugar.

Não use kanji nem kana no português, salvo entre aspas com romaji entre
parênteses. Preserve as citações de fonte entre colchetes, as marcações de
turno (`Interlocutor:`, `Meishu-Sama:`) e a numeração de poema ou item.

Devolva SÓ o parágrafo corrigido, sem comentário, sem aspas em volta, sem
cabeçalho.
"""


def paragrafo(texto: str, ini: int, fim: int, trecho: str) -> tuple[int, int] | None:
    """Limites do parágrafo que contém o trecho, dentro da janela do artigo."""
    p = texto.find(trecho, ini, fim)
    if p < 0:
        return None
    a = texto.rfind("\n\n", ini, p)
    a = ini if a < 0 else a + 2
    b = texto.find("\n\n", p + len(trecho))
    b = fim if b < 0 or b > fim else b
    return a, b


def contido(velho: str, novo: str, trecho: str, para: str) -> str | None:
    """Aceita só se a mudança estiver contida na região da correção."""
    if not novo.strip():
        return "resposta vazia"
    if len(novo) > len(velho) * CRESCIMENTO_MAX:
        return f"parágrafo inchou {len(novo)/len(velho):.1f}x"
    if trecho in novo:
        return "a correção não foi aplicada — o trecho antigo continua lá"
    # prefixo e sufixo comuns: o que sobra é a região que mudou
    i = 0
    while i < min(len(velho), len(novo)) and velho[i] == novo[i]:
        i += 1
    j = 0
    while (j < min(len(velho), len(novo)) - i
           and velho[len(velho) - 1 - j] == novo[len(novo) - 1 - j]):
        j += 1
    reg_velha, reg_nova = velho[i:len(velho) - j], novo[i:len(novo) - j]
    # A região que mudou tem de estar DENTRO do vão onde o trecho estava, com
    # margem para o ajuste em volta (artigo, preposição, concordância).
    #
    # A primeira versão exigia o contrário -- que a região contivesse o trecho
    # inteiro -- e rejeitava 85% das emendas corretas: em «Kannon-Sama-Sama» ->
    # «Kannon-Sama» a diferença mínima é só «-Sama», porque prefixo e sufixo
    # comuns consomem o resto. O teste estava invertido, não o modelo errado.
    MARGEM = 60
    p_ini = velho.find(trecho)
    p_fim = p_ini + len(trecho)
    if p_ini < 0:
        return "trecho não encontrado no parágrafo original"
    if i < p_ini - MARGEM or (len(velho) - j) > p_fim + MARGEM:
        return (f"mudou fora do vão do trecho: {velho[i:len(velho)-j][:70]!r} "
                f"-> {reg_nova[:70]!r}")
    if len(reg_nova) > len(reg_velha) * 3 + 120:
        return "a região corrigida cresceu demais"
    return None


def emenda(jp: str, par: str, de: str, para: str) -> str:
    r = ag._client().chat.completions.create(
        model=MODELO, max_tokens=8192,
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content":
                   f"=== JAPONÊS DO ARTIGO ===\n{jp[:9000]}\n\n"
                   f"=== PARÁGRAFO ATUAL ===\n{par}\n\n"
                   f"=== CORREÇÃO APROVADA ===\n"
                   f"o trecho: {de}\n"
                   f"deve virar: {para}\n\n"
                   f"Devolva o parágrafo corrigido."}])
    return (r.choices[0].message.content or "").strip()


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    d1 = T._le(T.DS1)
    proc = {A.chave(r): r for r in A.procedentes()}
    feitos = set(json.loads(REGISTRO.read_text(encoding="utf-8"))
                 if REGISTRO.exists() else [])
    por_obra: dict[str, list[dict]] = {}
    for k in T.pilhas()["A"]:
        if k in feitos or d1[k]["veredito"] != "aprovado" or k not in proc:
            continue
        it = proc[k]
        por_obra.setdefault(it["obra"], []).append(
            {"chave": k, "artigo": it["artigo"], "de": it["de"], "para": it["para"]})

    tot = sum(len(v) for v in por_obra.values())
    print(f"{tot} correções aprovadas, em {len(por_obra)} obras\n", flush=True)
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    aplicadas, recusadas = [], []

    # As chamadas de API são independentes entre si, inclusive entre obras:
    # calcula TODAS em paralelo. Paralelizar só dentro da obra desperdiçava a
    # banda, porque a maioria tem poucas correções.
    pedidos, textos, jp_por_obra = [], {}, {}
    for obra, itens in sorted(por_obra.items()):
        f = PT_FONTE / obra
        if not f.exists():
            continue
        textos[obra] = f.read_text(encoding="utf-8")
        try:
            spj = json.loads((SPEC_DIR / f"{obra}.json").read_text(encoding="utf-8"))
            jp_por_obra[obra] = split_by_anchors(
                clean_body((RAIZ / f"reports/livros_trabalho/jp/{obra}")
                           .read_text(encoding="utf-8")),
                [a["jp_anchor"] for a in spj["articles"]], label=obra)
        except Exception:
            jp_por_obra[obra] = None
        jan0 = janelas(obra, textos[obra])
        for it in itens:
            if jan0 is None or it["artigo"] >= len(jan0):
                recusadas.append((it["chave"], "janela do artigo indeterminável"))
                continue
            ini, fim = jan0[it["artigo"]]
            lim = paragrafo(textos[obra], ini, fim, it["de"])
            if lim is None:
                recusadas.append((it["chave"], "trecho não está na janela do artigo"))
                continue
            par = textos[obra][lim[0]:lim[1]]
            if par.count(it["de"]) != 1:
                recusadas.append((it["chave"],
                                  f"{par.count(it['de'])} ocorrências no parágrafo"))
                continue
            jpb = jp_por_obra[obra]
            jp = jpb[it["artigo"]] if jpb and it["artigo"] < len(jpb) else ""
            pedidos.append((obra, it, par, jp))

    emendas: dict[str, str] = {}
    trava, feito = threading.Lock(), [0]

    def calcula(arg):
        obra, it, par, jp = arg
        try:
            novo_par = emenda(jp, par, it["de"], it["para"])
        except Exception as exc:
            with trava:
                recusadas.append((it["chave"], f"erro de API: {exc!r}"[:70]))
            return
        motivo = contido(par, novo_par, it["de"], it["para"])
        with trava:
            feito[0] += 1
            if motivo:
                recusadas.append((it["chave"], motivo))
            else:
                emendas[it["chave"]] = novo_par
            if feito[0] % 25 == 0:
                print(f"  [{feito[0]}/{len(pedidos)}] "
                      f"{len(emendas)} aceitas, {len(recusadas)} recusadas", flush=True)

    if pedidos:
        with ThreadPoolExecutor(max_workers=12) as pool:
            list(pool.map(calcula, pedidos))
    print(f"\ncálculo: {len(emendas)} aceitas, {len(recusadas)} recusadas "
          f"de {tot}\n", flush=True)

    # gravação em série por obra: cada emenda desloca as posições seguintes
    for obra, itens in sorted(por_obra.items()):
        if obra not in textos:
            continue
        texto, antes, n = textos[obra], textos[obra], 0
        for it in [x for x in itens if x["chave"] in emendas]:
            jan = janelas(obra, texto)
            if jan is None or it["artigo"] >= len(jan):
                recusadas.append((it["chave"], "janela perdida durante a gravação"))
                break
            ini, fim = jan[it["artigo"]]
            lim = paragrafo(texto, ini, fim, it["de"])
            if lim is None or texto[lim[0]:lim[1]].count(it["de"]) != 1:
                recusadas.append((it["chave"], "parágrafo mudou desde o cálculo"))
                continue
            texto = texto[:lim[0]] + emendas[it["chave"]] + texto[lim[1]:]
            aplicadas.append(it["chave"])
            n += 1
        if not n:
            continue
        if not aplicar:
            print(f"  {obra[:44]:<46} {n:>3} emendadas (ensaio)")
            continue
        f = PT_FONTE / obra
        shutil.copy(f, f.with_suffix(f".txt.bak_aplic_{carimbo}"))
        f.write_text(texto, encoding="utf-8")
        (PT_STAGING / obra).write_text(texto, encoding="utf-8")
        sp = SPEC_DIR / f"{obra}.json"
        if sp.exists():
            anc = [x.get("pt_anchor", "") for x in
                   json.loads(sp.read_text(encoding="utf-8")).get("articles", [])]
            if len(anc) > 1 and all(anc):
                try:
                    if len(split_by_anchors(clean_body(texto), anc, label=obra)) != len(anc):
                        raise ValueError("contagem")
                except ValueError:
                    print(f"  *** ÂNCORA QUEBRADA — REVERTENDO {obra}")
                    f.write_text(antes, encoding="utf-8")
                    (PT_STAGING / obra).write_text(antes, encoding="utf-8")
                    aplicadas = [x for x in aplicadas
                                 if x not in {i["chave"] for i in itens}]
                    continue
        print(f"  {obra[:44]:<46} {n:>3} aplicadas")

    print(f"\n{len(aplicadas)} aplicadas, {len(recusadas)} recusadas pela verificação")
    for k, m in recusadas[:25]:
        print(f"  {k.split('|')[0][:26]} art{k.split('|')[1]}: {m}")
    if aplicar and aplicadas:
        ja = json.loads(REGISTRO.read_text(encoding="utf-8")) if REGISTRO.exists() else []
        REGISTRO.write_text(json.dumps(sorted(set(ja) | set(aplicadas)),
                                       ensure_ascii=False, indent=1), encoding="utf-8")
    if not aplicar:
        print("(ensaio — nada gravado; rode com --aplicar)")


if __name__ == "__main__":
    main()
