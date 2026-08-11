"""Aplica as correções das obras onde `implanta_semantico_v2.py`/
`repara_implanta_v2.py` não conseguiram fechar -- todas têm o mesmo padrão:
vários itens caem no MESMO parágrafo (frequente em relatos/falas longas sem
quebra de linha interna), e cada `novo_paragrafo` é uma reescrita
INDEPENDENTE do parágrafo inteiro, calculada sem saber dos outros itens do
mesmo parágrafo -- aplicar em sequência faz o item seguinte sobrescrever o
anterior (perda silenciosa), e se a correção mexe no trecho de abertura do
parágrafo (que é a própria âncora do artigo), a âncora quebra.

Decisão do usuário (2026-08-11): não tentar preservar `pt_anchor` durante a
aplicação -- as posições são calculadas contra o texto BASE (parado, nunca
editado durante o processo), aplicadas de trás pra frente (posição
descendente, pra uma edição não deslocar a posição da próxima), e a
segmentação inteira é refeita depois, num passo separado.

Método:
1. Pra cada obra, `janelas()` contra o texto BASE (sempre resolve --
   nenhuma dessas obras teve escrita bem sucedida ainda).
2. Pra cada item, acha o span do parágrafo (`paragrafo()`) contra o texto
   BASE -- nunca contra um texto já editado por outro item.
3. Agrupa itens do mesmo artigo cujos spans se sobrepõem. Grupo de 1 item:
   reaproveita o `novo_paragrafo` já calculado (sem nova chamada). Grupo de
   2+: UMA chamada nova ao DeepSeek, mostrando TODAS as trocas de uma vez,
   pedindo UM parágrafo que aplique todas juntas.
4. Aplica os grupos de trás pra frente (posição descendente) na obra
   inteira, de uma vez, sem `janelas()` no meio.

Uso:
    python3 scripts/mescla_e_aplica.py <checkpoint.json> <obra1> [obra2 ...]        # ensaio
    python3 scripts/mescla_e_aplica.py <checkpoint.json> <obra1> [obra2 ...] --aplicar
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

from build_clean_large_indexes import clean_body  # noqa: E402
from aplica_no_artigo import janelas  # noqa: E402
from implanta_semantico_v2 import (  # noqa: E402
    paragrafo, PT_FONTE, PT_STAGING, carrega_jp_por_obra,
    artigo_pt_para_contexto, MAX_JP, MAX_TOKENS_SAIDA, MODELO,
)
from goshinsho.services import agentic_search as ag  # noqa: E402

SYSTEM_MESCLA = """Você aplica VÁRIAS correções já aprovadas, todas no MESMO
parágrafo de uma tradução do japonês para o português, do acervo de
Meishu-Sama.

As decisões já foram tomadas por auditores -- você não as rediscute. Seu
trabalho é aplicar TODAS elas de uma vez, no mesmo parágrafo, sem que uma
atrapalhe a outra.

Você recebe o ARTIGO INTEIRO em português (contexto), o JAPONÊS do artigo,
o PARÁGRAFO original a reescrever, e a lista de correções (cada uma: um
trecho que muda para outro).

O QUE FAZER

Reescreva o PARÁGRAFO aplicando TODAS as correções da lista, cada uma no
lugar certo, com concordância de gênero/número/artigo/preposição ajustada
onde a troca exigir. Antes de devolver, confira se o conteúdo de qualquer
correção já aparece em outro lugar do artigo (contexto) -- se aparecer, não
repita.

O QUE NÃO FAZER

Não toque em nada do parágrafo que nenhuma das correções pede pra mudar --
o resto tem que sair EXATAMENTE como entrou, caractere por caractere. Não
use kanji/kana no português, salvo entre aspas com romaji entre parênteses.
Preserve citação de fonte entre colchetes, marcação de turno
(`Interlocutor:`, `Meishu-Sama:`) e numeração de poema/item.

CONVENÇÃO JÁ FIXADA (não a rediscuta, só aplique): quando o japonês trouxer
o marcador solto "（御教え）" (sem número de edição nem página), a forma
correta em português é sempre "(Mioshie-shū)" -- nunca "(Mioshie)" sozinho,
nem "(Ensinamento)" genérico.

Devolva SÓ o parágrafo corrigido, sem comentário, sem aspas em volta, sem
cabeçalho.
"""


def preserva_bordas(original: str, resposta: str) -> str:
    """O modelo devolve o parágrafo sem espaço/quebra de linha sobrando nas
    pontas -- normal quando o parágrafo é só o texto em si. Mas achado real
    (御讃歌集 art13, poemas separados por UMA quebra só, sem linha em
    branco): `paragrafo()` inclui a quebra final no span (fronteira real é
    o início do PRÓXIMO artigo, não há "\\n\\n" pra parar antes) -- sem essa
    quebra de volta, o poema seguinte gruda direto no anterior ("servem.14.
    Quem pensaria..."). Reconstrói as bordas de espaço em branco do
    original ao redor do texto novo, sempre que a resposta já não trouxer
    a borda por conta própria."""
    ini_ws = original[:len(original) - len(original.lstrip())]
    fim_ws = original[len(original.rstrip()):]
    r = resposta
    if ini_ws and not r.startswith(ini_ws):
        r = ini_ws + r
    if fim_ws and not r.endswith(fim_ws):
        r = r + fim_ws
    return r


def sobrepoe(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def agrupa_por_span(itens_artigo: list[dict], base: str, ini: int, fim: int) -> list[dict]:
    """Cada item ganha seu span (contra o texto BASE, nunca editado).
    Itens cujos spans se sobrepõem viram um grupo só."""
    com_span = []
    for it in itens_artigo:
        lim = paragrafo(base, ini, fim, it["de"])
        if lim is None:
            continue
        if base[lim[0]:lim[1]].count(it["de"]) < 1:
            continue
        com_span.append({**it, "span": lim})
    grupos: list[dict] = []
    for it in sorted(com_span, key=lambda x: x["span"][0]):
        destino = None
        for g in grupos:
            if sobrepoe(g["span"], it["span"]):
                destino = g
                break
        if destino is None:
            grupos.append({"span": it["span"], "itens": [it]})
        else:
            destino["itens"].append(it)
            a = min(destino["span"][0], it["span"][0])
            b = max(destino["span"][1], it["span"][1])
            destino["span"] = (a, b)
    return grupos


def mescla_grupo(jp: str, artigo_pt: str, par: str, itens: list[dict]) -> str:
    lista = "\n".join(f"- o trecho: {it['de']}\n  deve virar: {it['para']}" for it in itens)
    pedido = (f"=== JAPONÊS DO ARTIGO ===\n{jp[:MAX_JP]}\n\n"
              f"=== ARTIGO INTEIRO EM PORTUGUÊS (contexto) ===\n{artigo_pt_para_contexto(artigo_pt)}\n\n"
              f"=== PARÁGRAFO A EDITAR ===\n{par}\n\n"
              f"=== CORREÇÕES APROVADAS (aplicar todas) ===\n{lista}\n\n"
              f"Devolva o parágrafo com todas as correções aplicadas.")
    # achado real (御教え集15号 art1, 7 itens no mesmo parágrafo de 8387 chars):
    # com o teto normal (8192) o raciocínio sozinho já come o orçamento inteiro
    # e a resposta sai vazia (finish_reason=length) -- diferente do caso já
    # descartado em 2026-08-11 (subir o teto não resolvia uma falha
    # ESTRUTURAL de âncora cruzada). Aqui a demanda é genuína: quanto mais
    # correções mescladas + maior o parágrafo, mais raciocínio o modelo
    # precisa -- testado, 20000 resolve este caso de verdade (finish_reason
    # volta a "stop"). Por isso o teto maior é só uma 2ª tentativa, restrita
    # a este caminho (mesclagem de vários itens), não ao caso normal de 1
    # item por chamada.
    r = ag._client().chat.completions.create(
        model=MODELO, max_tokens=MAX_TOKENS_SAIDA,
        messages=[{"role": "system", "content": SYSTEM_MESCLA},
                  {"role": "user", "content": pedido}])
    conteudo = (r.choices[0].message.content or "").strip()
    if not conteudo and r.choices[0].finish_reason == "length":
        r = ag._client().chat.completions.create(
            model=MODELO, max_tokens=24000,
            messages=[{"role": "system", "content": SYSTEM_MESCLA},
                      {"role": "user", "content": pedido}])
        conteudo = (r.choices[0].message.content or "").strip()
    return conteudo


def processa_obra(obra: str, itens_por_chave: dict) -> dict:
    f = PT_FONTE / obra
    base = f.read_text(encoding="utf-8")
    jan = janelas(obra, base)
    if jan is None:
        return {"obra": obra, "erro": "janelas() falhou no texto BASE (nunca deveria)"}

    itens = [r for r in itens_por_chave.values() if r.get("obra") == obra and "novo_paragrafo" in r]
    por_artigo: dict[int, list[dict]] = {}
    for it in itens:
        por_artigo.setdefault(it["artigo"], []).append(it)

    jps = carrega_jp_por_obra(obra)
    substituicoes: list[tuple[int, int, str]] = []
    pendencias = []

    for artigo, seus in por_artigo.items():
        if artigo >= len(jan):
            pendencias.append((artigo, "artigo fora da janela"))
            continue
        ini, fim = jan[artigo]
        grupos = agrupa_por_span(seus, base, ini, fim)
        artigo_pt = base[ini:fim]
        jp = jps[artigo] if jps and artigo < len(jps) else ""
        for g in grupos:
            gi, gf = g["span"]
            par = base[gi:gf]
            if len(g["itens"]) == 1:
                np = preserva_bordas(par, g["itens"][0]["novo_paragrafo"])
            else:
                try:
                    np = mescla_grupo(jp, artigo_pt, par, g["itens"])
                except Exception as exc:
                    pendencias.append((artigo, f"erro de API no grupo: {exc!r}"[:120]))
                    continue
                np = preserva_bordas(par, np)
                if not np.strip():
                    pendencias.append((artigo, "grupo mesclado voltou vazio"))
                    continue
                if np == par:
                    pendencias.append((artigo, "grupo mesclado não mudou nada"))
                    continue
                # mesma guarda de crescimento do contido() (implanta_semantico_v2),
                # só que somando o delta esperado de TODOS os itens do grupo --
                # nunca aceitar um parágrafo mesclado que cresceu muito além do
                # que as correções pediam.
                delta_esperado = sum(max(0, len(it["para"]) - len(it["de"])) for it in g["itens"])
                crescimento_max = len(par) + delta_esperado + 250 * len(g["itens"])
                if len(np) > crescimento_max:
                    pendencias.append((artigo, f"grupo mesclado cresceu além do esperado "
                                                f"({len(np)} > {crescimento_max})"))
                    continue
            substituicoes.append((gi, gf, np))

    substituicoes.sort(key=lambda x: x[0], reverse=True)
    texto = base
    for gi, gf, np in substituicoes:
        texto = texto[:gi] + np + texto[gf:]

    return {
        "obra": obra, "texto": texto, "n_grupos": len(substituicoes),
        "n_itens": len(itens), "pendencias": pendencias,
    }


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    args = [a for a in sys.argv[1:] if a != "--aplicar"]
    checkpoint = Path(args[0])
    obras = args[1:]
    ck = json.loads(checkpoint.read_text(encoding="utf-8"))

    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    trava = threading.Lock()
    resultados = []

    def trabalho(obra):
        r = processa_obra(obra, ck)
        with trava:
            resultados.append(r)
            print(f"  {obra[:45]:<47} {r.get('n_grupos','-')} grupos aplicados de "
                  f"{r.get('n_itens','-')} itens, {len(r.get('pendencias', []))} pendências"
                  if "texto" in r else f"  {obra[:45]:<47} ERRO: {r.get('erro')}", flush=True)

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(trabalho, obras))

    for r in resultados:
        if "texto" not in r:
            continue
        for art, motivo in r["pendencias"]:
            print(f"    pendência {r['obra'][:40]} artigo {art}: {motivo}")
        if aplicar:
            f = PT_FONTE / r["obra"]
            shutil.copy(f, f.with_suffix(f".txt.bak_mescla_{carimbo}"))
            f.write_text(r["texto"], encoding="utf-8")
            (PT_STAGING / r["obra"]).write_text(r["texto"], encoding="utf-8")

    if not aplicar:
        print("\n(ensaio -- nada gravado; rode com --aplicar)")


if __name__ == "__main__":
    main()
