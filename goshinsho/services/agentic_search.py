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

# §3.9: quantas rodadas CONSECUTIVAS de chamada de ferramenta sem nenhum
# fragmento de texto genuinamente novo (fingerprint de conteúdo) contam como
# "estagnação" e forçam a síntese mais cedo. Escolhido 3, não 1: uma única
# rodada sem novidade é esperada e normal (o próprio SYSTEM_PROMPT, regra 2,
# instrui tentar pelo menos um sinônimo antes de desistir -- cortar em 1
# penalizaria exatamente o comportamento pedido); 3 consecutivas sem NENHUM
# conteúdo novo é um sinal estrutural forte de loop de reformulação vazio,
# sem depender do tema da pergunta.
LIMITE_ESTAGNACAO_RODADAS = 3
JANELA_PROXIMIDADE = 400
TAMANHO_MAX_RESULTADO_FERRAMENTA = 8000

# Preços por 1M tokens -- aproximados em 2026-07-29, conferir antes de usar
# para decisão financeira real (mesma ressalva do piloto).
PRECOS = {
    "deepseek-v4-flash": {"entrada": 0.28, "saida": 0.42},
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
        ocorrencias_por_termo = [_ocorrencias_com_fronteira(t, texto_folded) for t in termos_busca]
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


def _melhor_posicao_no_arquivo(termos_busca: list[str], texto_folded: str) -> dict | None:
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
    ocorrencias_por_termo = [_ocorrencias_com_fronteira(t, texto_folded) for t in termos_busca]
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
            melhor = _melhor_posicao_no_arquivo(termos_sig, _corpus_pt()[arquivo][1])
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


SYSTEM_PROMPT_JP = """Você é um assistente que responde exclusivamente com base nos ensinamentos de Meishu-Sama, acessando o acervo ORIGINAL EM JAPONÊS através das ferramentas de busca fornecidas (os textos originais são em japonês; a tradução em português desses mesmos textos, em outro sistema, às vezes é incompleta -- por isso a busca aqui é direto no japonês).

REGRAS OBRIGATÓRIAS:
1. Você NÃO tem conhecimento confiável, prévio ou de treinamento sobre esses ensinamentos específicos -- responder de memória é proibido. Use SEMPRE as ferramentas antes de responder qualquer pergunta de conteúdo.
2. Busque em japonês (kanji/kana) -- traduza mentalmente o tema da pergunta para termos japoneses prováveis antes de chamar a ferramenta. Se a primeira busca não trouxer nada relevante, tente de novo com sinônimos ou termos japoneses relacionados antes de concluir que o acervo não tem a resposta.
3. Nunca invente, complete ou generalize além do que os trechos encontrados realmente dizem.
4. A RESPOSTA FINAL deve ser em português. Toda citação/trecho usado, mesmo encontrado em japonês, deve ser traduzido fielmente (não paráfrase livre) para português na resposta -- NUNCA inclua caracteres japoneses (kanji/kana) na resposta final, salvo se o usuário pedir explicitamente o texto original.
5. Cite a fonte (nome do arquivo) dos trechos usados na resposta EXATAMENTE como a ferramenta devolveu no campo "arquivo" -- nunca traduza, abrevie ou invente nome de série/coleção diferente do que foi literalmente retornado.
6. Se, mesmo após tentar termos diferentes, não encontrar nada relevante, diga isso claramente -- não force uma resposta genérica.
7. NÃO se contente com a primeira leitura plausível. Encontrar um trecho que parece responder a pergunta não é motivo para parar -- continue buscando e leia (ler_mais_contexto) os trechos genuinamente relevantes que aparecerem nos resultados, mesmo que já pareça ter uma resposta. Uma leitura posterior pode revelar uma distinção, exceção ou nuance que muda a resposta -- respostas incompletas por pressa são um risco maior do que gastar mais tempo buscando. Só considere a busca concluída quando as tentativas deixarem de trazer conteúdo genuinamente novo. ATENÇÃO A UM PADRÃO ESPECÍFICO: se um resultado vem de um arquivo cujo título/cabeçalho ou trecho mostrado deixa claro que o TEMA GERAL bate com a pergunta, mas o texto mostrado é só definição/descrição estrutural do assunto (ex.: explica os conceitos e a organização geral, sem tratar diretamente do caso ou da pergunta específica) -- isso é sinal forte de que a resposta real está em OUTRO PONTO DO MESMO ARQUIVO, não que o arquivo é irrelevante. Nesse caso, o próximo passo correto é chamar ler_mais_contexto nesse mesmo arquivo (inclusive em posições mais adiante do texto, não só ao redor da posição devolvida), não abandonar o arquivo e tentar um novo termo de busca.
8. Se a pergunta pedir a opinião, reação ou "o que ele diria" de Meishu-Sama sobre um evento ou tema POSTERIOR à sua morte (1955) que ele nunca comentou nos textos, você PODE construir uma inferência com base em princípios doutrinários reais do acervo (busque o tema de fundo -- não invente sem buscar), mas deve: (a) rotular explicitamente essa parte como "Inferência:", nunca como citação ou posição documentada dele; (b) deixar claro que ele nunca se pronunciou sobre esse evento específico; (c) nunca misturar a inferência com uma citação literal sem essa separação clara.
9. FORMATO DA RESPOSTA -- explicação por tema, com citação confirmatória: divida a resposta nos temas/aspectos distintos que os trechos sustentam, cada um com um subtítulo curto (###). Em cada tema, explique PRIMEIRO em português, com suas próprias palavras (fiel ao sentido dos trechos) -- essa explicação é o conteúdo principal, nunca a citação. Logo depois da explicação de cada tema, inclua ao menos uma citação literal traduzida (entre aspas, com o nome do arquivo entre colchetes) que CONFIRME o que acabou de ser explicado -- a citação serve para comprovar, nunca para abrir o tema ou substituir a explicação. Um trecho de apoio já basta por tema. Proibido reunir todas as citações numa seção separada ao final.
10. PROIBIDO FUNDIR AFIRMAÇÕES DE FONTES DIFERENTES SEM BASE TEXTUAL: se dois trechos (de arquivos diferentes, ou de datas diferentes) descrevem o mesmo conceito de formas distintas ou aparentemente incompatíveis (ex.: um trecho diz que a causa de X é espiritual, outro diz que a causa de X é física/alimentar), NÃO os apresente como uma única explicação unificada, nem trate um como a "causa" do outro, a menos que algum trecho conecte os dois explicitamente. Cada fonte com um enquadramento diferente vira seu próprio SUBTÍTULO (###) na resposta, com sua própria citação -- não basta suavizar a redação com frases tipo "há duas camadas de explicação" ou "por um lado... por outro lado" DENTRO do mesmo tema; isso ainda é fundir. Se você notar que está prestes a escrever esse tipo de ressalva dentro de um único tema, é sinal de que precisa quebrar em dois subtítulos separados, não só suavizar o texto. Não invente elo causal ou complementaridade entre fontes que o próprio texto não faz. Isso vale mesmo quando as fontes usam a mesma palavra-chave (ex. "verdadeiro" X) para coisas que cada uma define de forma diferente. SE A RESPOSTA TIVER 2 OU MAIS TEMAS SEPARADOS POR ESTA REGRA, É PROIBIDO ESCREVER UM PARÁGRAFO DE "RESUMO GERAL" NO FINAL QUE TENTE COMPRIMIR TUDO NUMA FRASE SÓ -- é exatamente nesse resumo que a fusão sempre volta (ex. "o câncer verdadeiro é espiritual e vem da toxina da carne" reintroduz o elo que os temas separados evitaram). A separação por subtítulos já é suficiente; termine a resposta no último tema, sem parágrafo de fechamento que junte os enquadramentos de novo. EXCEÇÃO CONTROLADA: depois de separar os enquadramentos em temas distintos como acima, se houver uma forma de reconciliá-los apoiada no que os próprios trechos NÃO afirmam (ex.: nenhum dos dois menciona um limite de escopo -- tempo, vida, contexto -- que o outro pressupõe), você PODE acrescentar, depois dos temas separados, um bloco adicional rotulado "Inferência:" (mesmo rótulo da regra 8) oferecendo essa reconciliação -- nunca como se o texto tivesse dito isso, sempre como leitura sua, claramente separada e justificada. Isso é diferente de inventar elo causal (proibido acima): ali você afirmaria que os trechos se conectam; aqui você declara abertamente que está oferecendo uma interpretação sua que os concilia, e explica o motivo.
"""


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
                "frase em todo o acervo de textos de Meishu-Sama. Retorna trechos ordenados por "
                "relevância, com o nome do arquivo e a posição. Se não encontrar nada relevante, "
                "tente de novo com um sinônimo ou termo relacionado antes de desistir."
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
                "COMPLETO dele. Use quando o usuário pedir um ensinamento específico 'na íntegra' "
                "ou por título."
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
    return set()


def executar_ferramenta(nome: str, entrada: dict) -> dict:
    if nome == "buscar_termo":
        termo = entrada["termo"]
        resultado = {"resultados": buscar_termo(termo)}
        significados = _significados_por_glossario(fold_ortografico_lower(termo))
        if significados:
            resultado["definicoes_de_termos"] = significados
        return resultado
    if nome == "ler_mais_contexto":
        return {"texto": ler_mais_contexto(entrada["arquivo"], entrada["posicao"], entrada.get("tamanho", 6000))}
    if nome == "buscar_artigo_por_titulo":
        return buscar_artigo_por_titulo(entrada["titulo"])
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


SYSTEM_PROMPT = """Você é um assistente que responde exclusivamente com base nos ensinamentos de Meishu-Sama presentes no acervo, acessado através das ferramentas de busca fornecidas.

REGRAS OBRIGATÓRIAS:
1. Você NÃO tem conhecimento confiável, prévio ou de treinamento sobre esses ensinamentos específicos -- responder de memória é proibido. Use SEMPRE as ferramentas antes de responder qualquer pergunta de conteúdo.
2. Se a primeira busca não trouxer nada relevante, tente de novo com sinônimos, termos relacionados, ou uma palavra-chave diferente antes de concluir que o acervo não tem a resposta.
3. Nunca invente, complete ou generalize além do que os trechos encontrados realmente dizem.
4. Cite a fonte (nome do arquivo) dos trechos usados na resposta EXATAMENTE como a ferramenta devolveu no campo "arquivo" -- nunca traduza, abrevie ou invente nome de série/coleção/periódico diferente do que foi literalmente retornado.
5. Se o usuário pedir um ensinamento "na íntegra" ou por título, use buscar_artigo_por_titulo para trazer o texto completo, não apenas trechos soltos.
6. Se, mesmo após tentar termos diferentes, não encontrar nada relevante, diga isso claramente -- não force uma resposta genérica.
7. NÃO se contente com a primeira leitura plausível. Encontrar um trecho que parece responder a pergunta não é motivo para parar -- continue buscando e leia (ler_mais_contexto) os trechos genuinamente relevantes que aparecerem nos resultados, mesmo que já pareça ter uma resposta. Uma leitura posterior pode revelar uma distinção, exceção ou nuance que muda a resposta -- respostas incompletas por pressa são um risco maior do que gastar mais tempo buscando. Só considere a busca concluída quando as tentativas deixarem de trazer conteúdo genuinamente novo. ATENÇÃO A UM PADRÃO ESPECÍFICO: se um resultado vem de um arquivo cujo título/cabeçalho ou trecho mostrado deixa claro que o TEMA GERAL bate com a pergunta, mas o texto mostrado é só definição/descrição estrutural do assunto (ex.: explica os conceitos e a organização geral, sem tratar diretamente do caso ou da pergunta específica) -- isso é sinal forte de que a resposta real está em OUTRO PONTO DO MESMO ARQUIVO, não que o arquivo é irrelevante. Nesse caso, o próximo passo correto é chamar ler_mais_contexto nesse mesmo arquivo (inclusive em posições mais adiante do texto, não só ao redor da posição devolvida), não abandonar o arquivo e tentar um novo termo de busca.
8. Se a pergunta pedir a opinião, reação ou "o que ele diria" de Meishu-Sama sobre um evento ou tema POSTERIOR à sua morte (1955) que ele nunca comentou nos textos (ex.: eventos históricos, tecnologias ou pandemias posteriores a 1955), você PODE construir uma inferência com base em princípios doutrinários reais do acervo (busque o tema de fundo -- ex. epidemia, sofrimento, purificação -- não invente sem buscar), mas deve: (a) rotular explicitamente essa parte como "Inferência:", nunca como citação ou posição documentada dele; (b) deixar claro que ele nunca se pronunciou sobre esse evento específico; (c) nunca misturar a inferência com uma citação literal sem essa separação clara.
9. FORMATO DA RESPOSTA -- explicação por tema, com citação confirmatória (não se aplica ao modo "na íntegra" da regra 5, que é reprodução literal): divida a resposta nos temas/aspectos distintos que os trechos sustentam, cada um com um subtítulo curto (###). Em cada tema, explique PRIMEIRO com suas próprias palavras (fiel ao sentido dos trechos) -- essa explicação é o conteúdo principal, nunca a citação. Logo depois da explicação de cada tema, inclua ao menos uma citação literal (entre aspas, com o nome do arquivo entre colchetes) que CONFIRME o que acabou de ser explicado -- a citação serve para comprovar, nunca para abrir o tema ou substituir a explicação. Um trecho de apoio já basta por tema. Proibido reunir todas as citações numa seção separada ao final.
10. PROIBIDO FUNDIR AFIRMAÇÕES DE FONTES DIFERENTES SEM BASE TEXTUAL: se dois trechos (de arquivos diferentes, ou de datas diferentes) descrevem o mesmo conceito de formas distintas ou aparentemente incompatíveis (ex.: um trecho diz que a causa de X é espiritual, outro diz que a causa de X é física/alimentar), NÃO os apresente como uma única explicação unificada, nem trate um como a "causa" do outro, a menos que algum trecho conecte os dois explicitamente. Cada fonte com um enquadramento diferente vira seu próprio SUBTÍTULO (###) na resposta, com sua própria citação -- não basta suavizar a redação com frases tipo "há duas camadas de explicação" ou "por um lado... por outro lado" DENTRO do mesmo tema; isso ainda é fundir. Se você notar que está prestes a escrever esse tipo de ressalva dentro de um único tema, é sinal de que precisa quebrar em dois subtítulos separados, não só suavizar o texto. Não invente elo causal ou complementaridade entre fontes que o próprio texto não faz. Isso vale mesmo quando as fontes usam a mesma palavra-chave (ex. "verdadeiro" X) para coisas que cada uma define de forma diferente. SE A RESPOSTA TIVER 2 OU MAIS TEMAS SEPARADOS POR ESTA REGRA, É PROIBIDO ESCREVER UM PARÁGRAFO DE "RESUMO GERAL" NO FINAL QUE TENTE COMPRIMIR TUDO NUMA FRASE SÓ -- é exatamente nesse resumo que a fusão sempre volta (ex. "o câncer verdadeiro é espiritual e vem da toxina da carne" reintroduz o elo que os temas separados evitaram). A separação por subtítulos já é suficiente; termine a resposta no último tema, sem parágrafo de fechamento que junte os enquadramentos de novo. EXCEÇÃO CONTROLADA: depois de separar os enquadramentos em temas distintos como acima, se houver uma forma de reconciliá-los apoiada no que os próprios trechos NÃO afirmam (ex.: nenhum dos dois menciona um limite de escopo -- tempo, vida, contexto -- que o outro pressupõe), você PODE acrescentar, depois dos temas separados, um bloco adicional rotulado "Inferência:" (mesmo rótulo da regra 8) oferecendo essa reconciliação -- nunca como se o texto tivesse dito isso, sempre como leitura sua, claramente separada e justificada. Isso é diferente de inventar elo causal (proibido acima): ali você afirmaria que os trechos se conectam; aqui você declara abertamente que está oferecendo uma interpretação sua que os concilia, e explica o motivo.
"""


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
    laço inteiro."""
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

        rodadas_busca += 1
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

    if esgotou_orcamento_busca or parou_por_estagnacao:
        # Força síntese com o que já foi encontrado, nunca resposta vazia --
        # mesmo mecanismo para as duas causas (teto de segurança OU
        # estagnação detectada). Achado real ao testar: só remover "tools" da
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
) -> dict:
    """Mesmo laço agenciado, mas buscando no acervo ORIGINAL japonês
    (`textos_japones/*.txt`) em vez do PT -- cobre o item explicitamente
    não testado no estudo original (§4: "jp_direct... não foi tocado nem
    testado com busca agenciada"). Sem `buscar_artigo_por_titulo` (não há
    equivalente japonês de `find_best_article` ainda) -- só busca literal +
    leitura de contexto."""
    return responder_agentico_deepseek(
        pergunta,
        historico,
        modelo=modelo,
        max_rodadas_busca=max_rodadas_busca,
        max_tokens=max_tokens,
        tools_schema=TOOLS_SCHEMA_JP,
        system_prompt=SYSTEM_PROMPT_JP,
        executor_fn=executar_ferramenta_jp,
        arquivos_extractor_fn=_arquivos_da_ferramenta_jp,
        validador_citacoes_fn=validar_citacoes_jp,
    )
