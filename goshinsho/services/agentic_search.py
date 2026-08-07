"""Busca agenciada sobre o acervo real (sem embedding/FAISS) -- implementação
de produção dos achados corrigíveis do piloto, ver
`docs/13-ESTUDO-MIGRACAO-BUSCA-AGENTICA.md`:

- §3.3: busca literal tolerante a acento/maiúscula, com fronteira de palavra
  (reaproveita `fold_ortografico_lower`, já usada em `search_glossary.py`).
- §3.6: ordenação por relevância (densidade de termos da própria busca ao
  redor de cada ocorrência), não pela ordem em que os arquivos são varridos.
- §3.4: reforço de citação literal de arquivo + validação programática
  best-effort (`validar_citacoes`).
- §3.2 (o bug mais sério do piloto): o laço agenciado separa o orçamento de
  rodadas de busca do orçamento de síntese -- se o modelo esgota as rodadas
  de busca sem parar sozinho, uma última chamada é feita SEM ferramentas
  disponíveis, forçando síntese com o que já foi encontrado, nunca resposta
  vazia.
- §3.5: política decidida pelo usuário (2026-07-29) para eventos posteriores
  à morte de Meishu-Sama (1955): inferência rotulada é permitida (mesmo
  comportamento que já existe em produção), mas precisa de regra explícita
  no prompt -- adicionada abaixo.
- §3.8 (desacoplar do modelo de embedding): já feito em
  `search_service.carregar_chunks_metadados_pt_leve`, reaproveitado aqui
  via `teaching_article_service` (que já usa essa função).
- §3.9 (achado 2026-07-29, depois de eliminar o teto fixo de rodadas a
  pedido do usuário): sem teto, o modelo pode entrar em loop de
  reformulação sem nunca achar nada novo -- turno 3 do piloto v3
  ("é possível mudar de plano espiritual na mesma reencarnação?") foi até
  o teto de segurança de 40 rodadas (125s, $0,204) sem se dar por vencido
  antes. Mecanismo ESTRUTURAL de estagnação (nunca temático -- ver regra
  suprema anti-tutela do projeto): rastreia um "fingerprint" de conteúdo
  (hash do texto retornado, não só o nome do arquivo) de cada chamada de
  ferramenta; se `LIMITE_ESTAGNACAO_RODADAS` rodadas consecutivas não
  trouxerem NENHUM fragmento de texto genuinamente novo (nem em
  `buscar_termo`, `ler_mais_contexto` ou `buscar_artigo_por_titulo`),
  força a síntese mais cedo, reaproveitando o mesmo mecanismo já usado
  para o teto de segurança. Reler um trecho já visto de um arquivo já
  encontrado não é penalizado por si só (é normal aprofundar); o que conta
  é o CONTEÚDO (texto) já ter aparecido antes, não o arquivo. Validado com
  2 pares de controle sem relação temática com o achado original antes de
  reconfirmar os turnos 3/4 -- ver `reports/agentic_search_orcamento/
  VALIDACAO.json` e a seção correspondente do CLAUDE.md.
- §3.10 (achado 2026-07-30, causa raiz real por trás do §3.9): o usuário
  apontou que ajustar o limiar de rodadas não resolve o problema de fundo --
  o modelo nunca reconhece que a busca se esgotou porque toda reformulação
  ainda acha ALGO tangencial (nunca um "zero resultados" que dispararia a
  regra 6 do prompt). Investigando o turno 3 do piloto ("mudar de plano
  espiritual na mesma reencarnação"), achamos 2 causas reais e corrigíveis:
  (a) `buscar_termo` batia frase de várias palavras como substring
  CONTÍGUA -- o corpus usa "planos: superior, médio e inferior" para a
  hierarquia do mundo espiritual, nunca a frase "plano espiritual inferior"
  que o modelo tentou; corrigido para AND de palavras significativas em
  janela de proximidade, não mais frase exata (só agentic_search.py --
  pt_direct/jp_direct usam outro mecanismo, não tocados); (b) "plano
  espiritual" tem 2 sentidos no corpus (genérico vs. hierarquia) e o modelo
  sempre buscava o sentido errado -- criado
  `glossario_sinonimos_busca_agente.json` (novo, terceiro glossário do
  projeto, distinto de `glossario.json` e `glossario_traducao.json`) para
  equalizar isso: quando a busca bate uma frase cadastrada, os termos
  relacionados também são buscados automaticamente. Estrutural (equaliza
  vocabulário por termo literal, não por tema da pergunta) -- consistente
  com a regra suprema anti-tutela do projeto.

Este módulo ainda NÃO está ligado a `routes.py`/`pipeline/answer.py`. É a
peça a ser testada (passo 6 da seção 5 do estudo) antes de qualquer
integração real na pipeline de produção -- nenhuma promoção/troca de
produção sem autorização explícita do usuário.

Cobre também o item explicitamente não testado no estudo original (§4):
`responder_agentico_deepseek_jp` busca no acervo ORIGINAL japonês
(`textos_japones/*.txt`), mesma arquitetura, resposta final sempre em
português (traduzindo qualquer trecho japonês encontrado).
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from functools import lru_cache
from pathlib import Path

from .text_normalize import fold_ortografico_lower

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
TEXTOS_DIR = PROJECT_ROOT / "textos_portugues"
JAPONES_DIR = PROJECT_ROOT / "textos_japones"

# Não é mais um orçamento de trabalho (a decisão de quando parar de buscar é
# do próprio modelo, ver regras 2/6/7 do SYSTEM_PROMPT abaixo) -- é só uma
# rede de segurança contra loop descontrolado/custo fora de controle. Um
# valor alto o suficiente para nunca ser alcançado em uso normal (2026-07-29:
# o teste mais exigente até agora usou 6 rodadas antes desta mudança);
# atingi-lo é sinal de anomalia, não de pergunta difícil.
LIMITE_SEGURANCA_RODADAS = 40

# 2026-08-06: achado real em produção -- pergunta sem resposta literal no
# acervo ("filósofo/artista/salvador") esgotou as 40 rodadas de segurança
# em 270s, bem acima do timeout de 180s do gunicorn (--timeout 180), o
# worker foi morto no meio (WORKER TIMEOUT + SIGKILL) e o usuário viu
# "Resposta inesperada do servidor" -- 3 vezes, reproduzido e confirmado.
# O teto de RODADA sozinho não protege contra isso, porque a duração de
# cada rodada varia (latência real da API DeepSeek, já documentada em
# sessão anterior). Este teto de TEMPO DECORRIDO é um segundo tipo de rede
# de segurança, independente da contagem de rodada -- força a mesma
# síntese com o que já foi encontrado (nunca resposta vazia) bem antes do
# timeout do servidor, com margem real para a própria chamada de síntese
# final (que também gasta tempo) e para o overhead de fila/streaming do
# routes.py. Escolhido 100s: no pior caso já medido (~7s/rodada média),
# ainda permite ~14 rodadas de busca real antes de cortar -- suficiente
# pra a maioria das perguntas difíceis já testadas no projeto -- e deixa
# ~80s de margem sob os 180s do gunicorn para síntese + streaming.
LIMITE_SEGURANCA_SEGUNDOS = 100

# §3.9: quantas rodadas CONSECUTIVAS de chamada de ferramenta sem nenhum
# fragmento de texto genuinamente novo (fingerprint de conteúdo) contam como
# "estagnação" e forçam a síntese mais cedo. Escolhido 3, não 1: uma única
# rodada sem novidade é esperada e normal (o próprio SYSTEM_PROMPT, regra 2,
# instrui tentar pelo menos um sinônimo antes de desistir -- cortar em 1
# penalizaria exatamente o comportamento pedido); 3 consecutivas sem NENHUM
# conteúdo novo é um sinal estrutural forte de loop de reformulação vazio,
# sem depender do tema da pergunta.
LIMITE_ESTAGNACAO_RODADAS = 3

# 2026-07-31: a pedido do usuário -- preocupação com experiência do
# usuário durante a espera, não com o tempo total em si. Depois de uma
# primeira busca curta (esta constante) sem resposta pronta, o chamador
# (routes.py) é avisado uma vez via `on_deep_search`, pra poder mostrar
# "ainda pesquisando" ao usuário -- não muda em nada o que o agente busca
# nem quando ele decide parar, só quando um aviso é disparado.
RODADAS_AVISO_BUSCA_PROFUNDA = 3
JANELA_PROXIMIDADE = 400
# 2026-08-07: 8000 -> 20000, medido em teste ISOLADO (12 execuções
# sequenciais, 3 perguntas x 2 caps x 2 repetições, tudo o mais idêntico à
# configuração de produção). O corte de 8000 descartava em silêncio a CAUDA
# do resultado de busca -- 31 buscas truncadas e 96.234 caracteres perdidos
# só nessas 6 execuções -- e o modelo gastava rodadas extras tentando
# recuperar o que já tinha sido encontrado e jogado fora:
#
#   pergunta   cap 8000              cap 20000
#   difícil    123,7s / 8,0 rodadas  54,8s / 5,0 rodadas
#   ampla       40,2s / 2,5 rodadas  47,2s / 3,5 rodadas   (empate, ruído)
#   simples     67,1s / 6,5 rodadas  28,4s / 3,5 rodadas
#   GERAL       77,0s / 5,7 rodadas  43,5s / 4,0 rodadas   (-44%, venceu 5 de 6 pares)
#
# Fundamentação (fontes abertas) ficou igual: 3,5 x 3,2, dentro do ruído --
# o ganho é de trabalho desperdiçado, não de profundidade. IMPORTANTE: este
# valor foi testado SOZINHO. Uma tentativa anterior de mudá-lo junto com
# janela de trecho e fusão de hits ("alavanca estrutural") foi reprovada em
# bloco, escondendo o fato de que o cap era a peça boa do pacote.
TAMANHO_MAX_RESULTADO_FERRAMENTA = 20000

# 2026-07-31: preço do deepseek-v4-flash recalibrado contra a fatura REAL
# (painel de faturamento DeepSeek, 29/07: US$ 0,59 / 13.923.984 tokens =
# ~US$ 0,0424/1M, blended) -- a tabela assumida antes ($0,28/$0,42)
# superestimava em ~6-7x porque o código nunca lia os campos de cache que a
# API retorna, e o laço agenciado reenvia um prefixo quase idêntico a cada
# rodada de ferramenta (fortemente descontado por cache de contexto em
# disco). Ver mesma constante/nota em deepseek_usage_service.py -- fonte
# única da verdade é lá, este valor é mantido igual só para o "custo"
# autorreportado por esta função não divergir do dashboard admin.
PRECOS = {
    "deepseek-v4-flash": {"entrada": 0.0424, "saida": 0.0424},
    "claude-sonnet-5": {"entrada": 3.0, "saida": 15.0},
    "claude-haiku-4-5-20251001": {"entrada": 1.0, "saida": 5.0},
}


# --------------------------------------------------------------------------
# Corpus em memória (carregado uma vez por processo) -- grep literal real
# sobre os arquivos de produção, sem nenhum índice vetorial.
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _corpus_pt() -> dict[str, tuple[str, str]]:
    """arquivo -> (texto original, texto dobrado p/ busca sem acento/maiúscula).

    `fold_ortografico_lower` preserva a posição caractere-a-caractere do
    texto original no caso comum (texto já em NFC, sem multi-diacríticos) --
    por isso é seguro usar a posição encontrada no texto dobrado direto no
    texto original ao extrair o trecho."""
    corpus: dict[str, tuple[str, str]] = {}
    for path in sorted(TEXTOS_DIR.glob("*.txt")):
        try:
            texto = path.read_text(encoding="utf-8")
        except Exception:
            continue
        corpus[path.name] = (texto, fold_ortografico_lower(texto))
    return corpus


def _termos_significativos(termo_folded: str) -> list[str]:
    return [t for t in re.split(r"\s+", termo_folded.strip()) if len(t) >= 3]


@lru_cache(maxsize=1)
def _glossario_sinonimos_busca() -> dict[str, dict]:
    """§3.10/§3.11 (achado 2026-07-30): glossário de desambiguação/sinônimos
    SÓ do modo agenciado (glossario_sinonimos_busca_agente.json na raiz do
    projeto) -- diferente de glossario.json (kanji->PT, usado por
    pt_direct/jp_direct) e glossario_traducao.json (tradução do corpus), não
    tocados por este módulo. Cada entrada tem até 3 campos: `termos_
    relacionados` (busca adicional, ver `_termos_expandidos_por_glossario`),
    `significado` (definição NEUTRA/ESTRUTURAL do termo, mostrada ao agente
    via `_significados_por_glossario` -- NUNCA uma conclusão que responda a
    uma pergunta específica, isso seria tutela) e `nota` (só documentação,
    nunca lida por código). Estrutural, não temático: equaliza vocabulário e
    evita que o agente confunda termos parecidos, nunca decide por
    assunto/doença/obra nem entrega a resposta pronta."""
    path = PROJECT_ROOT / "glossario_sinonimos_busca_agente.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    resultado: dict[str, dict] = {}
    for chave, valor in raw.items():
        if chave.startswith("_") or not isinstance(valor, dict):
            continue
        resultado[fold_ortografico_lower(chave)] = valor
    return resultado


def _entradas_glossario_batidas(termo_folded: str) -> list[dict]:
    """Entradas do glossário de sinônimos de busca cuja chave bate (frase
    inteira, ou palavras significativas contidas em `termo_folded`)."""
    palavras_termo = set(_termos_significativos(termo_folded))
    batidas = []
    for chave_folded, entrada in _glossario_sinonimos_busca().items():
        palavras_chave = set(_termos_significativos(chave_folded))
        if chave_folded == termo_folded or (palavras_chave and palavras_chave <= palavras_termo):
            batidas.append(entrada)
    return batidas


def _termos_expandidos_por_glossario(termo_folded: str) -> list[str]:
    """Termos adicionais a buscar quando `termo_folded` bate com uma entrada
    do glossário de sinônimos de busca -- ver `_glossario_sinonimos_busca`."""
    extras: list[str] = []
    for entrada in _entradas_glossario_batidas(termo_folded):
        extras.extend(entrada.get("termos_relacionados") or [])
    return extras


def _significados_por_glossario(termo_folded: str) -> list[str]:
    """Definições NEUTRAS/ESTRUTURAIS (campo `significado`) das entradas do
    glossário que batem com `termo_folded` -- mostradas ao agente (via
    resultado de `buscar_termo`) para ele não confundir termos parecidos
    (ex.: 'plano' vs 'camada' vs 'nível'). Nunca inclui conclusão que
    responda a uma pergunta específica -- só o que cada termo representa
    estruturalmente, deixando a interpretação da pergunta ao próprio agente
    (ver `regra-suprema-tutela-pesquisa.mdc`)."""
    vistos: set[str] = set()
    significados: list[str] = []
    for entrada in _entradas_glossario_batidas(termo_folded):
        sig = entrada.get("significado")
        if sig and sig not in vistos:
            vistos.add(sig)
            significados.append(sig)
    return significados


def _ocorrencias_com_fronteira(padrao_termo: str, texto_folded: str) -> list[int]:
    return [m.start() for m in re.finditer(r"\b" + re.escape(padrao_termo) + r"\b", texto_folded)]


@lru_cache(maxsize=None)
def _ocorrencias_termo_em_arquivo(termo_folded: str, arquivo: str) -> tuple[int, ...]:
    """Mesma busca de `_ocorrencias_com_fronteira`, cacheada por par
    (termo, arquivo) -- achado 2026-07-30: uma consulta que bate no
    glossário de sinônimos de busca (ex. 'plano espiritual', 8 termos
    relacionados) chamava `_buscar_termo_unico` 9 vezes (1 pelo termo
    original + 8 pelos relacionados), cada vez varrendo os 145 arquivos do
    zero -- ~3000 varreduras regex repetidas, 7,5s numa única chamada de
    `buscar_termo`. Sem custo de correção (mesmo resultado, só não
    recalculado), já que o corpus não muda durante o processo."""
    texto_folded = _corpus_pt()[arquivo][1]
    return tuple(m.start() for m in re.finditer(r"\b" + re.escape(termo_folded) + r"\b", texto_folded))


def _buscar_termo_unico(termo_folded: str) -> list[dict]:
    """Busca UM termo/frase -- match por AND de palavras significativas em
    janela de proximidade, não mais substring contígua exata (§3.10, achado
    2026-07-30): o corpus usa 'planos: superior, médio e inferior' para a
    hierarquia do mundo espiritual, nunca a frase contígua 'plano espiritual
    inferior' -- correspondência de frase exata nunca batia, mesmo com o
    termo certo em mente, fazendo o agente reformular a pergunta sem nunca
    achar o trecho certo. Com 0-1 palavra significativa, o comportamento é
    idêntico ao original (a palavra tem que aparecer, com fronteira). Só usado
    pelo modo agenciado -- pt_direct/jp_direct usam outro mecanismo de busca,
    não tocado por esta mudança."""
    termos_sig = _termos_significativos(termo_folded)
    termos_busca = termos_sig if len(termos_sig) >= 2 else [termo_folded]

    candidatos: list[dict] = []
    for arquivo, (_, texto_folded) in _corpus_pt().items():
        ocorrencias_por_termo = [_ocorrencias_termo_em_arquivo(t, arquivo) for t in termos_busca]
        if not all(ocorrencias_por_termo):
            continue  # todas as palavras significativas precisam aparecer em algum lugar do arquivo

        idx_ancora = min(range(len(ocorrencias_por_termo)), key=lambda i: len(ocorrencias_por_termo[i]))
        outras = [ocorrencias_por_termo[i] for i in range(len(ocorrencias_por_termo)) if i != idx_ancora]

        for pos in ocorrencias_por_termo[idx_ancora]:
            if outras and not all(
                any(pos - JANELA_PROXIMIDADE <= p <= pos + JANELA_PROXIMIDADE for p in lista) for lista in outras
            ):
                continue
            janela_ini = max(0, pos - JANELA_PROXIMIDADE)
            janela_fim = min(len(texto_folded), pos + JANELA_PROXIMIDADE)
            vizinhanca = texto_folded[janela_ini:janela_fim]
            score = sum(vizinhanca.count(t) for t in termos_busca)
            candidatos.append({"arquivo": arquivo, "posicao": pos, "score": score})
    return candidatos


@lru_cache(maxsize=1)
def _bm25_index():
    """Índice BM25 em nível de ARQUIVO INTEIRO (não de janela) -- só entra
    como sinal COMPLEMENTAR de candidatura em `buscar_termo` (§3.12, achado
    2026-07-30): o filtro AND+janela de `_buscar_termo_unico` é preciso mas
    tem recall baixo quando a consulta é uma paráfrase cujas palavras estão
    espalhadas longe umas das outras no texto-fonte (ex.: pergunta cita
    'subir'/'descer'/'conforme'/'ações' e o texto real tem essas ideias em
    parágrafos distantes de um diálogo longo) -- nesse caso o AND+janela dá
    ZERO candidatos mesmo com o arquivo certo no acervo. BM25 por arquivo
    inteiro não exige proximidade nem todas as palavras presentes; pondera
    por raridade do termo no corpus (evita que palavras comuns como 'morte'
    dominem o placar). Testado (script `test_bm25.py`, não versionado):
    melhora a posição do arquivo-alvo de 195º/145 para 3º/145 numa consulta
    que antes dava zero resultados, sem regressão em consultas de controle
    sem relação temática nenhuma (câncer, agricultura natural, calamidades).
    Requer a biblioteca `rank_bm25` (já usada por `search_service.py` no
    pipeline pt_direct/jp_direct)."""
    from rank_bm25 import BM25Okapi

    arquivos = list(_corpus_pt().keys())
    tokenizado = [re.findall(r"\b\w{3,}\b", _corpus_pt()[a][1]) for a in arquivos]
    return arquivos, BM25Okapi(tokenizado)


def _bm25_top_arquivos(termo_folded: str, k: int = 20) -> list[str]:
    arquivos, bm25 = _bm25_index()
    termos = _termos_significativos(termo_folded) or [termo_folded]
    scores = bm25.get_scores(termos)
    ranking = sorted(range(len(arquivos)), key=lambda i: -scores[i])
    return [arquivos[i] for i in ranking[:k] if scores[i] > 0]


def _melhor_posicao_no_arquivo(termos_busca: list[str], arquivo: str) -> dict | None:
    """Dado que BM25 já decidiu que este arquivo é um candidato relevante
    (por conteúdo geral, não por proximidade), acha a melhor posição para
    mostrar como trecho -- mesma lógica de densidade local de
    `_buscar_termo_unico`, mas sem exigir que TODAS as palavras estejam na
    janela (aceita quantas houver por perto, pontua pela quantidade).

    Testa como âncora a posição de CADA ocorrência de CADA termo presente,
    não só as do termo mais raro -- bug real achado ao testar: com 'subir
    descer conforme ações', ancorar só em 'conforme' (o termo mais raro,
    1 ocorrência) nunca via que 'subir' e 'descer' se agrupam a poucos
    caracteres um do outro noutro ponto do texto (2 termos por perto ali,
    contra 1 na posição de 'conforme') -- perdia o melhor trecho por só
    olhar as posições do termo errado."""
    ocorrencias_por_termo = [_ocorrencias_termo_em_arquivo(t, arquivo) for t in termos_busca]
    presentes = [(i, occ) for i, occ in enumerate(ocorrencias_por_termo) if occ]
    if not presentes:
        return None
    melhor_pos, melhor_score = None, -1
    for _, ocorrencias in presentes:
        for pos in ocorrencias:
            janela_ini, janela_fim = pos - JANELA_PROXIMIDADE, pos + JANELA_PROXIMIDADE
            score = sum(1 for _, occ in presentes if any(janela_ini <= p <= janela_fim for p in occ))
            if score > melhor_score:
                melhor_score, melhor_pos = score, pos
    return {"posicao": melhor_pos, "score": melhor_score}


def buscar_termo(termo: str, max_resultados: int = 12) -> list[dict]:
    """Busca literal (tolerante a acento/maiúscula) do termo/frase em todo o
    acervo, ordenada por relevância -- corrige achados do estudo original:
    (a) §3.3, DeepSeek buscando 'cancer' sem acento batia só 3x contra 366x
    de 'câncer', jogando a busca para um canto errado do acervo; (b) §3.6,
    uma ordenação ingênua por ordem de arquivo podia cortar o trecho certo
    antes de ele aparecer quando o termo tem muitas ocorrências espalhadas;
    (c) §3.10, frases de 2+ palavras casam por AND de palavras em janela de
    proximidade, não mais substring contígua exata -- e frases com entrada
    no glossário de sinônimos de busca (`_glossario_sinonimos_busca`) também
    disparam busca pelos termos relacionados, mesclada aos resultados;
    (d) §3.12, candidatos adicionais via BM25 em nível de arquivo (ver
    `_bm25_index`) para arquivos que o AND+janela não capturou de jeito
    nenhum -- só complementa, nunca substitui o mecanismo original."""
    termo_folded = fold_ortografico_lower(termo)
    if not termo_folded:
        return []

    candidatos = _buscar_termo_unico(termo_folded)
    for extra in _termos_expandidos_por_glossario(termo_folded):
        candidatos.extend(_buscar_termo_unico(fold_ortografico_lower(extra)))

    arquivos_ja_achados = {c["arquivo"] for c in candidatos}
    termos_sig = _termos_significativos(termo_folded) or [termo_folded]
    if len(termos_sig) >= 2:
        for arquivo in _bm25_top_arquivos(termo_folded):
            if arquivo in arquivos_ja_achados:
                continue
            melhor = _melhor_posicao_no_arquivo(termos_sig, arquivo)
            if melhor and melhor["score"] > 0:
                candidatos.append({"arquivo": arquivo, "posicao": melhor["posicao"], "score": melhor["score"]})

    candidatos.sort(key=lambda c: (-c["score"], c["arquivo"], c["posicao"]))

    dedup: list[dict] = []
    vistos: set[tuple[str, int]] = set()
    for c in candidatos:
        chave = (c["arquivo"], c["posicao"] // 500)
        if chave in vistos:
            continue
        vistos.add(chave)
        texto_original = _corpus_pt()[c["arquivo"]][0]
        ini = max(0, c["posicao"] - 200)
        fim = min(len(texto_original), c["posicao"] + len(termo) + 300)
        dedup.append({"arquivo": c["arquivo"], "posicao": c["posicao"], "trecho": texto_original[ini:fim].strip()})
        if len(dedup) >= max_resultados:
            break
    return dedup


def ler_mais_contexto(arquivo: str, posicao: int, tamanho: int = 6000) -> str:
    entry = _corpus_pt().get(arquivo)
    if not entry:
        return f"Arquivo '{arquivo}' não encontrado no acervo."
    texto, _ = entry
    ini = max(0, posicao - 500)
    fim = min(len(texto), posicao + tamanho)
    return texto[ini:fim]


@lru_cache(maxsize=1)
def _indices_semanticos_pt():
    """Carrega o índice FAISS/embedding já usado pelo search_service (mesmo
    índice de produção, intfloat/multilingual-e5-large) -- reaproveitado,
    não duplicado. lru_cache evita recarregar o modelo/índice a cada
    chamada da ferramenta dentro do mesmo processo."""
    from .search_service import carregar_indices_pt

    return carregar_indices_pt()


def buscar_por_significado(consulta: str, k: int = 6) -> list[dict]:
    """Busca por SENTIDO via embedding, complementar a `buscar_termo` (que é
    busca literal de palavra). Achado real, 2026-08-06: um título oficial
    conhecido de fora do acervo (ex. IMMB) ou uma paráfrase de memória pode
    ter baixíssima sobreposição de palavra com a tradução própria do nosso
    corpus para o MESMO conteúdo (ex.: "O ser humano depende do seu
    pensamento" x "O Ser Humano é Segundo Seus Pensamentos") -- busca
    literal não acha nada, mesmo com o trecho presente. Validado: embedding
    achou o trecho certo em 1º lugar, com folga de score, num caso real
    onde a busca agenciada completa (40 rodadas) não achou nada.

    Retorna posição REAL no arquivo bruto (localizando o chunk dentro do
    texto original via correspondência de início), compatível com
    `ler_mais_contexto` -- igual ao formato de `buscar_termo`."""
    try:
        import faiss as _faiss
    except Exception:
        return []
    chunks_pt, metadados_pt, indice_pt, modelo_pt = _indices_semanticos_pt()
    if not chunks_pt:
        return []
    emb = modelo_pt.encode([consulta]).astype("float32")
    _faiss.normalize_L2(emb)
    distancias, indices = indice_pt.search(emb, k)
    corpus = _corpus_pt()
    resultados: list[dict] = []
    for dist, idx in zip(distancias[0], indices[0]):
        if idx < 0:
            continue
        meta = metadados_pt[idx]
        arquivo = meta.get("arquivo") or meta.get("arquivo_original")
        texto_chunk = chunks_pt[idx]
        if not arquivo or arquivo not in corpus or not texto_chunk:
            continue
        texto_original = corpus[arquivo][0]
        agulha = texto_chunk[:80].strip()
        posicao = texto_original.find(agulha) if agulha else -1
        if posicao < 0:
            posicao = 0
        ini = max(0, posicao - 100)
        fim = min(len(texto_original), posicao + 700)
        resultados.append(
            {
                "arquivo": arquivo,
                "posicao": posicao,
                "trecho": texto_original[ini:fim].strip(),
                "score_semantico": round(float(dist), 3),
            }
        )
    return resultados


def buscar_termo_enriquecido(termo: str, max_resultados: int = 12, k_semantico: int = 4) -> list[dict]:
    """`buscar_termo` (literal) + resultados semânticos complementares na
    MESMA chamada -- 2026-08-06, decisão do usuário: enriquecer toda busca
    por padrão, não só como fallback quando a busca literal falha por
    completo (regra 8a). Achado real ao testar a mesma pergunta várias
    vezes: a busca literal já encontrava BASTANTE conteúdo relevante (não
    falhava), mas nem sempre a citação específica que resolve uma
    ambiguidade -- variava de tentativa pra tentativa qual termo o modelo
    escolhia tentar. Isso não é o cenário que a regra 8a cobre (ela só
    dispara quando a busca literal não acha nada). Fundir os dois na
    mesma chamada, em vez de exigir uma ferramenta separada, evita o
    custo de uma rodada de rede inteira (~a fatia dominante do tempo,
    medido antes: 80-87% do tempo é chamada à API, só 13-19% é local) --
    o cálculo do embedding + busca FAISS é local e rápido (<1s medido).

    Resultados semânticos que caem muito perto de um resultado literal já
    encontrado (mesmo arquivo, posição a menos de 500 caracteres) são
    descartados -- não adianta mostrar o mesmo trecho duas vezes."""
    resultados = buscar_termo(termo, max_resultados=max_resultados)
    ja_vistos = {(r["arquivo"], r["posicao"] // 500) for r in resultados}
    try:
        semanticos = buscar_por_significado(termo, k=k_semantico)
    except Exception:
        semanticos = []
    for s in semanticos:
        chave = (s["arquivo"], s["posicao"] // 500)
        if chave in ja_vistos:
            continue
        ja_vistos.add(chave)
        resultados.append(
            {
                "arquivo": s["arquivo"],
                "posicao": s["posicao"],
                "trecho": s["trecho"],
                "via": "busca semântica (por sentido, não palavra exata) -- complementar aos resultados acima",
            }
        )
    return resultados


# --------------------------------------------------------------------------
# Variante japonesa (§4 do estudo: "não testado ainda, escopo explícito") --
# busca sobre o acervo ORIGINAL em japonês (textos_japones/*.txt), mesma
# arquitetura, sem normalização de acento (japonês não tem diacrítico) e
# sem fronteira de palavra \b (japonês não separa palavras por espaço, \b
# não se aplica de forma útil a esse script). A resposta final continua em
# português -- o modelo precisa traduzir fielmente qualquer trecho japonês
# encontrado, nunca reproduzir kanji/kana na resposta (mesma regra já usada
# em produção para jp_direct).
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _corpus_jp() -> dict[str, str]:
    corpus: dict[str, str] = {}
    for path in sorted(JAPONES_DIR.glob("*.txt")):
        try:
            corpus[path.name] = path.read_text(encoding="utf-8")
        except Exception:
            continue
    return corpus


def buscar_termo_jp(termo: str, max_resultados: int = 12) -> list[dict]:
    if not termo:
        return []
    termos_sig = [t for t in termo.split() if len(t) >= 2] or [termo]
    candidatos: list[dict] = []
    for arquivo, texto in _corpus_jp().items():
        inicio = 0
        while True:
            pos = texto.find(termo, inicio)
            if pos == -1:
                break
            janela_ini = max(0, pos - JANELA_PROXIMIDADE)
            janela_fim = min(len(texto), pos + len(termo) + JANELA_PROXIMIDADE)
            vizinhanca = texto[janela_ini:janela_fim]
            score = sum(vizinhanca.count(t) for t in termos_sig)
            candidatos.append({"arquivo": arquivo, "posicao": pos, "score": score})
            inicio = pos + len(termo)

    candidatos.sort(key=lambda c: (-c["score"], c["arquivo"], c["posicao"]))

    dedup: list[dict] = []
    vistos: set[tuple[str, int]] = set()
    for c in candidatos:
        chave = (c["arquivo"], c["posicao"] // 500)
        if chave in vistos:
            continue
        vistos.add(chave)
        texto = _corpus_jp()[c["arquivo"]]
        ini = max(0, c["posicao"] - 200)
        fim = min(len(texto), c["posicao"] + len(termo) + 300)
        dedup.append({"arquivo": c["arquivo"], "posicao": c["posicao"], "trecho": texto[ini:fim].strip()})
        if len(dedup) >= max_resultados:
            break
    return dedup


def ler_mais_contexto_jp(arquivo: str, posicao: int, tamanho: int = 6000) -> str:
    texto = _corpus_jp().get(arquivo)
    if not texto:
        return f"Arquivo '{arquivo}' não encontrado no acervo japonês."
    ini = max(0, posicao - 500)
    fim = min(len(texto), posicao + tamanho)
    return texto[ini:fim]


def executar_ferramenta_jp(nome: str, entrada: dict) -> dict:
    if nome == "buscar_termo":
        return {"resultados": buscar_termo_jp(entrada["termo"])}
    if nome == "ler_mais_contexto":
        return {"texto": ler_mais_contexto_jp(entrada["arquivo"], entrada["posicao"], entrada.get("tamanho", 6000))}
    return {"erro": f"ferramenta desconhecida: {nome}"}


def _arquivos_da_ferramenta_jp(nome: str, entrada: dict, resultado) -> set[str]:
    if nome == "buscar_termo" and isinstance(resultado, dict):
        return {r["arquivo"] for r in resultado.get("resultados", []) if r.get("arquivo")}
    if nome == "ler_mais_contexto":
        arquivo = entrada.get("arquivo")
        return {arquivo} if arquivo else set()
    return set()


def validar_citacoes_jp(resposta: str, arquivos_retornados: set[str]) -> list[str]:
    if not resposta:
        return []
    citados_reais = {arquivo for arquivo in _corpus_jp() if arquivo in resposta}
    return sorted(citados_reais - arquivos_retornados)


TOOLS_SCHEMA_JP = [
    {
        "type": "function",
        "function": {
            "name": "buscar_termo",
            "description": (
                "Busca literal (em japonês) de uma palavra ou frase em todo o acervo ORIGINAL "
                "japonês de Meishu-Sama. Retorna trechos ordenados por relevância, com o nome do "
                "arquivo e a posição. Se não encontrar nada relevante, tente de novo com um sinônimo "
                "ou termo japonês relacionado (kanji/kana) antes de desistir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "termo": {"type": "string", "description": "Palavra ou frase em japonês a buscar"},
                },
                "required": ["termo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ler_mais_contexto",
            "description": "Lê um trecho maior de um arquivo específico do acervo japonês, ao redor de uma posição já encontrada por buscar_termo. Se o documento já parece central ao tema mas o trecho lido não respondeu totalmente, prefira chamar de novo com uma posição MAIOR no mesmo arquivo (continuar lendo adiante) antes de trocar de termo de busca -- a explicação completa costuma continuar logo depois do trecho já lido, não em outro arquivo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "arquivo": {"type": "string"},
                    "posicao": {"type": "integer"},
                    "tamanho": {"type": "integer", "description": "Quantos caracteres ler (padrão 6000)"},
                },
                "required": ["arquivo", "posicao"],
            },
        },
    },
]


SYSTEM_PROMPT_JP_HEAD_TEMPLATE = """Você é um assistente que responde exclusivamente com base nos ensinamentos de Meishu-Sama, acessando o acervo ORIGINAL EM JAPONÊS através das ferramentas de busca fornecidas (os textos originais são em japonês; a tradução em português desses mesmos textos, em outro sistema, às vezes é incompleta -- por isso a busca aqui é direto no japonês).

REGRAS OBRIGATÓRIAS:
1. Você NÃO tem conhecimento confiável, prévio ou de treinamento sobre esses ensinamentos específicos -- responder de memória é proibido. Use SEMPRE as ferramentas antes de responder qualquer pergunta de conteúdo.
2. Busque em japonês (kanji/kana) -- traduza mentalmente o tema da pergunta para termos japoneses prováveis antes de chamar a ferramenta. Se a primeira busca não trouxer nada relevante, tente de novo com sinônimos ou termos japoneses relacionados antes de concluir que o acervo não tem a resposta.
3. Nunca invente, complete ou generalize além do que os trechos encontrados realmente dizem.
4. A RESPOSTA FINAL deve ser em {idioma}. Toda citação/trecho usado, mesmo encontrado em japonês, deve ser traduzido fielmente (não paráfrase livre) para {idioma} na resposta -- NUNCA inclua caracteres japoneses (kanji/kana) na resposta final, salvo se o usuário pedir explicitamente o texto original. Isso vale também para explicar a ETIMOLOGIA ou transliteração de um termo (ex.: "johrei vem de 浄霊") -- é proibido colar o kanji original entre parênteses ou dentro da frase mesmo nesse contexto; explique o significado só com palavras em {idioma} (ex.: "johrei, que significa 'purificação do espírito'"), nunca mostrando o caractere japonês em si. Nenhuma explicação de origem de palavra é motivo válido para incluir kanji/kana na resposta.
5. Cite a fonte (nome do arquivo) dos trechos usados na resposta EXATAMENTE como a ferramenta devolveu no campo "arquivo" -- nunca traduza, abrevie ou invente nome de série/coleção diferente do que foi literalmente retornado.
6. Se, mesmo após tentar termos diferentes, não encontrar nada relevante, diga isso claramente -- não force uma resposta genérica.
7. NÃO se contente com a primeira leitura plausível. Encontrar um trecho que parece responder a pergunta não é motivo para parar -- continue buscando e leia (ler_mais_contexto) os trechos genuinamente relevantes que aparecerem nos resultados, mesmo que já pareça ter uma resposta. Uma leitura posterior pode revelar uma distinção, exceção ou nuance que muda a resposta -- respostas incompletas por pressa são um risco maior do que gastar mais tempo buscando. Só considere a busca concluída quando as tentativas deixarem de trazer conteúdo genuinamente novo. ATENÇÃO A UM PADRÃO ESPECÍFICO: se um resultado vem de um arquivo cujo título/cabeçalho ou trecho mostrado deixa claro que o TEMA GERAL bate com a pergunta, mas o texto mostrado é só definição/descrição estrutural do assunto (ex.: explica os conceitos e a organização geral, sem tratar diretamente do caso ou da pergunta específica) -- isso é sinal forte de que a resposta real está em OUTRO PONTO DO MESMO ARQUIVO, não que o arquivo é irrelevante. Nesse caso, o próximo passo correto é chamar ler_mais_contexto nesse mesmo arquivo (inclusive em posições mais adiante do texto, não só ao redor da posição devolvida), não abandonar o arquivo e tentar um novo termo de busca.
8. Se a pergunta pedir a opinião, reação ou "o que ele diria" de Meishu-Sama sobre um evento ou tema POSTERIOR à sua morte (1955) que ele nunca comentou nos textos, você PODE construir uma inferência com base em princípios doutrinários reais do acervo (busque o tema de fundo -- não invente sem buscar), mas deve: (a) rotular explicitamente essa parte como "Inferência:" (ou o equivalente em {idioma}), nunca como citação ou posição documentada dele; (b) deixar claro que ele nunca se pronunciou sobre esse evento específico; (c) nunca misturar a inferência com uma citação literal sem essa separação clara.
8a. HIERARQUIA ENTRE PALAVRA ESCRITA E PALAVRA ORAL: todo o acervo é doutrina estabelecida (é só o que Meishu-Sama escolheu publicar em vida). Mas quando uma pergunta encontra trechos de fontes ESCRITAS (ensaios, artigos de periódico, livros doutrinários) e de fontes ORAIS (diálogos registrados -- coletâneas de perguntas e respostas) sobre o MESMO assunto, com enquadramentos diferentes: trate a fonte ESCRITA como a base doutrinária central, e a fonte ORAL como complemento/ampliação dela -- a fala oral está presa ao contexto do momento e do interlocutor específico, enquanto o texto escrito é a formulação mais deliberada e permanente do ensinamento. Isso NÃO muda a regra 10 (nunca fundir sem base textual) -- os enquadramentos continuam em temas/subtítulos separados -- mas ao decidir COM QUAL TEMA ABRIR a resposta e ao apresentar os temas, coloque a fonte escrita primeiro/como referência central, e enquadre a oral explicitamente como complementando/detalhando a partir dela, não como uma visão alternativa de peso igual. Se só existir um dos dois tipos sobre o assunto (só escrito, ou só oral), esse é a doutrina soberana por padrão, sem necessidade de aplicar essa hierarquia.
8b. DISCIPLINA DA FRASE DE ABERTURA: a abertura da resposta pesa mais do que o resto do texto -- muitos leitores só leem essa parte e param. NUNCA abra com uma afirmação categórica (ex. "Sim, ..."/"Não, ..." ou equivalente em {idioma}) decidida antes de você ter processado todos os trechos que vai usar -- isso é comum em geração de texto sequencial: começa-se a escrever com uma primeira impressão, e uma nuance ou contradição só aparece depois, no meio ou no fim da resposta, sem a abertura ser corrigida para refletir isso. Antes de escrever a primeira frase, finalize mentalmente qual é a síntese completa (incluindo qualquer nuance, exceção ou tensão entre trechos que você vai apresentar mais adiante) e só então escreva a abertura de acordo com essa síntese final -- nunca de acordo com a primeira impressão. Se a resposta plena for mista ou matizada (não um "sim" ou "não" limpo), a abertura já deve refletir essa complexidade, não simplificar para depois complicar.
8c. NUNCA DÊ RESPOSTA DETERMINÍSTICA EM CASO DE AMBIGUIDADE EXPLÍCITA OU IMPLÍCITA: se os trechos encontrados, tomados em conjunto, sustentam leituras diferentes ou aparentemente contraditórias sobre a mesma pergunta -- ambiguidade EXPLÍCITA (os próprios trechos discordam entre si) ou IMPLÍCITA (um termo da pergunta ou de um trecho admite mais de uma interpretação plausível, e a resposta muda dependendo de qual interpretação se usa) -- NUNCA feche a resposta com um "Sim" ou "Não" categórico (ou equivalente em {idioma}), nem na abertura (regra 8b) nem na conclusão. Apresente os enquadramentos como a regra 10 já pede (temas/subtítulos separados, cada um com sua citação), e feche reconhecendo abertamente que a resposta depende de como se interpreta o termo ou a pergunta, ou que o acervo sustenta mais de uma leitura -- sem escolher uma delas como "a resposta certa" por conta própria. Isso só deixa de valer quando um trecho específico resolve a ambiguidade de forma explícita (nesse caso, cite esse trecho como o que resolve, e a regra 8a sobre precedência escrita/oral se aplica quando for o caso).
"""

SYSTEM_PROMPT_JP_REGRA9_CITACOES_TEMPLATE = """9. FORMATO DA RESPOSTA -- explicação por tema, com citação confirmatória: divida a resposta nos temas/aspectos distintos que os trechos sustentam, cada um com um subtítulo curto (###). Em cada tema, explique PRIMEIRO em {idioma}, com suas próprias palavras (fiel ao sentido dos trechos) -- essa explicação é o conteúdo principal, nunca a citação. Logo depois da explicação de cada tema, inclua ao menos uma citação literal traduzida (entre aspas, com o nome do arquivo entre colchetes) que CONFIRME o que acabou de ser explicado -- a citação serve para comprovar, nunca para abrir o tema ou substituir a explicação. Um trecho de apoio já basta por tema. Proibido reunir todas as citações numa seção separada ao final.
"""

SYSTEM_PROMPT_JP_REGRA9_DIRETA_TEMPLATE = """9. FORMATO DA RESPOSTA -- explicação por tema, sem citação literal (não se aplica ao modo "na íntegra" da regra 5, que é reprodução literal): divida a resposta nos temas/aspectos distintos que os trechos sustentam, cada um com um subtítulo curto (###). Em cada tema, explique em {idioma}, com suas próprias palavras, fiel ao sentido dos trechos -- a precisão continua obrigatória (nada que os trechos não sustentem pode aparecer na resposta), mas NÃO é necessário transcrever nenhuma citação literal entre aspas nem indicar [arquivo.txt] no texto. Escreva como um texto corrido e conectado, não como uma lista de citações comentadas. NO MODO DIRETA, A REGRA 5 (citar a fonte) NÃO SE APLICA: é PROIBIDO mencionar o nome do arquivo em QUALQUER lugar ou formato da resposta -- nem entre colchetes, nem em lista/seção "Fontes"/"Referências" ao final, nem citado DENTRO da própria frase/prosa (ex.: "Meishu-Sama, em [nome de arquivo], diz que..." também é proibido, mesmo sem colchetes). O nome de arquivo deste acervo é em japonês (contém kanji) -- mencioná-lo violaria também a regra 4 sobre nunca incluir caracteres japoneses na resposta. Se sentir necessidade de indicar de onde vem a informação, use no máximo uma referência genérica e sem nome de arquivo (ex.: "segundo os ensinamentos de Meishu-Sama sobre o tema"), nunca o nome do arquivo.

9a. TAMANHO NO MODO DIRETA (2026-08-06, decisão do usuário: só se aplica aqui, nunca no modo com citações): a resposta final deve ter, no máximo, cerca de 2000 caracteres -- é uma restrição real, não uma sugestão solta. Para caber nisso: escolha só os 1-2 enquadramentos mais centrais e diretos ao tema perguntado, sem tentar cobrir todos os ângulos que a busca trouxe. Termine SEMPRE com um convite específico e concreto, em {idioma} (nomeando o assunto real que ficou de fora, nunca um convite genérico tipo "posso explicar mais se quiser") para o usuário perguntar mais sobre o que não coube -- o aprofundamento no modo Direta acontece pela conversa continuar, pergunta a pergunta, não numa única resposta que tenta caber tudo. EXCEÇÃO (2026-08-06): quando a regra 8c (nunca dar resposta determinística em ambiguidade) se aplicar -- ou seja, quando os trechos sustentarem leituras diferentes/contraditórias e não houver como resolver isso com uma resposta limpa --, o teto de 2000 caracteres pode ser ultrapassado o necessário para apresentar os enquadramentos separadamente, como a regra 8c exige. Mesmo nesse caso, a resposta deve continuar o mais objetiva possível -- cada enquadramento apresentado de forma direta e sem elaboração supérflua, nunca um pretexto para voltar a despejar tudo que a busca encontrou.
"""

SYSTEM_PROMPT_JP_TAIL = """10. PROIBIDO FUNDIR AFIRMAÇÕES DE FONTES DIFERENTES SEM BASE TEXTUAL: se dois trechos (de arquivos diferentes, ou de datas diferentes) descrevem o mesmo conceito de formas distintas ou aparentemente incompatíveis (ex.: um trecho diz que a causa de X é espiritual, outro diz que a causa de X é física/alimentar), NÃO os apresente como uma única explicação unificada, nem trate um como a "causa" do outro, a menos que algum trecho conecte os dois explicitamente. Cada fonte com um enquadramento diferente vira seu próprio SUBTÍTULO (###) na resposta, com sua própria citação -- não basta suavizar a redação com frases tipo "há duas camadas de explicação" ou "por um lado... por outro lado" DENTRO do mesmo tema; isso ainda é fundir. Se você notar que está prestes a escrever esse tipo de ressalva dentro de um único tema, é sinal de que precisa quebrar em dois subtítulos separados, não só suavizar o texto. Não invente elo causal ou complementaridade entre fontes que o próprio texto não faz. Isso vale mesmo quando as fontes usam a mesma palavra-chave (ex. "verdadeiro" X) para coisas que cada uma define de forma diferente. SE A RESPOSTA TIVER 2 OU MAIS TEMAS SEPARADOS POR ESTA REGRA, É PROIBIDO ESCREVER UM PARÁGRAFO DE "RESUMO GERAL" NO FINAL QUE TENTE COMPRIMIR TUDO NUMA FRASE SÓ -- é exatamente nesse resumo que a fusão sempre volta (ex. "o câncer verdadeiro é espiritual e vem da toxina da carne" reintroduz o elo que os temas separados evitaram). A separação por subtítulos já é suficiente; termine a resposta no último tema, sem parágrafo de fechamento que junte os enquadramentos de novo. EXCEÇÃO CONTROLADA: depois de separar os enquadramentos em temas distintos como acima, se houver uma forma de reconciliá-los apoiada no que os próprios trechos NÃO afirmam (ex.: nenhum dos dois menciona um limite de escopo -- tempo, vida, contexto -- que o outro pressupõe), você PODE acrescentar, depois dos temas separados, um bloco adicional rotulado "Inferência:" (regra 8) oferecendo essa reconciliação -- nunca como se o texto tivesse dito isso, sempre como leitura sua, claramente separada e justificada. Isso é diferente de inventar elo causal (proibido acima): ali você afirmaria que os trechos se conectam; aqui você declara abertamente que está oferecendo uma interpretação sua que os concilia, e explica o motivo.
"""


def _system_prompt_jp(idioma: str = "Português", *, com_citacoes: bool = True) -> str:
    # 2026-07-31: achado real -- a regra de idioma da resposta estava fixa
    # em português, e o parâmetro `language` do payload nunca chegava até
    # aqui, então qualquer idioma selecionado no app (que sempre cai em
    # jp_agentic, ver routes.py) devolvia a resposta em português mesmo
    # assim. Corrigido parametrizando as 2 regras que mencionam o idioma
    # de saída (4 e 9); o resto do prompt (contexto, regras de busca/
    # citação/inferência) não depende de idioma e fica igual.
    #
    # 2026-08-03: prompt separado em HEAD (regras 1-8, compartilhadas) +
    # regra 9 variável (com citação / direta -- modo "Direta"/"Com
    # citações" escolhido pelo usuário no composer) + TAIL (regra 10) --
    # assim qualquer ajuste futuro nas regras compartilhadas vale para os
    # dois modos automaticamente, sem duplicar texto.
    idioma = (idioma or "Português").strip() or "Português"
    regra9 = SYSTEM_PROMPT_JP_REGRA9_CITACOES_TEMPLATE if com_citacoes else SYSTEM_PROMPT_JP_REGRA9_DIRETA_TEMPLATE
    return (SYSTEM_PROMPT_JP_HEAD_TEMPLATE + regra9 + SYSTEM_PROMPT_JP_TAIL).format(idioma=idioma)


# Mantidos como constantes para compatibilidade com quem importa o texto
# pronto (ex. scripts de piloto) -- equivalentes a
# _system_prompt_jp("Português", com_citacoes=...).
SYSTEM_PROMPT_JP = _system_prompt_jp("Português", com_citacoes=True)
SYSTEM_PROMPT_JP_DIRETO = _system_prompt_jp("Português", com_citacoes=False)


def buscar_artigo_por_titulo(titulo: str) -> dict:
    """Reaproveita `find_best_article`/`load_article_chunks` -- já
    corrigidos nesta mesma sessão (116->3.788 artigos reconhecíveis) e já
    desacoplados do modelo de embedding (§3.8)."""
    from .teaching_article_service import find_best_article, load_article_chunks

    artigo = find_best_article(titulo, min_score=0.45)
    if not artigo:
        return {
            "encontrado": False,
            "motivo": (
                "Nenhum artigo com esse título foi encontrado com confiança suficiente. "
                "Tente buscar_termo com palavras-chave do tema em vez do título exato."
            ),
        }
    chunks, _ = load_article_chunks(artigo["id"])
    texto_completo = "\n\n".join(chunks)[:20000]
    return {
        "encontrado": True,
        "titulo": artigo["title"],
        "arquivo": artigo["arquivo"],
        "texto_completo": texto_completo,
    }


TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "buscar_termo",
            "description": (
                "Busca literal (tolerante a acento e maiúscula/minúscula) de uma palavra ou "
                "frase em todo o acervo de textos de Meishu-Sama, já enriquecida com alguns "
                "resultados complementares por SENTIDO (embedding) além dos literais -- não é "
                "preciso chamar buscar_por_significado à parte para obter esse complemento. "
                "Retorna trechos ordenados por relevância, com o nome do arquivo e a posição. "
                "Se não encontrar nada relevante, tente de novo com um sinônimo ou termo "
                "relacionado antes de desistir."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "termo": {"type": "string", "description": "Palavra ou frase a buscar"},
                },
                "required": ["termo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ler_mais_contexto",
            "description": "Lê um trecho maior de um arquivo específico, ao redor de uma posição já encontrada por buscar_termo. Se o documento já parece central ao tema mas o trecho lido não respondeu totalmente, prefira chamar de novo com uma posição MAIOR no mesmo arquivo (continuar lendo adiante) antes de trocar de termo de busca -- a explicação completa costuma continuar logo depois do trecho já lido, não em outro arquivo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "arquivo": {"type": "string"},
                    "posicao": {"type": "integer"},
                    "tamanho": {"type": "integer", "description": "Quantos caracteres ler (padrão 6000)"},
                },
                "required": ["arquivo", "posicao"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_artigo_por_titulo",
            "description": (
                "Busca um ensinamento/artigo específico pelo título aproximado e retorna o TEXTO "
                "COMPLETO dele. Use SÓ quando o usuário pedir EXPLICITAMENTE o texto/artigo 'na "
                "íntegra', 'completo', 'inteiro', ou citar um título específico pedindo para "
                "reproduzi-lo -- NUNCA para uma pergunta genérica de tema ou termo (ex.: uma única "
                "palavra como 'Johrei', ou 'o que é X', 'fale sobre X'), mesmo que essa palavra "
                "apareça no título de algum artigo do acervo por coincidência. Para perguntas de "
                "tema, use buscar_termo."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "titulo": {"type": "string", "description": "Título aproximado do ensinamento"},
                },
                "required": ["titulo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buscar_por_significado",
            "description": (
                "Busca por SENTIDO (embedding), não por palavra exata -- use como COMPLEMENTO a "
                "buscar_termo, nunca como primeira tentativa. Útil especificamente quando "
                "buscar_termo (inclusive com sinônimos) não encontrou nada relevante, mas você "
                "suspeita que o conteúdo existe sob outra formulação -- por exemplo, o usuário "
                "citou um título ou frase que parece vir de memória ou de uma fonte externa "
                "(título oficial de outra publicação, resumo de terceiro), que pode não bater "
                "palavra por palavra com a tradução própria deste acervo para o mesmo conteúdo. "
                "Retorna trechos ordenados por proximidade de sentido, não de palavra."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "consulta": {"type": "string", "description": "A frase ou pergunta cujo SENTIDO deve ser buscado"},
                },
                "required": ["consulta"],
            },
        },
    },
]


def _arquivos_da_ferramenta(nome: str, entrada: dict, resultado) -> set[str]:
    """Nomes de arquivo que uma chamada de ferramenta realmente devolveu --
    usado por `validar_citacoes` para detectar citação inventada (§3.4)."""
    if nome == "buscar_termo" and isinstance(resultado, dict):
        return {r["arquivo"] for r in resultado.get("resultados", []) if r.get("arquivo")}
    if nome == "ler_mais_contexto":
        arquivo = entrada.get("arquivo")
        return {arquivo} if arquivo else set()
    if nome == "buscar_artigo_por_titulo" and isinstance(resultado, dict):
        arquivo = resultado.get("arquivo")
        return {arquivo} if arquivo else set()
    if nome == "buscar_por_significado" and isinstance(resultado, dict):
        return {r["arquivo"] for r in resultado.get("resultados", []) if r.get("arquivo")}
    return set()


def executar_ferramenta(nome: str, entrada: dict) -> dict:
    if nome == "buscar_termo":
        termo = entrada["termo"]
        resultado = {"resultados": buscar_termo_enriquecido(termo)}
        significados = _significados_por_glossario(fold_ortografico_lower(termo))
        if significados:
            resultado["definicoes_de_termos"] = significados
        return resultado
    if nome == "ler_mais_contexto":
        return {"texto": ler_mais_contexto(entrada["arquivo"], entrada["posicao"], entrada.get("tamanho", 6000))}
    if nome == "buscar_artigo_por_titulo":
        return buscar_artigo_por_titulo(entrada["titulo"])
    if nome == "buscar_por_significado":
        return {"resultados": buscar_por_significado(entrada["consulta"])}
    return {"erro": f"ferramenta desconhecida: {nome}"}


def _fingerprint_texto(texto: str) -> str:
    """Hash curto de um trecho de texto -- usado para detectar estagnação
    (§3.9) por CONTEÚDO, não por nome de arquivo ou termo de busca (a mesma
    busca reformulada pode achar o mesmo trecho de sempre; o mesmo arquivo
    pode render texto genuinamente novo numa posição diferente)."""
    return hashlib.sha1(texto.strip().encode("utf-8", errors="ignore")).hexdigest()[:16]


def _fingerprints_da_ferramenta(nome: str, resultado) -> set[str]:
    """Fingerprints de conteúdo retornado por uma chamada de ferramenta --
    genérica para PT e JP, já que as três ferramentas devolvem a mesma forma
    de dict nos dois acervos (`resultados`/`trecho`, `texto`,
    `texto_completo`). Usada só para medir NOVIDADE (§3.9), não substitui
    `_arquivos_da_ferramenta`/`_arquivos_da_ferramenta_jp` (que servem para
    validar citação, §3.4)."""
    if not isinstance(resultado, dict):
        return set()
    if nome == "buscar_termo":
        return {_fingerprint_texto(r["trecho"]) for r in resultado.get("resultados", []) if r.get("trecho")}
    if nome == "ler_mais_contexto":
        texto = resultado.get("texto")
        return {_fingerprint_texto(texto)} if texto else set()
    if nome == "buscar_artigo_por_titulo":
        texto = resultado.get("texto_completo")
        return {_fingerprint_texto(texto)} if texto else set()
    if nome == "buscar_por_significado":
        return {_fingerprint_texto(r["trecho"]) for r in resultado.get("resultados", []) if r.get("trecho")}
    return set()


def _resposta_vazou_sintaxe_de_ferramenta(texto: str) -> bool:
    """Detecta um vazamento real achado ao testar o fallback de síntese
    forçada (§3.2, 2026-07-29): o deepseek-v4-flash pode devolver a sintaxe
    interna de tool-call como texto literal (tokens tipo
    '<｜｜DSML｜｜tool_calls>...<｜｜DSML｜｜invoke name="...">') em vez de prosa,
    mesmo depois do aviso explícito de que não há mais ferramenta disponível.
    Rede de segurança final -- nunca deve chegar ao usuário."""
    if not texto:
        return False
    return "｜｜" in texto and ("tool_calls" in texto or "invoke" in texto or "DSML" in texto)


def validar_citacoes(resposta: str, arquivos_retornados: set[str]) -> list[str]:
    """Nomes de arquivo citados na resposta que NÃO batem com nenhum arquivo
    realmente devolvido pelas ferramentas nesta conversa -- sinal de citação
    inventada (achado §3.4: o Haiku, no piloto, rotulou trechos do
    Gokōwa-roku como se fossem do periódico Hikari).

    Compara contra a lista real de nomes de arquivo do acervo (não uma
    regex genérica de ".txt") -- os nomes de arquivo deste corpus contêm
    pontuação japonesa (『』（）) e hífen que quebram fronteira de regex
    simples, gerando falso positivo (ex.: '3号.txt' extraído de
    '...『浄霊法講座』3号.txt', que na verdade é uma citação correta e
    completa). Best-effort: só cobre citação por nome de arquivo literal,
    não paráfrase de nome de série sem o nome do arquivo."""
    if not resposta:
        return []
    citados_reais = {arquivo for arquivo in _corpus_pt() if arquivo in resposta}
    return sorted(citados_reais - arquivos_retornados)


SYSTEM_PROMPT_HEAD = """Você é um assistente que responde exclusivamente com base nos ensinamentos de Meishu-Sama presentes no acervo, acessado através das ferramentas de busca fornecidas.

REGRAS OBRIGATÓRIAS:
1. Você NÃO tem conhecimento confiável, prévio ou de treinamento sobre esses ensinamentos específicos -- responder de memória é proibido. Use SEMPRE as ferramentas antes de responder qualquer pergunta de conteúdo.
2. Se a primeira busca não trouxer nada relevante, tente de novo com sinônimos, termos relacionados, ou uma palavra-chave diferente antes de concluir que o acervo não tem a resposta.
3. Nunca invente, complete ou generalize além do que os trechos encontrados realmente dizem.
4. Cite a fonte (nome do arquivo) dos trechos usados na resposta EXATAMENTE como a ferramenta devolveu no campo "arquivo" -- nunca traduza, abrevie ou invente nome de série/coleção/periódico diferente do que foi literalmente retornado.
5. USE buscar_artigo_por_titulo APENAS quando o usuário pedir EXPLICITAMENTE o texto completo de um ensinamento específico -- frases inequívocas como "na íntegra", "texto completo", "artigo inteiro", "reproduza todo o ensinamento", ou quando o usuário citar o TÍTULO exato de uma obra/artigo pedindo para vê-la. Uma pergunta genérica sobre um TEMA ou TERMO (ex.: uma única palavra como "Johrei", ou "o que é X", "fale sobre X") NUNCA é pedido de reprodução integral, mesmo que essa palavra apareça por coincidência no título de algum artigo do acervo -- nesse caso, busque e responda normalmente pelo tema (regra 9), sem despejar um artigo inteiro só porque o título bateu com uma palavra da pergunta. Na dúvida sobre a intenção do usuário, prefira o modo temático da regra 9; só use a reprodução integral quando o pedido de "tudo"/"completo"/"na íntegra" for inequívoco.
6. Se, mesmo após tentar termos diferentes, não encontrar nada relevante, diga isso claramente -- não force uma resposta genérica.
7. NÃO se contente com a primeira leitura plausível. Encontrar um trecho que parece responder a pergunta não é motivo para parar -- continue buscando e leia (ler_mais_contexto) os trechos genuinamente relevantes que aparecerem nos resultados, mesmo que já pareça ter uma resposta. Uma leitura posterior pode revelar uma distinção, exceção ou nuance que muda a resposta -- respostas incompletas por pressa são um risco maior do que gastar mais tempo buscando. Só considere a busca concluída quando as tentativas deixarem de trazer conteúdo genuinamente novo. ATENÇÃO A UM PADRÃO ESPECÍFICO: se um resultado vem de um arquivo cujo título/cabeçalho ou trecho mostrado deixa claro que o TEMA GERAL bate com a pergunta, mas o texto mostrado é só definição/descrição estrutural do assunto (ex.: explica os conceitos e a organização geral, sem tratar diretamente do caso ou da pergunta específica) -- isso é sinal forte de que a resposta real está em OUTRO PONTO DO MESMO ARQUIVO, não que o arquivo é irrelevante. Nesse caso, o próximo passo correto é chamar ler_mais_contexto nesse mesmo arquivo (inclusive em posições mais adiante do texto, não só ao redor da posição devolvida), não abandonar o arquivo e tentar um novo termo de busca.
8. Se a pergunta pedir a opinião, reação ou "o que ele diria" de Meishu-Sama sobre um evento ou tema POSTERIOR à sua morte (1955) que ele nunca comentou nos textos (ex.: eventos históricos, tecnologias ou pandemias posteriores a 1955), você PODE construir uma inferência com base em princípios doutrinários reais do acervo (busque o tema de fundo -- ex. epidemia, sofrimento, purificação -- não invente sem buscar), mas deve: (a) rotular explicitamente essa parte como "Inferência:", nunca como citação ou posição documentada dele; (b) deixar claro que ele nunca se pronunciou sobre esse evento específico; (c) nunca misturar a inferência com uma citação literal sem essa separação clara.
8a. Se buscar_termo (mesmo tentando sinônimos, regra 2) não encontrar nada relevante, mas a pergunta citar um título, frase ou formulação que parece vir de memória ou de uma fonte externa (ex.: o nome oficial de uma publicação, um resumo de terceiro) -- ou seja, algo que provavelmente EXISTE no acervo mas com vocabulário de tradução diferente do que a pergunta usa -- tente buscar_por_significado antes de concluir que o conteúdo não existe. Ela busca por sentido, não por palavra exata, e pode achar o trecho certo mesmo com baixíssima sobreposição de vocabulário.
8b. HIERARQUIA ENTRE PALAVRA ESCRITA E PALAVRA ORAL: todo o acervo é doutrina estabelecida (é só o que Meishu-Sama escolheu publicar em vida). Mas quando uma pergunta encontra trechos de fontes ESCRITAS (ensaios, artigos de periódico, livros doutrinários) e de fontes ORAIS (diálogos registrados -- coletâneas de perguntas e respostas) sobre o MESMO assunto, com enquadramentos diferentes: trate a fonte ESCRITA como a base doutrinária central, e a fonte ORAL como complemento/ampliação dela -- a fala oral está presa ao contexto do momento e do interlocutor específico, enquanto o texto escrito é a formulação mais deliberada e permanente do ensinamento. Isso NÃO muda a regra 10 (nunca fundir sem base textual) -- os enquadramentos continuam em temas/subtítulos separados -- mas ao decidir COM QUAL TEMA ABRIR a resposta e ao apresentar os temas, coloque a fonte escrita primeiro/como referência central, e enquadre a oral explicitamente como complementando/detalhando a partir dela, não como uma visão alternativa de peso igual. Se só existir um dos dois tipos sobre o assunto (só escrito, ou só oral), esse é a doutrina soberana por padrão, sem necessidade de aplicar essa hierarquia.
8c. DISCIPLINA DA FRASE DE ABERTURA: a abertura da resposta pesa mais do que o resto do texto -- muitos leitores só leem essa parte e param. NUNCA abra com uma afirmação categórica (ex. "Sim, ..."/"Não, ...") decidida antes de você ter processado todos os trechos que vai usar -- isso é comum em geração de texto sequencial: começa-se a escrever com uma primeira impressão, e uma nuance ou contradição só aparece depois, no meio ou no fim da resposta, sem a abertura ser corrigida para refletir isso. Antes de escrever a primeira frase, finalize mentalmente qual é a síntese completa (incluindo qualquer nuance, exceção ou tensão entre trechos que você vai apresentar mais adiante) e só então escreva a abertura de acordo com essa síntese final -- nunca de acordo com a primeira impressão. Se a resposta plena for mista ou matizada (não um "sim" ou "não" limpo), a abertura já deve refletir essa complexidade, não simplificar para depois complicar.
8d. NUNCA DÊ RESPOSTA DETERMINÍSTICA EM CASO DE AMBIGUIDADE EXPLÍCITA OU IMPLÍCITA: se os trechos encontrados, tomados em conjunto, sustentam leituras diferentes ou aparentemente contraditórias sobre a mesma pergunta -- ambiguidade EXPLÍCITA (os próprios trechos discordam entre si) ou IMPLÍCITA (um termo da pergunta ou de um trecho admite mais de uma interpretação plausível, e a resposta muda dependendo de qual interpretação se usa) -- NUNCA feche a resposta com um "Sim" ou "Não" categórico, nem na abertura (regra 8c) nem na conclusão. Apresente os enquadramentos como a regra 10 já pede (temas/subtítulos separados, cada um com sua citação), e feche reconhecendo abertamente que a resposta depende de como se interpreta o termo ou a pergunta, ou que o acervo sustenta mais de uma leitura -- sem escolher uma delas como "a resposta certa" por conta própria. Isso só deixa de valer quando um trecho específico resolve a ambiguidade de forma explícita (nesse caso, cite esse trecho como o que resolve, e a regra 8b sobre precedência escrita/oral se aplica quando for o caso).
"""

SYSTEM_PROMPT_REGRA9_CITACOES = """9. FORMATO DA RESPOSTA -- explicação por tema, com citação confirmatória (não se aplica ao modo "na íntegra" da regra 5, que é reprodução literal): divida a resposta nos temas/aspectos distintos que os trechos sustentam, cada um com um subtítulo curto (###). Em cada tema, explique PRIMEIRO com suas próprias palavras (fiel ao sentido dos trechos) -- essa explicação é o conteúdo principal, nunca a citação. Logo depois da explicação de cada tema, inclua ao menos uma citação literal (entre aspas, com o nome do arquivo entre colchetes) que CONFIRME o que acabou de ser explicado -- a citação serve para comprovar, nunca para abrir o tema ou substituir a explicação. Um trecho de apoio já basta por tema. Proibido reunir todas as citações numa seção separada ao final.
"""

SYSTEM_PROMPT_REGRA9_DIRETA = """9. FORMATO DA RESPOSTA -- explicação por tema, sem citação literal (não se aplica ao modo "na íntegra" da regra 5, que é reprodução literal): divida a resposta nos temas/aspectos distintos que os trechos sustentam, cada um com um subtítulo curto (###). Em cada tema, explique com suas próprias palavras, fiel ao sentido dos trechos -- a precisão continua obrigatória (nada que os trechos não sustentem pode aparecer na resposta), mas NÃO é necessário transcrever nenhuma citação literal entre aspas nem indicar [arquivo.txt] no texto. Escreva como um texto corrido e conectado, não como uma lista de citações comentadas. NO MODO DIRETA, A REGRA 4 (citar a fonte) NÃO SE APLICA: é PROIBIDO mencionar o nome do arquivo em QUALQUER lugar ou formato da resposta -- nem entre colchetes, nem em lista/seção "Fontes"/"Referências" ao final, nem citado DENTRO da própria frase/prosa (ex.: "Meishu-Sama, em [nome de arquivo], diz que..." também é proibido, mesmo sem colchetes). O nome de arquivo deste acervo é em japonês (contém kanji) -- mencioná-lo também introduziria caracteres japoneses soltos na resposta, o que nunca deve acontecer. Se sentir necessidade de indicar de onde vem a informação, use no máximo uma referência genérica e sem nome de arquivo (ex.: "segundo os ensinamentos de Meishu-Sama sobre o tema"), nunca o nome do arquivo.

9a. TAMANHO NO MODO DIRETA (2026-08-06, decisão do usuário: só se aplica aqui, nunca no modo com citações): a resposta final deve ter, no máximo, cerca de 2000 caracteres -- é uma restrição real, não uma sugestão solta. Para caber nisso: escolha só os 1-2 enquadramentos mais centrais e diretos ao tema perguntado, sem tentar cobrir todos os ângulos que a busca trouxe. Termine SEMPRE com um convite específico e concreto (nomeando o assunto real que ficou de fora, nunca um convite genérico tipo "posso explicar mais se quiser") para o usuário perguntar mais sobre o que não coube -- o aprofundamento no modo Direta acontece pela conversa continuar, pergunta a pergunta, não numa única resposta que tenta caber tudo. EXCEÇÃO (2026-08-06): quando a regra 8d (nunca dar resposta determinística em ambiguidade) se aplicar -- ou seja, quando os trechos sustentarem leituras diferentes/contraditórias e não houver como resolver isso com uma resposta limpa --, o teto de 2000 caracteres pode ser ultrapassado o necessário para apresentar os enquadramentos separadamente, como a regra 8d exige. Mesmo nesse caso, a resposta deve continuar o mais objetiva possível -- cada enquadramento apresentado de forma direta e sem elaboração supérflua, nunca um pretexto para voltar a despejar tudo que a busca encontrou.
"""

SYSTEM_PROMPT_TAIL = """10. PROIBIDO FUNDIR AFIRMAÇÕES DE FONTES DIFERENTES SEM BASE TEXTUAL: se dois trechos (de arquivos diferentes, ou de datas diferentes) descrevem o mesmo conceito de formas distintas ou aparentemente incompatíveis (ex.: um trecho diz que a causa de X é espiritual, outro diz que a causa de X é física/alimentar), NÃO os apresente como uma única explicação unificada, nem trate um como a "causa" do outro, a menos que algum trecho conecte os dois explicitamente. Cada fonte com um enquadramento diferente vira seu próprio SUBTÍTULO (###) na resposta, com sua própria citação -- não basta suavizar a redação com frases tipo "há duas camadas de explicação" ou "por um lado... por outro lado" DENTRO do mesmo tema; isso ainda é fundir. Se você notar que está prestes a escrever esse tipo de ressalva dentro de um único tema, é sinal de que precisa quebrar em dois subtítulos separados, não só suavizar o texto. Não invente elo causal ou complementaridade entre fontes que o próprio texto não faz. Isso vale mesmo quando as fontes usam a mesma palavra-chave (ex. "verdadeiro" X) para coisas que cada uma define de forma diferente. SE A RESPOSTA TIVER 2 OU MAIS TEMAS SEPARADOS POR ESTA REGRA, É PROIBIDO ESCREVER UM PARÁGRAFO DE "RESUMO GERAL" NO FINAL QUE TENTE COMPRIMIR TUDO NUMA FRASE SÓ -- é exatamente nesse resumo que a fusão sempre volta (ex. "o câncer verdadeiro é espiritual e vem da toxina da carne" reintroduz o elo que os temas separados evitaram). A separação por subtítulos já é suficiente; termine a resposta no último tema, sem parágrafo de fechamento que junte os enquadramentos de novo. EXCEÇÃO CONTROLADA: depois de separar os enquadramentos em temas distintos como acima, se houver uma forma de reconciliá-los apoiada no que os próprios trechos NÃO afirmam (ex.: nenhum dos dois menciona um limite de escopo -- tempo, vida, contexto -- que o outro pressupõe), você PODE acrescentar, depois dos temas separados, um bloco adicional rotulado "Inferência:" (mesmo rótulo da regra 8) oferecendo essa reconciliação -- nunca como se o texto tivesse dito isso, sempre como leitura sua, claramente separada e justificada. Isso é diferente de inventar elo causal (proibido acima): ali você afirmaria que os trechos se conectam; aqui você declara abertamente que está oferecendo uma interpretação sua que os concilia, e explica o motivo.
"""

# 2026-08-03: prompt separado em HEAD (regras 1-8, compartilhadas) + regra 9
# variável (com citação / direta -- modo "Direta"/"Com citações" escolhido
# pelo usuário no composer) + TAIL (regra 10), mesma estrutura do lado JP
# acima -- qualquer ajuste futuro nas regras compartilhadas vale para os
# dois modos automaticamente, sem duplicar texto.
SYSTEM_PROMPT = SYSTEM_PROMPT_HEAD + SYSTEM_PROMPT_REGRA9_CITACOES + SYSTEM_PROMPT_TAIL
SYSTEM_PROMPT_DIRETO = SYSTEM_PROMPT_HEAD + SYSTEM_PROMPT_REGRA9_DIRETA + SYSTEM_PROMPT_TAIL


def _client():
    from .ai_service import _client as _deepseek_client

    return _deepseek_client()


def responder_agentico_deepseek(
    pergunta: str,
    historico: list[dict] | None = None,
    *,
    modelo: str = "deepseek-v4-flash",
    max_rodadas_busca: int = LIMITE_SEGURANCA_RODADAS,
    max_tokens: int = 8000,
    tools_schema: list[dict] = TOOLS_SCHEMA,
    system_prompt: str = SYSTEM_PROMPT,
    executor_fn=executar_ferramenta,
    arquivos_extractor_fn=_arquivos_da_ferramenta,
    validador_citacoes_fn=validar_citacoes,
    on_deep_search=None,
) -> dict:
    """Laço agenciado real. Decisão do usuário (2026-07-29): NÃO existe mais
    orçamento de busca como limite de trabalho normal -- é o próprio modelo
    quem decide quando parar (regras 2/6/7 do SYSTEM_PROMPT: tentar
    sinônimos antes de desistir, parar assim que tiver material suficiente,
    e dizer explicitamente quando não encontrar nada em vez de forçar
    resposta genérica). `max_rodadas_busca` agora é só uma rede de
    segurança contra loop descontrolado -- se for atingida, é sinal de
    anomalia (bug/loop), não de "pergunta difícil que precisava de mais
    orçamento", e o resultado ainda assim sintetiza com o que já foi
    encontrado em vez de devolver uma resposta vazia.

    Parametrizado (tools/prompt/executor) para poder apontar para o acervo
    PT (padrão) ou JP (`responder_agentico_deepseek_jp`) sem duplicar o
    laço inteiro.

    `on_deep_search`: callback opcional, sem argumentos, chamado UMA vez
    (2026-07-31) quando a busca passa de `RODADAS_AVISO_BUSCA_PROFUNDA`
    rodadas sem resposta pronta -- só para o chamador avisar o usuário que
    a pesquisa vai continuar mais a fundo. Não influencia em nada a busca
    em si (mesma decisão de parar/continuar de sempre)."""
    client = _client()
    messages = [{"role": "system", "content": system_prompt}] + list(historico or []) + [{"role": "user", "content": pergunta}]
    total_in = total_out = 0
    rodadas_busca = 0
    chamadas_ferramenta: list[str] = []
    arquivos_retornados: set[str] = set()
    fingerprints_vistos: set[str] = set()
    rodadas_sem_novidade = 0
    esgotou_orcamento_busca = False
    parou_por_estagnacao = False
    esgotou_tempo_busca = False
    t0 = time.time()
    resposta_final = ""
    truncada = False

    while True:
        if rodadas_busca >= max_rodadas_busca:
            # Rede de segurança atingida (LIMITE_SEGURANCA_RODADAS) sem o
            # modelo ter parado sozinho nem a estagnação (abaixo) ter
            # disparado antes -- em uso normal não deveria acontecer.
            esgotou_orcamento_busca = True
            break

        if time.time() - t0 >= LIMITE_SEGURANCA_SEGUNDOS:
            # 2026-08-06: rede de segurança por tempo decorrido -- ver nota
            # em LIMITE_SEGURANCA_SEGUNDOS. Independente da contagem de
            # rodada, protege contra o timeout real do servidor (gunicorn
            # --timeout 180) quando rodadas individuais demoram mais que o
            # normal (variância documentada da API DeepSeek).
            esgotou_tempo_busca = True
            break

        rodadas_busca += 1
        if rodadas_busca == RODADAS_AVISO_BUSCA_PROFUNDA and on_deep_search is not None:
            try:
                on_deep_search()
            except Exception:
                pass  # aviso de UX nunca deve derrubar a busca em si
        resp = client.chat.completions.create(model=modelo, max_tokens=max_tokens, messages=messages, tools=tools_schema)
        usage = resp.usage
        total_in += usage.prompt_tokens
        total_out += usage.completion_tokens
        choice = resp.choices[0]
        msg = choice.message

        if choice.finish_reason == "tool_calls" and msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content, "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
            novidade_nesta_rodada = False
            for tc in msg.tool_calls:
                nome = tc.function.name
                try:
                    entrada = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    entrada = {}
                chamadas_ferramenta.append(f"{nome}({json.dumps(entrada, ensure_ascii=False)})")
                resultado = executor_fn(nome, entrada)
                arquivos_retornados |= arquivos_extractor_fn(nome, entrada, resultado)
                fps = _fingerprints_da_ferramenta(nome, resultado)
                if fps - fingerprints_vistos:
                    novidade_nesta_rodada = True
                fingerprints_vistos |= fps
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(resultado, ensure_ascii=False)[:TAMANHO_MAX_RESULTADO_FERRAMENTA],
                    }
                )

            # §3.9: rendimento decrescente -- N rodadas seguidas sem NENHUM
            # fragmento de texto novo (fingerprint de conteúdo, não nome de
            # arquivo) é sinal estrutural de loop de reformulação vazio.
            # Reler mais contexto de um arquivo já visto não penaliza por si
            # só, desde que o texto lido em si seja novo.
            rodadas_sem_novidade = 0 if novidade_nesta_rodada else rodadas_sem_novidade + 1
            if rodadas_sem_novidade >= LIMITE_ESTAGNACAO_RODADAS:
                parou_por_estagnacao = True
                break
            continue

        resposta_final = msg.content or ""
        truncada = choice.finish_reason == "length"
        break

    if esgotou_orcamento_busca or parou_por_estagnacao or esgotou_tempo_busca:
        # Força síntese com o que já foi encontrado, nunca resposta vazia --
        # mesmo mecanismo para as três causas (teto de rodadas, teto de
        # tempo OU estagnação detectada). Achado real ao testar: só remover "tools" da
        # chamada (ou usar tool_choice="none" com tools ainda presentes) NÃO
        # basta -- o deepseek-v4-flash "vaza" a sintaxe interna de tool-call
        # como texto literal (tokens <｜｜DSML｜｜tool_calls>...) mesmo sem
        # "tools" no payload. Só parou de acontecer ao acrescentar uma
        # mensagem explícita de usuário avisando que não há mais ferramenta
        # disponível -- comportamento específico deste modelo, não
        # documentado, achado por teste direto (2026-07-29).
        messages.append(
            {
                "role": "user",
                "content": (
                    "Nenhuma ferramenta está mais disponível agora. Com base SOMENTE nos trechos já "
                    "encontrados acima, escreva a resposta final em texto corrido, sem tentar chamar "
                    "nenhuma função ou ferramenta."
                ),
            }
        )
        resp = client.chat.completions.create(model=modelo, max_tokens=max_tokens, messages=messages)
        usage = resp.usage
        total_in += usage.prompt_tokens
        total_out += usage.completion_tokens
        choice = resp.choices[0]
        resposta_final = (choice.message.content or "").strip() or (
            "Não consegui sintetizar uma resposta com o material buscado -- tente reformular a pergunta."
        )
        truncada = choice.finish_reason == "length"

    if truncada:
        # 2026-08-06: achado real, reproduzido em teste direto -- às vezes
        # UMA ÚNICA chamada (natural ou de síntese forçada acima) estoura
        # max_tokens=8000 no meio da geração (finish_reason="length") e o
        # texto fica cortado abruptamente, mesmo com o teto de tempo/rodada
        # (LIMITE_SEGURANCA_SEGUNDOS/RODADAS) nunca tendo sido atingido --
        # é um estouro de UMA chamada, não de rodadas acumuladas, então
        # aquele fix não cobre este caso. Em vez de aceitar o texto cortado
        # como resposta final, tenta 1x mais pedindo explicitamente uma
        # resposta mais concisa que caiba inteira -- sem tools, sem repetir
        # o texto cortado no histórico (nunca foi anexado a `messages`).
        messages.append(
            {
                "role": "user",
                "content": (
                    "Sua resposta anterior foi cortada por exceder o limite de tamanho antes de "
                    "terminar. Responda de novo, do zero, de forma mais concisa (escolha só os "
                    "pontos mais centrais para caber inteira dentro do limite), sem tentar chamar "
                    "nenhuma função ou ferramenta."
                ),
            }
        )
        resp = client.chat.completions.create(model=modelo, max_tokens=max_tokens, messages=messages)
        usage = resp.usage
        total_in += usage.prompt_tokens
        total_out += usage.completion_tokens
        choice = resp.choices[0]
        nova_resposta = (choice.message.content or "").strip()
        if nova_resposta:
            resposta_final = nova_resposta
            truncada = choice.finish_reason == "length"
        # se a 2ª tentativa também vier vazia, mantém o resultado da 1ª
        # (mesmo truncado) em vez de substituir por nada -- nunca piora.

    vazamento_sintaxe_ferramenta = _resposta_vazou_sintaxe_de_ferramenta(resposta_final)
    if vazamento_sintaxe_ferramenta:
        resposta_final = "Não consegui sintetizar uma resposta com o material buscado -- tente reformular a pergunta."

    tempo = time.time() - t0
    preco = PRECOS.get(modelo, {"entrada": 0, "saida": 0})
    custo = (total_in * preco["entrada"] + total_out * preco["saida"]) / 1_000_000
    citacoes_suspeitas = validador_citacoes_fn(resposta_final, arquivos_retornados)

    return {
        "resposta": resposta_final,
        "truncada": truncada,
        "esgotou_orcamento_busca": esgotou_orcamento_busca,
        "esgotou_tempo_busca": esgotou_tempo_busca,
        "parou_por_estagnacao": parou_por_estagnacao,
        "vazamento_sintaxe_ferramenta": vazamento_sintaxe_ferramenta,
        "tempo": round(tempo, 1),
        "rodadas": rodadas_busca,
        "chamadas_ferramenta": chamadas_ferramenta,
        "citacoes_suspeitas": citacoes_suspeitas,
        "tokens_entrada": total_in,
        "tokens_saida": total_out,
        "custo": round(custo, 5),
        "modelo": modelo,
    }


def responder_agentico_deepseek_jp(
    pergunta: str,
    historico: list[dict] | None = None,
    *,
    modelo: str = "deepseek-v4-flash",
    max_rodadas_busca: int = LIMITE_SEGURANCA_RODADAS,
    max_tokens: int = 8000,
    idioma: str = "Português",
    com_citacoes: bool = True,
    on_deep_search=None,
) -> dict:
    """Mesmo laço agenciado, mas buscando no acervo ORIGINAL japonês
    (`textos_japones/*.txt`) em vez do PT -- cobre o item explicitamente
    não testado no estudo original (§4: "jp_direct... não foi tocado nem
    testado com busca agenciada"). Sem `buscar_artigo_por_titulo` (não há
    equivalente japonês de `find_best_article` ainda) -- só busca literal +
    leitura de contexto.

    `idioma`: idioma da resposta final (a busca em si continua sempre em
    japonês, regra 2). Usado por qualquer idioma que não seja português
    no app (ver routes.py) -- default "Português" preserva o comportamento
    de sempre para quem já usa o app em português.

    `com_citacoes`: escolhe a regra 9 (formato "Direta" sem citação literal
    vs. "Com citações") -- default True preserva o comportamento anterior
    para quem chama sem especificar (scripts de piloto); `routes.py` passa
    o valor explícito conforme o modo escolhido pelo usuário no app."""
    return responder_agentico_deepseek(
        pergunta,
        historico,
        modelo=modelo,
        max_rodadas_busca=max_rodadas_busca,
        max_tokens=max_tokens,
        tools_schema=TOOLS_SCHEMA_JP,
        system_prompt=_system_prompt_jp(idioma, com_citacoes=com_citacoes),
        executor_fn=executar_ferramenta_jp,
        arquivos_extractor_fn=_arquivos_da_ferramenta_jp,
        validador_citacoes_fn=validar_citacoes_jp,
        on_deep_search=on_deep_search,
    )
