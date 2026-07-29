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


def buscar_termo(termo: str, max_resultados: int = 12) -> list[dict]:
    """Busca literal (tolerante a acento/maiúscula, fronteira de palavra) do
    termo/frase em todo o acervo, ordenada por relevância -- corrige dois
    achados do estudo: (a) §3.3, DeepSeek buscando 'cancer' sem acento batia
    só 3x contra 366x de 'câncer', jogando a busca para um canto errado do
    acervo; (b) §3.6, uma ordenação ingênua por ordem de arquivo podia cortar
    o trecho certo antes de ele aparecer quando o termo tem muitas
    ocorrências espalhadas."""
    termo_folded = fold_ortografico_lower(termo)
    if not termo_folded:
        return []
    padrao = re.compile(r"\b" + re.escape(termo_folded) + r"\b")
    termos_sig = _termos_significativos(termo_folded)

    candidatos: list[dict] = []
    for arquivo, (_, texto_folded) in _corpus_pt().items():
        for match in padrao.finditer(texto_folded):
            pos = match.start()
            janela_ini = max(0, pos - JANELA_PROXIMIDADE)
            janela_fim = min(len(texto_folded), pos + len(termo_folded) + JANELA_PROXIMIDADE)
            vizinhanca = texto_folded[janela_ini:janela_fim]
            score = sum(vizinhanca.count(t) for t in termos_sig) if termos_sig else 1
            candidatos.append({"arquivo": arquivo, "posicao": pos, "score": score})

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


def ler_mais_contexto(arquivo: str, posicao: int, tamanho: int = 3000) -> str:
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


def ler_mais_contexto_jp(arquivo: str, posicao: int, tamanho: int = 3000) -> str:
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
        return {"texto": ler_mais_contexto_jp(entrada["arquivo"], entrada["posicao"], entrada.get("tamanho", 3000))}
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
            "description": "Lê um trecho maior de um arquivo específico do acervo japonês, ao redor de uma posição já encontrada por buscar_termo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "arquivo": {"type": "string"},
                    "posicao": {"type": "integer"},
                    "tamanho": {"type": "integer", "description": "Quantos caracteres ler (padrão 3000)"},
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
7. Não é obrigatório usar todas as rodadas de busca disponíveis -- pare de buscar assim que tiver material suficiente para responder com confiança; buscas repetidas sem necessidade custam tempo e dinheiro à toa.
8. Se a pergunta pedir a opinião, reação ou "o que ele diria" de Meishu-Sama sobre um evento ou tema POSTERIOR à sua morte (1955) que ele nunca comentou nos textos, você PODE construir uma inferência com base em princípios doutrinários reais do acervo (busque o tema de fundo -- não invente sem buscar), mas deve: (a) rotular explicitamente essa parte como "Inferência:", nunca como citação ou posição documentada dele; (b) deixar claro que ele nunca se pronunciou sobre esse evento específico; (c) nunca misturar a inferência com uma citação literal sem essa separação clara.
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
            "description": "Lê um trecho maior de um arquivo específico, ao redor de uma posição já encontrada por buscar_termo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "arquivo": {"type": "string"},
                    "posicao": {"type": "integer"},
                    "tamanho": {"type": "integer", "description": "Quantos caracteres ler (padrão 3000)"},
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
        return {"resultados": buscar_termo(entrada["termo"])}
    if nome == "ler_mais_contexto":
        return {"texto": ler_mais_contexto(entrada["arquivo"], entrada["posicao"], entrada.get("tamanho", 3000))}
    if nome == "buscar_artigo_por_titulo":
        return buscar_artigo_por_titulo(entrada["titulo"])
    return {"erro": f"ferramenta desconhecida: {nome}"}


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
7. Não é obrigatório usar todas as rodadas de busca disponíveis -- pare de buscar assim que tiver material suficiente para responder com confiança; buscas repetidas sem necessidade custam tempo e dinheiro à toa.
8. Se a pergunta pedir a opinião, reação ou "o que ele diria" de Meishu-Sama sobre um evento ou tema POSTERIOR à sua morte (1955) que ele nunca comentou nos textos (ex.: eventos históricos, tecnologias ou pandemias posteriores a 1955), você PODE construir uma inferência com base em princípios doutrinários reais do acervo (busque o tema de fundo -- ex. epidemia, sofrimento, purificação -- não invente sem buscar), mas deve: (a) rotular explicitamente essa parte como "Inferência:", nunca como citação ou posição documentada dele; (b) deixar claro que ele nunca se pronunciou sobre esse evento específico; (c) nunca misturar a inferência com uma citação literal sem essa separação clara.
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
    esgotou_orcamento_busca = False
    t0 = time.time()
    resposta_final = ""
    truncada = False

    while rodadas_busca < max_rodadas_busca:
        rodadas_busca += 1
        resp = client.chat.completions.create(model=modelo, max_tokens=max_tokens, messages=messages, tools=tools_schema)
        usage = resp.usage
        total_in += usage.prompt_tokens
        total_out += usage.completion_tokens
        choice = resp.choices[0]
        msg = choice.message

        if choice.finish_reason == "tool_calls" and msg.tool_calls:
            messages.append({"role": "assistant", "content": msg.content, "tool_calls": [tc.model_dump() for tc in msg.tool_calls]})
            for tc in msg.tool_calls:
                nome = tc.function.name
                try:
                    entrada = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    entrada = {}
                chamadas_ferramenta.append(f"{nome}({json.dumps(entrada, ensure_ascii=False)})")
                resultado = executor_fn(nome, entrada)
                arquivos_retornados |= arquivos_extractor_fn(nome, entrada, resultado)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(resultado, ensure_ascii=False)[:TAMANHO_MAX_RESULTADO_FERRAMENTA],
                    }
                )
            continue

        resposta_final = msg.content or ""
        truncada = choice.finish_reason == "length"
        break
    else:
        # Rede de segurança atingida (LIMITE_SEGURANCA_RODADAS) sem o modelo
        # ter parado sozinho -- em uso normal isso não deveria acontecer (o
        # próprio modelo decide quando parar, ver docstring); força síntese
        # mesmo assim, para nunca devolver uma resposta vazia. Achado real ao
        # testar: só remover "tools" da chamada (ou usar tool_choice="none"
        # com tools ainda presentes) NÃO basta -- o deepseek-v4-flash "vaza" a
        # sintaxe interna de tool-call como texto literal (tokens
        # <｜｜DSML｜｜tool_calls>...) mesmo sem "tools" no payload. Só parou de
        # acontecer ao acrescentar uma mensagem explícita de usuário avisando
        # que não há mais ferramenta disponível -- comportamento específico
        # deste modelo, não documentado, achado por teste direto (2026-07-29).
        esgotou_orcamento_busca = True
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
