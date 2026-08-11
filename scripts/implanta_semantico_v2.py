"""Segunda versão do aplicador semântico -- conserta os dois bugs reais achados
na leitura dupla de verificação de 2026-08-11:

1. DUPLICAÇÃO: `aplicar_semantico.emenda()` só mostrava ao modelo o PARÁGRAFO
   sendo editado, nunca os parágrafos vizinhos -- quando a correção restaura
   um conteúdo que por acaso já está logo antes/depois (fora do parágrafo),
   o modelo não tinha como saber e duplicava. `aplicar_pilha_a.py` era pior
   ainda: fazia `texto.replace(de, para)` literal, sem NENHUM modelo na
   escrita -- a duplicação nasce inteira na proposta original
   (`leitura_fidelidade.py`), sem nenhuma chance de ser pega antes de gravar.

   Conserto: o modelo agora recebe o ARTIGO INTEIRO em português (não só o
   parágrafo), com instrução explícita de nunca restabelecer algo que já
   está no texto ao redor -- e SEMPRE passa por um modelo, nunca replace cru.

2. MARCADOR DE REMOÇÃO TRATADO COMO TEXTO: quando a correção aprovada tinha
   "para" = "-" ou "remover" ou "(remover)" (instrução de apagar o trecho,
   não texto de substituição), a aplicação cega colava essa palavra
   literalmente no corpus. Conserto: esses marcadores são detectados antes
   de chamar o modelo, e a instrução muda para "remova o trecho por
   completo, sem deixar resíduo".

Mesma disciplina de sempre -- nada muda nisso:
    localizar artigo e trecho   -> script (posição, sem julgamento)
    reescrever o PARÁGRAFO      -> DeepSeek, lendo o japonês e o ARTIGO INTEIRO
    verificar o que mudou       -> script (contido() -- mudança só no vão do trecho)
    gravar e revalidar âncora   -> script, revertendo se quebrar

Calcular e aplicar são passos separados de propósito: calcular só chama a
API (lento, caro, pode cair no meio de um lote grande) e grava um
checkpoint incremental a cada 20 itens -- rodar de novo com o mesmo
checkpoint retoma sem recalcular o que já foi feito. Aplicar é rápido
(só grava arquivo) e lê do checkpoint pronto.

    python3 scripts/implanta_semantico_v2.py --calcular casos.json checkpoint.json
    python3 scripts/implanta_semantico_v2.py --aplicar checkpoint.json
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402
from aplica_no_artigo import janelas  # noqa: E402
from goshinsho.services import agentic_search as ag  # noqa: E402

PT_FONTE = RAIZ / "livros_publicacao_pt_revisado"
PT_STAGING = RAIZ / "reports/livros_trabalho/pt"
SPEC_DIR = RAIZ / "reports/livros_trabalho/segmentacao_manual"
JP_DIR = RAIZ / "reports/livros_trabalho/jp"
MODELO = "deepseek-v4-flash"
CRESCIMENTO_MAX = 1.6
MAX_JP = 40000
MAX_ARTIGO_PT = 20000       # acima disso, corta uma janela ao redor do trecho
MAX_TOKENS_SAIDA = 8192     # testado 16000 (2026-08-11): não resolveu o único caso
                            # estrutural pendente (precisa de reparo de âncora, não
                            # de mais token) e, medido em casos normais, correlaciona
                            # com MAIS tokens gastos mesmo sem bater no teto -- não é
                            # reserva "de graça". Casos de borda ficam pendentes de
                            # revisão manual em vez de pagar o prêmio em todo o lote.

MARCADOR_REMOCAO = re.compile(r"^\s*[-–—]\s*$|^\s*\(?\s*(ou\s+)?remover(\s+a\s+frase)?\s*\.?\)?\s*$", re.I)
# "para" compound: frase real + marcador de remoção pendurado no fim, tipo
# 'Queimadura curada pelo Johrei (ou remover a frase).' -- achado real do
# teste (世界救世教奇蹟集|78): o regex acima só pega quando "para" é SÓ o
# marcador; este aqui pega quando o marcador vem colado ao final de uma frase.
MARCADOR_REMOCAO_FINAL = re.compile(r"\(\s*(ou\s+)?remover(\s+a\s+frase)?\s*\.?\)\.?\s*$", re.I)
# achado real (investigação dos 66 recusados, 2026-08-11): "remover" seguido
# de uma EXPLICAÇÃO ("remover a linha de data -- o texto passa a terminar
# em...") não batia em nenhum dos dois regex acima (exigem "remover" sozinho
# ou só no fim) -- caía no caminho de SUBSTITUIÇÃO normal, com a frase
# inteira de instrução sendo tratada como se fosse o texto literal a
# inserir, o que deixava o modelo confuso e a resposta saía vazia
# repetidamente, mesmo em retentativa. Esta forma pega "remover"/"suprimir"
# no INÍCIO de "para", com ou sem parênteses, com qualquer coisa depois.
MARCADOR_REMOCAO_DESCRITIVO = re.compile(r"^\s*\(?\s*(suprimir|remover)\b", re.I)
INSERE_ANTES = re.compile(r"^\s*(antes,?\s+)?inserir(\s+antes)?\s*:\s*(.+)$", re.I | re.S)
INSERE_DEPOIS = re.compile(r"^\s*(depois,?\s+)?inserir(\s+depois)?\s*:\s*(.+)$", re.I | re.S)

SYSTEM_SUBSTITUI = """Você aplica uma correção já aprovada a um parágrafo de tradução do
japonês para o português, do acervo de Meishu-Sama.

A decisão de corrigir já foi tomada por auditores. Você não a rediscute: seu
trabalho é fazer a emenda caber no português, com a frase inteira funcionando.

Você recebe o ARTIGO INTEIRO em português (para contexto) e o PARÁGRAFO que
deve ser reescrito. Antes de devolver, confira se o conteúdo que a correção
introduz JÁ aparece em outro lugar do artigo (antes ou depois do parágrafo) --
se aparecer, NÃO repita: escreva a correção de forma que o sentido fique
certo sem duplicar o que já está dito em outro ponto do texto.

O QUE FAZER

Reescreva o PARÁGRAFO com a correção aplicada, ajustando o que a troca
exigir: concordância de gênero e número, artigo, preposição, ordem das
palavras.

O QUE NÃO FAZER

Não melhore o resto do parágrafo. Não reorganize frases que a correção não
toca. Não acrescente nem remova conteúdo além do que a correção pede. Tudo
que estiver fora da região da correção tem de sair EXATAMENTE como entrou,
caractere por caractere -- o parágrafo devolvido é comparado com o original
e recusado se você mexer noutro lugar.

Não use kanji nem kana no português, salvo entre aspas com romaji entre
parênteses. Preserve as citações de fonte entre colchetes, as marcações de
turno (`Interlocutor:`, `Meishu-Sama:`) e a numeração de poema ou item.

CONVENÇÃO JÁ FIXADA (não a rediscuta, só aplique): quando o japonês trouxer
o marcador solto "（御教え）" (sem número de edição nem página), a forma
correta em português é sempre "(Mioshie-shū)" -- nunca "(Mioshie)" sozinho,
nem "(Ensinamento)" genérico. Se a correção que você está aplicando reduzir
esse marcador para uma dessas formas erradas, mantenha "(Mioshie-shū)" em
vez de seguir literalmente o texto da correção nesse ponto específico --
essa é uma convenção de nomenclatura já decidida para o projeto inteiro,
não uma leitura nova a fazer.

Devolva SÓ o parágrafo corrigido, sem comentário, sem aspas em volta, sem
cabeçalho.
"""

SYSTEM_REMOVE = """Você aplica uma correção já aprovada a um parágrafo de tradução do
japonês para o português, do acervo de Meishu-Sama.

A correção aprovada é REMOVER um trecho por completo -- ele foi identificado
como acréscimo sem correspondência no japonês. Você recebe o ARTIGO INTEIRO
em português (para contexto) e o PARÁGRAFO de onde o trecho deve sair.

O QUE FAZER

Devolva o parágrafo com o trecho indicado REMOVIDO por completo -- nenhuma
palavra no lugar dele, nem "remover" nem "-" nem qualquer marcador. Ajuste
só a pontuação e o espaçamento imediatamente ao redor do ponto da remoção
(vírgula/ponto sobrando, quebra de linha dupla se o trecho era uma linha
inteira), para o parágrafo continuar gramatical.

O QUE NÃO FAZER

Não toque em mais nada do parágrafo. Tudo fora da região da remoção tem de
sair EXATAMENTE como entrou.

Devolva SÓ o parágrafo resultante, sem comentário, sem aspas em volta.
"""

SYSTEM_INSERE = """Você aplica uma correção já aprovada a um parágrafo de tradução do
japonês para o português, do acervo de Meishu-Sama.

A correção aprovada é INSERIR uma frase que faltava -- ela foi identificada
como omissão em relação ao japonês. Você recebe o ARTIGO INTEIRO em
português (para contexto), o japonês, o PARÁGRAFO onde a frase deve entrar,
o TRECHO DE REFERÊNCIA (onde a inserção acontece, antes ou depois dele) e a
FRASE A INSERIR.

O QUE FAZER

Confirme no japonês que a frase realmente corresponde a um trecho que falta
no português (cite o trecho japonês correspondente antes de decidir).
Confirme também que essa frase NÃO aparece em nenhum outro lugar do artigo
(contexto acima) -- se já aparecer, não a repita, e devolva o parágrafo sem
mudança nenhuma. Se estiver tudo certo, devolva o parágrafo com a frase
inserida na posição indicada (antes ou depois do trecho de referência,
conforme a instrução), com pontuação e conector natural em português. O
TRECHO DE REFERÊNCIA deve continuar no parágrafo -- ele não está sendo
substituído, só ganhando a frase nova ao lado.

O QUE NÃO FAZER

Não toque em mais nada do parágrafo. Não reescreva o trecho de referência.

Devolva SÓ o parágrafo resultante, sem comentário, sem aspas em volta.
"""


def paragrafo(texto: str, ini: int, fim: int, trecho: str) -> tuple[int, int] | None:
    p = texto.find(trecho, ini, fim)
    if p < 0:
        return None
    a = texto.rfind("\n\n", ini, p)
    a = ini if a < 0 else a + 2
    b = texto.find("\n\n", p + len(trecho))
    b = fim if b < 0 or b > fim else b
    return a, b


def contido(velho: str, novo: str, trecho: str, para: str) -> str | None:
    """Aceita só se a mudança estiver contida na região da correção.

    Duas regras foram substituídas depois do teste de 2026-08-11 achar que
    rejeitavam correções CERTAS, já conferidas contra o japonês (o modelo
    tinha razão, a guarda que estava errada):

    · "se 'trecho' ainda aparece em 'novo', recusa" -- falso positivo sempre
      que "para" contém "trecho" como substring, o que é o caso NORMAL de
      inserção (nada é removido, só algo é acrescentado ao lado) e também de
      qualquer prefixo/sufixo adicionado antes/depois do trecho original.
      Substituído por "novo == velho" (nada mudou é a falha real).
    · teto de crescimento FIXO (1.6x do parágrafo inteiro) -- rejeitava
      restaurações grandes e legítimas (ex.: título inteiro que faltava)
      só porque high genuinamente muda bastante o texto. Substituído por um
      teto ligado ao que "para" já anuncia que vai crescer (len(para) vs
      len(trecho)), não ao tamanho do parágrafo inteiro.
    """
    if not novo.strip():
        # achado real (investigação dos 66 recusados, 2026-08-11): quando o
        # parágrafo INTEIRO é o trecho a remover (uma linha de byline/título
        # sozinha, sem mais nada), o resultado correto DEPOIS de remover é
        # mesmo vazio -- o modelo reconhecia isso certo (reasoning_content
        # confirmado: "the result is an empty line... output nothing") e
        # essa guarda rejeitava a resposta certa como se fosse falha. Só
        # aceita vazio nesse caso específico -- em qualquer outro, resposta
        # vazia continua sendo recusada.
        resto = velho.strip().replace(trecho.strip(), "", 1).strip("*_\"'` \n")
        if trecho.strip() == velho.strip() or (trecho.strip() in velho.strip() and not resto):
            # aceita vazio quando "trecho" É o parágrafo, ou quando o
            # parágrafo é só "trecho" decorado por marcação (ex.:
            # "*Vila de Shishimachi...*" -- achado real, 世界救世教奇蹟集
            # art19: o "de" não incluía os asteriscos do markdown, então
            # trecho != parágrafo em bytes mas semanticamente é a mesma
            # linha inteira; sobra só pontuação/marcação depois de tirar
            # "trecho" do meio, nunca texto de verdade).
            return None
        return "resposta vazia"
    if novo == velho:
        return "não mudou nada"
    delta_esperado = max(0, len(para) - len(trecho))
    crescimento_max = len(velho) + delta_esperado + 250   # folga p/ ajuste gramatical
    if len(novo) > crescimento_max:
        return f"parágrafo cresceu além do esperado ({len(novo)} > {crescimento_max})"
    i = 0
    while i < min(len(velho), len(novo)) and velho[i] == novo[i]:
        i += 1
    j = 0
    while (j < min(len(velho), len(novo)) - i
           and velho[len(velho) - 1 - j] == novo[len(novo) - 1 - j]):
        j += 1
    MARGEM = 150
    p_ini = velho.find(trecho)
    if p_ini < 0:
        return None
    p_fim = p_ini + len(trecho)
    if i > p_ini + MARGEM or (len(velho) - j) < p_fim - MARGEM:
        return "mudou fora do vão do trecho"
    return None


def artigo_pt_para_contexto(artigo_pt: str) -> str:
    """Se o artigo for muito longo, o contexto integral não cabe -- mas o
    risco de duplicação é sempre LOCAL (parágrafos vizinhos), nunca do outro
    lado de um artigo de 30 mil caracteres. Nesse caso o próprio parágrafo
    (já incluído à parte no prompt) já cobre o essencial; passamos só o
    artigo inteiro quando ele cabe com folga."""
    if len(artigo_pt) <= MAX_ARTIGO_PT:
        return artigo_pt
    return artigo_pt[:MAX_ARTIGO_PT] + "\n\n[...artigo truncado por tamanho...]"


def _extrai_insercao(para: str) -> tuple[str, str] | None:
    """Se 'para' for uma instrução 'Inserir antes/depois: "X"', devolve
    (posicao, frase). Senão, None."""
    m = INSERE_ANTES.match(para.strip())
    if m:
        return "antes", m.group(3).strip().strip('"').strip("'")
    m = INSERE_DEPOIS.match(para.strip())
    if m:
        return "depois", m.group(3).strip().strip('"').strip("'")
    return None


def para_efetivo_para_marcador(para: str) -> str:
    """'para' pode ser só o marcador de remoção, ou uma frase real com o
    marcador colado no fim (ex.: '...curado pelo Johrei (ou remover a
    frase).') -- neste caso o marcador vale, mas por prudência tratamos como
    substituição normal pela frase SEM o marcador, não como remoção (a frase
    real tem conteúdo que o marcador puro não tem)."""
    return MARCADOR_REMOCAO_FINAL.sub("", para).strip()


def emenda_v2(jp: str, artigo_pt: str, par: str, de: str, para: str) -> str:
    remover = bool(MARCADOR_REMOCAO.match(para.strip()) or MARCADOR_REMOCAO_DESCRITIVO.match(para.strip()))
    insercao = None if remover else _extrai_insercao(para)

    if remover:
        system = SYSTEM_REMOVE
        # achado real: "remover"/"suprimir" seguido de uma explicação
        # ("remover a linha de data -- o texto passa a terminar em...") tem
        # informação útil (o que deve sobrar depois) -- passa como
        # orientação extra, não descarta.
        guia = MARCADOR_REMOCAO.match(para.strip())
        explicacao = "" if guia else para.strip()
        pedido = (f"=== JAPONÊS DO ARTIGO ===\n{jp[:MAX_JP]}\n\n"
                  f"=== ARTIGO INTEIRO EM PORTUGUÊS (contexto) ===\n{artigo_pt_para_contexto(artigo_pt)}\n\n"
                  f"=== PARÁGRAFO A EDITAR ===\n{par}\n\n"
                  f"=== TRECHO A REMOVER ===\n{de}\n\n"
                  + (f"=== ORIENTAÇÃO DE QUEM APROVOU A REMOÇÃO ===\n{explicacao}\n\n" if explicacao else "")
                  + "Devolva o parágrafo com esse trecho removido.")
    elif insercao:
        posicao, frase = insercao
        system = SYSTEM_INSERE
        pedido = (f"=== JAPONÊS DO ARTIGO ===\n{jp[:MAX_JP]}\n\n"
                  f"=== ARTIGO INTEIRO EM PORTUGUÊS (contexto) ===\n{artigo_pt_para_contexto(artigo_pt)}\n\n"
                  f"=== PARÁGRAFO A EDITAR ===\n{par}\n\n"
                  f"=== TRECHO DE REFERÊNCIA (permanece no parágrafo) ===\n{de}\n\n"
                  f"=== FRASE A INSERIR ({posicao} do trecho de referência) ===\n{frase}\n\n"
                  f"Devolva o parágrafo com a frase inserida {posicao} do trecho de referência, "
                  f"depois de confirmar contra o japonês que ela realmente falta.")
    else:
        para_eff = para_efetivo_para_marcador(para) or para
        system = SYSTEM_SUBSTITUI
        pedido = (f"=== JAPONÊS DO ARTIGO ===\n{jp[:MAX_JP]}\n\n"
                  f"=== ARTIGO INTEIRO EM PORTUGUÊS (contexto) ===\n{artigo_pt_para_contexto(artigo_pt)}\n\n"
                  f"=== PARÁGRAFO A EDITAR ===\n{par}\n\n"
                  f"=== CORREÇÃO APROVADA ===\n"
                  f"o trecho: {de}\n"
                  f"deve virar: {para_eff}\n\n"
                  f"Devolva o parágrafo corrigido.")
    r = ag._client().chat.completions.create(
        model=MODELO, max_tokens=MAX_TOKENS_SAIDA,
        messages=[{"role": "system", "content": system},
                  {"role": "user", "content": pedido}])
    return (r.choices[0].message.content or "").strip()


def carrega_jp_por_obra(obra: str) -> list[str] | None:
    sp = SPEC_DIR / f"{obra}.json"
    if not sp.exists():
        return None
    try:
        spec = json.loads(sp.read_text(encoding="utf-8"))
        jp_bruto = (JP_DIR / obra).read_text(encoding="utf-8")
        return split_by_anchors(clean_body(jp_bruto), [a["jp_anchor"] for a in spec["articles"]], label=obra)
    except Exception:
        return None


def calcula_emenda(item: dict) -> dict:
    """item: {chave, obra, artigo, de, para}. Devolve item + 'novo_paragrafo'
    ou 'recusa' (motivo)."""
    obra, artigo, de, para = item["obra"], item["artigo"], item["de"], item["para"]
    f = PT_FONTE / obra
    if not f.exists():
        return {**item, "recusa": "obra inexistente"}
    texto = f.read_text(encoding="utf-8")
    jan = janelas(obra, texto)
    if jan is None or artigo >= len(jan):
        return {**item, "recusa": "janela do artigo indeterminável"}
    ini, fim = jan[artigo]
    lim = paragrafo(texto, ini, fim, de)
    if lim is None:
        return {**item, "recusa": "trecho não está na janela do artigo"}
    par = texto[lim[0]:lim[1]]
    if par.count(de) != 1:
        return {**item, "recusa": f"{par.count(de)} ocorrências no parágrafo"}
    artigo_pt = texto[ini:fim]
    jps = carrega_jp_por_obra(obra)
    jp = jps[artigo] if jps and artigo < len(jps) else ""

    # "para" efetivo p/ o cálculo de crescimento esperado em contido() --
    # tem de refletir o que a correção REALMENTE deve produzir, não o texto
    # cru da instrução (que pode ser "Inserir antes: ..." ou ter marcador
    # de remoção colado).
    if MARCADOR_REMOCAO.match(para.strip()) or MARCADOR_REMOCAO_DESCRITIVO.match(para.strip()):
        para_delta = ""
    else:
        ins = _extrai_insercao(para)
        if ins:
            _, frase = ins
            para_delta = de + " " + frase
        else:
            para_delta = para_efetivo_para_marcador(para) or para

    try:
        novo_par = emenda_v2(jp, artigo_pt, par, de, para)
    except Exception as exc:
        return {**item, "recusa": f"erro de API: {exc!r}"[:100]}
    # achado real (mescla_e_aplica.py, 御讃歌集 art13): o modelo devolve o
    # parágrafo sem espaço/quebra nas pontas -- em coleções sem "\n\n" entre
    # itens (poemas separados por 1 quebra só), essa quebra final É parte do
    # parágrafo (fronteira real é o início do próximo artigo). Sem
    # reconstituir a borda, o item seguinte gruda no anterior.
    ini_ws = par[:len(par) - len(par.lstrip())]
    fim_ws = par[len(par.rstrip()):]
    if ini_ws and not novo_par.startswith(ini_ws):
        novo_par = ini_ws + novo_par
    if fim_ws and not novo_par.endswith(fim_ws):
        novo_par = novo_par + fim_ws
    motivo = contido(par, novo_par, de, para_delta)
    if motivo:
        return {**item, "recusa": motivo}
    return {**item, "novo_paragrafo": novo_par, "lim": lim}


def calcular(caminho: str, checkpoint: str) -> None:
    """Só calcula (chama o DeepSeek), nunca toca o corpus. Grava incremental
    em `checkpoint` a cada item -- retomável: se o processo cair, rodar de
    novo com o mesmo checkpoint pula o que já foi calculado."""
    itens = json.loads(Path(caminho).read_text(encoding="utf-8"))
    ck = Path(checkpoint)
    feitos: dict[str, dict] = json.loads(ck.read_text(encoding="utf-8")) if ck.exists() else {}
    pendentes = [it for it in itens if it["chave"] not in feitos]
    print(f"{len(itens)} casos, {len(feitos)} já calculados, {len(pendentes)} pendentes\n", flush=True)
    trava, feito = threading.Lock(), [0]

    def trabalho(item):
        try:
            r = calcula_emenda(item)
        except Exception as exc:
            r = {**item, "recusa": f"erro não tratado: {exc!r}"[:120]}
        with trava:
            feito[0] += 1
            feitos[item["chave"]] = r
            if feito[0] % 20 == 0:
                ck.write_text(json.dumps(feitos, ensure_ascii=False, indent=1), encoding="utf-8")
                aceitas = sum(1 for x in feitos.values() if "novo_paragrafo" in x)
                print(f"  [{feito[0]}/{len(pendentes)} desta rodada, {len(feitos)}/{len(itens)} no total] "
                      f"{aceitas} aceitas até agora", flush=True)

    if pendentes:
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(trabalho, pendentes))
    ck.write_text(json.dumps(feitos, ensure_ascii=False, indent=1), encoding="utf-8")

    aceitas = [r for r in feitos.values() if "novo_paragrafo" in r]
    recusadas = [r for r in feitos.values() if "recusa" in r]
    print(f"\n{len(aceitas)} aceitas, {len(recusadas)} recusadas (total no checkpoint)\n")
    from collections import Counter
    c = Counter(r["recusa"].split(" (")[0].split(":")[0][:40] for r in recusadas)
    for motivo, n in c.most_common(15):
        print(f"  {n:>4}  {motivo}")

    print("\n--- checagem de duplicação nos aceitos ---")
    REPETE = re.compile(r"\b((?:[A-Za-zÀ-ÿ()º°]+)(?:\s+[A-Za-zÀ-ÿ()º°]+){1,6})\s+\1\b", re.I)
    suspeitos = 0
    for r in aceitas:
        m = REPETE.search(r["novo_paragrafo"])
        if m and m.group(1) not in r["obra"]:
            trecho_generico = m.group(1).strip()
            if len(trecho_generico) >= 6:
                suspeitos += 1
                print(f"  *** possível duplicação em {r['chave'][:55]}: {m.group(0)[:100]!r}")
    if not suspeitos:
        print("  nenhuma duplicação nova detectada nos aceitos")


def aplicar_de_checkpoint(checkpoint: str) -> None:
    feitos = json.loads(Path(checkpoint).read_text(encoding="utf-8"))
    aceitas = [r for r in feitos.values() if "novo_paragrafo" in r]
    print(f"{len(aceitas)} aceitas no checkpoint, aplicando...\n", flush=True)
    aplicar_resultados(aceitas)


def aplicar_resultados(aceitas: list[dict]) -> None:
    por_obra: dict[str, list[dict]] = {}
    for r in aceitas:
        por_obra.setdefault(r["obra"], []).append(r)
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for obra, itens in por_obra.items():
        f = PT_FONTE / obra
        texto = f.read_text(encoding="utf-8")
        antes = texto
        n = 0
        # ordem descendente por artigo -- gravar do fim pro início evita que
        # uma edição early desloque a posição de uma edição later no mesmo
        # texto (mesmo raciocínio de sempre; a reconferência abaixo garante
        # segurança mesmo se a ordem não for perfeita)
        for it in sorted(itens, key=lambda x: x["artigo"], reverse=True):
            jan = janelas(obra, texto)
            if jan is None or it["artigo"] >= len(jan):
                continue
            ini, fim = jan[it["artigo"]]
            lim2 = paragrafo(texto, ini, fim, it["de"])
            if lim2 is None or texto[lim2[0]:lim2[1]].count(it["de"]) != 1:
                print(f"  PULADO na gravação (mudou): {it['chave'][:60]}")
                continue
            texto = texto[:lim2[0]] + it["novo_paragrafo"] + texto[lim2[1]:]
            n += 1
        if not n:
            continue
        shutil.copy(f, f.with_suffix(f".txt.bak_implantav2_{carimbo}"))
        f.write_text(texto, encoding="utf-8")
        (PT_STAGING / obra).write_text(texto, encoding="utf-8")
        sp = SPEC_DIR / f"{obra}.json"
        if sp.exists():
            anc = [a.get("pt_anchor", "") for a in json.loads(sp.read_text(encoding="utf-8")).get("articles", [])]
            if len(anc) > 1 and all(anc):
                try:
                    if len(split_by_anchors(clean_body(texto), anc, label=obra)) != len(anc):
                        raise ValueError()
                except ValueError:
                    print(f"  *** ÂNCORA QUEBRADA — REVERTENDO {obra}")
                    f.write_text(antes, encoding="utf-8")
                    (PT_STAGING / obra).write_text(antes, encoding="utf-8")
                    continue
        print(f"  {obra[:50]:<52} {n:>3} aplicadas")


if __name__ == "__main__":
    if "--calcular" in sys.argv:
        i = sys.argv.index("--calcular")
        caminho, checkpoint = sys.argv[i + 1], sys.argv[i + 2]
        calcular(caminho, checkpoint)
    elif "--aplicar" in sys.argv:
        i = sys.argv.index("--aplicar")
        aplicar_de_checkpoint(sys.argv[i + 1])
    else:
        print(__doc__)
        print("\nUso:\n"
              "  python3 implanta_semantico_v2.py --calcular casos.json checkpoint.json\n"
              "  python3 implanta_semantico_v2.py --aplicar checkpoint.json")
        sys.exit(1)
