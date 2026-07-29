#!/usr/bin/env python3
"""Piloto: Claude com busca agenciada (ferramentas) sobre o acervo real,
sem embedding/FAISS -- ao invés de pré-calcular chunks por similaridade
vetorial, o próprio modelo decide o que buscar, tenta de novo com outro
termo se a primeira busca falhar, e só responde com o que encontrou.

Compara contra a pipeline pt_direct já em produção (mesma pergunta, mesmo
corpus) em qualidade, tempo e custo. Não toca em nada de produção -- só
lê os arquivos de texto e o índice de artigos já existente.

Uso:
    ANTHROPIC_API_KEY já deve estar em .env (ou variável de ambiente)
    venv/bin/python3 scripts/pilot_agentic_claude.py
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv()

from anthropic import Anthropic
from openai import OpenAI

TEXTOS_DIR = PROJECT_ROOT / "textos_portugues"

# Preços por 1M tokens -- valores aproximados no momento em que este piloto
# foi escrito (2026-07-29); conferir em console.anthropic.com/pricing e
# platform.deepseek.com/api-docs/pricing antes de usar os números de custo
# para qualquer decisão real -- os totais em tokens (sempre exatos, vindos
# da própria API) são a métrica mais confiável deste relatório.
PRECOS = {
    "claude-haiku-4-5-20251001": {"entrada": 1.0, "saida": 5.0},
    "claude-sonnet-5": {"entrada": 3.0, "saida": 15.0},
    "deepseek-v4-flash": {"entrada": 0.28, "saida": 0.42},
}

MAX_RODADAS_FERRAMENTA = 6


# --------------------------------------------------------------------------
# Corpus em memória (carregado uma vez) -- simula o que eu faço como Claude
# Code: grep literal nos arquivos reais, sem nenhum índice vetorial.
# --------------------------------------------------------------------------
_CORPUS_CACHE: dict[str, str] | None = None


def carregar_corpus() -> dict[str, str]:
    global _CORPUS_CACHE
    if _CORPUS_CACHE is None:
        _CORPUS_CACHE = {}
        for path in sorted(TEXTOS_DIR.glob("*.txt")):
            try:
                _CORPUS_CACHE[path.name] = path.read_text(encoding="utf-8")
            except Exception:
                continue
    return _CORPUS_CACHE


def buscar_termo(termo: str, max_resultados: int = 12) -> list[dict]:
    """Grep literal (case-insensitive) do termo em todos os arquivos do
    acervo. Não usa embedding nem pontuação semântica -- só posição."""
    corpus = carregar_corpus()
    termo_lower = termo.lower()
    resultados = []
    for arquivo, texto in corpus.items():
        texto_lower = texto.lower()
        inicio = 0
        while True:
            pos = texto_lower.find(termo_lower, inicio)
            if pos == -1:
                break
            janela_ini = max(0, pos - 200)
            janela_fim = min(len(texto), pos + len(termo) + 300)
            trecho = texto[janela_ini:janela_fim].strip()
            resultados.append({"arquivo": arquivo, "posicao": pos, "trecho": trecho})
            inicio = pos + len(termo)
            if len(resultados) >= max_resultados * 3:
                break
        if len(resultados) >= max_resultados * 3:
            break
    # Deduplica hits muito próximos do mesmo arquivo (mesmo parágrafo)
    dedup: list[dict] = []
    vistos: set[tuple[str, int]] = set()
    for r in resultados:
        chave = (r["arquivo"], r["posicao"] // 500)
        if chave in vistos:
            continue
        vistos.add(chave)
        dedup.append(r)
        if len(dedup) >= max_resultados:
            break
    return dedup


def ler_mais_contexto(arquivo: str, posicao: int, tamanho: int = 3000) -> str:
    corpus = carregar_corpus()
    texto = corpus.get(arquivo)
    if not texto:
        return f"Arquivo '{arquivo}' não encontrado no acervo."
    ini = max(0, posicao - 500)
    fim = min(len(texto), posicao + tamanho)
    return texto[ini:fim]


def buscar_artigo_por_titulo(titulo: str) -> dict:
    """Reaproveita find_best_article/load_article_chunks já corrigidos
    nesta sessão -- não usa embedding, usa o campo 'titulo' por chunk."""
    from goshinsho.services.teaching_article_service import find_best_article, load_article_chunks

    artigo = find_best_article(titulo, min_score=0.45)
    if not artigo:
        return {"encontrado": False, "motivo": "Nenhum artigo com esse título foi encontrado com confiança suficiente."}
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
        "name": "buscar_termo",
        "description": (
            "Busca literal (grep) de uma palavra ou frase em todo o acervo de textos "
            "de Meishu-Sama. Retorna trechos onde o termo aparece, com o nome do "
            "arquivo e a posição. Se não encontrar nada relevante, tente de novo com "
            "um sinônimo ou termo relacionado antes de desistir."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "termo": {"type": "string", "description": "Palavra ou frase exata a buscar"},
            },
            "required": ["termo"],
        },
    },
    {
        "name": "ler_mais_contexto",
        "description": "Lê um trecho maior de um arquivo específico, ao redor de uma posição já encontrada por buscar_termo.",
        "input_schema": {
            "type": "object",
            "properties": {
                "arquivo": {"type": "string"},
                "posicao": {"type": "integer"},
                "tamanho": {"type": "integer", "description": "Quantos caracteres ler (padrão 3000)"},
            },
            "required": ["arquivo", "posicao"],
        },
    },
    {
        "name": "buscar_artigo_por_titulo",
        "description": (
            "Busca um ensinamento/artigo específico pelo título aproximado e retorna o "
            "TEXTO COMPLETO dele. Use quando o usuário pedir um ensinamento específico "
            "'na íntegra' ou por título."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "titulo": {"type": "string", "description": "Título aproximado do ensinamento"},
            },
            "required": ["titulo"],
        },
    },
]


def executar_ferramenta(nome: str, entrada: dict) -> dict:
    if nome == "buscar_termo":
        return {"resultados": buscar_termo(entrada["termo"])}
    if nome == "ler_mais_contexto":
        return {"texto": ler_mais_contexto(entrada["arquivo"], entrada["posicao"], entrada.get("tamanho", 3000))}
    if nome == "buscar_artigo_por_titulo":
        return buscar_artigo_por_titulo(entrada["titulo"])
    return {"erro": f"ferramenta desconhecida: {nome}"}


SYSTEM_PROMPT = """Você é um assistente que responde exclusivamente com base nos ensinamentos de Meishu-Sama presentes no acervo, acessado através das ferramentas de busca fornecidas.

REGRAS OBRIGATÓRIAS:
1. Você NÃO tem conhecimento confiável, prévio ou de treinamento sobre esses ensinamentos específicos -- responder de memória é proibido. Use SEMPRE as ferramentas antes de responder qualquer pergunta de conteúdo.
2. Se a primeira busca não trouxer nada relevante, tente de novo com sinônimos, termos relacionados, ou uma palavra-chave diferente antes de concluir que o acervo não tem a resposta.
3. Nunca invente, complete ou generalize além do que os trechos encontrados realmente dizem.
4. Sempre cite a fonte (nome do arquivo) dos trechos usados na resposta.
5. Se o usuário pedir um ensinamento "na íntegra" ou por título, use buscar_artigo_por_titulo para trazer o texto completo, não apenas trechos soltos.
6. Se, mesmo após tentar termos diferentes, não encontrar nada relevante, diga isso claramente -- não force uma resposta genérica.
"""


def responder_agentico(pergunta: str, historico: list[dict] | None, modelo: str) -> dict:
    client = Anthropic()
    messages = list(historico or []) + [{"role": "user", "content": pergunta}]
    total_in = total_out = 0
    rodadas = 0
    chamadas_ferramenta: list[str] = []
    t0 = time.time()
    resposta_final = ""

    while rodadas < MAX_RODADAS_FERRAMENTA:
        rodadas += 1
        resp = client.messages.create(
            model=modelo,
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            tools=TOOLS_SCHEMA,
            messages=messages,
        )
        total_in += resp.usage.input_tokens
        total_out += resp.usage.output_tokens

        if resp.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": resp.content})
            tool_results = []
            for block in resp.content:
                if block.type == "tool_use":
                    chamadas_ferramenta.append(f"{block.name}({json.dumps(block.input, ensure_ascii=False)})")
                    resultado = executar_ferramenta(block.name, block.input)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(resultado, ensure_ascii=False)[:8000],
                        }
                    )
            messages.append({"role": "user", "content": tool_results})
            continue

        resposta_final = "".join(b.text for b in resp.content if b.type == "text")
        truncada = resp.stop_reason == "max_tokens"
        break
    else:
        resposta_final = "(limite de rodadas de ferramenta atingido sem resposta final)"
        truncada = False

    tempo = time.time() - t0
    preco = PRECOS.get(modelo, {"entrada": 0, "saida": 0})
    custo = (total_in * preco["entrada"] + total_out * preco["saida"]) / 1_000_000

    return {
        "resposta": resposta_final,
        "truncada": truncada,
        "tempo": round(tempo, 1),
        "rodadas": rodadas,
        "chamadas_ferramenta": chamadas_ferramenta,
        "tokens_entrada": total_in,
        "tokens_saida": total_out,
        "custo": round(custo, 5),
        "modelo": modelo,
    }


def _tools_formato_openai() -> list[dict]:
    """Converte o esquema de ferramentas do formato Anthropic para o
    formato de function-calling compatível com OpenAI, usado pela API da
    DeepSeek."""
    convertidas = []
    for tool in TOOLS_SCHEMA:
        convertidas.append(
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
        )
    return convertidas


def responder_agentico_deepseek(pergunta: str, historico: list[dict] | None, modelo: str = "deepseek-v4-flash") -> dict:
    client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + list(historico or []) + [{"role": "user", "content": pergunta}]
    tools = _tools_formato_openai()
    total_in = total_out = 0
    rodadas = 0
    chamadas_ferramenta: list[str] = []
    t0 = time.time()
    resposta_final = ""
    truncada = False

    while rodadas < MAX_RODADAS_FERRAMENTA:
        rodadas += 1
        resp = client.chat.completions.create(
            model=modelo,
            max_tokens=8000,
            messages=messages,
            tools=tools,
        )
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
                resultado = executar_ferramenta(nome, entrada)
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(resultado, ensure_ascii=False)[:8000],
                    }
                )
            continue

        resposta_final = msg.content or ""
        truncada = choice.finish_reason == "length"
        break
    else:
        resposta_final = "(limite de rodadas de ferramenta atingido sem resposta final)"

    tempo = time.time() - t0
    preco = PRECOS.get(modelo, {"entrada": 0, "saida": 0})
    custo = (total_in * preco["entrada"] + total_out * preco["saida"]) / 1_000_000

    return {
        "resposta": resposta_final,
        "truncada": truncada,
        "tempo": round(tempo, 1),
        "rodadas": rodadas,
        "chamadas_ferramenta": chamadas_ferramenta,
        "tokens_entrada": total_in,
        "tokens_saida": total_out,
        "custo": round(custo, 5),
        "modelo": modelo,
    }


def responder_pt_direct(pergunta: str, historico: list[dict] | None) -> dict:
    from goshinsho.pipeline.answer import answer
    from goshinsho.services.pt_retrieval import pt_only_pool

    t0 = time.time()
    resp = answer(pergunta, history=historico or [], language="Português", response_mode="direct", base_pool_fn=pt_only_pool)
    tempo = time.time() - t0
    return {"resposta": resp, "tempo": round(tempo, 1)}


PERGUNTAS_TESTE = [
    "cancer",
    "johrei",
    "ikebana",
    "homosexualidade",
    "ohikari",
    "hora das bruxas",
    "quem é Meishu-Sama?",
    "o que Meishu-Sama falaria sobre a pandemia de Covid-19?",
    "Quais eram os critérios para o recebimento do Ohikari? Existia um curso para isso? Esse curso era obrigatório? Era necessário pagar alguma coisa?",
]


BACKENDS = ["sonnet", "haiku", "deepseek", "pt_direct"]


def main():
    resultados = {"data": time.strftime("%Y-%m-%d %H:%M:%S"), "casos": []}

    print("=" * 80)
    print("PILOTO: busca agenciada (Sonnet / Haiku / DeepSeek) vs pt_direct (produção)")
    print("=" * 80)

    historicos: dict[str, list[dict]] = {nome: [] for nome in BACKENDS}

    for i, pergunta in enumerate(PERGUNTAS_TESTE, 1):
        print(f"\n[Turno {i}] {pergunta}")
        print("-" * 80)

        respostas: dict[str, dict] = {}

        print("  Claude Sonnet (agentico)...", end=" ", flush=True)
        r = responder_agentico(pergunta, historicos["sonnet"], "claude-sonnet-5")
        print(f"OK ({r['tempo']}s, {r['rodadas']} rodadas, ${r['custo']:.5f})")
        respostas["sonnet"] = r

        print("  Claude Haiku (agentico)...", end=" ", flush=True)
        r = responder_agentico(pergunta, historicos["haiku"], "claude-haiku-4-5-20251001")
        print(f"OK ({r['tempo']}s, {r['rodadas']} rodadas, ${r['custo']:.5f})")
        respostas["haiku"] = r

        print("  DeepSeek (agentico)...", end=" ", flush=True)
        try:
            r = responder_agentico_deepseek(pergunta, historicos["deepseek"])
            print(f"OK ({r['tempo']}s, {r['rodadas']} rodadas, ${r['custo']:.5f})")
        except Exception as exc:
            r = {"resposta": f"(erro: {exc})", "tempo": 0, "rodadas": 0, "chamadas_ferramenta": [], "tokens_entrada": 0, "tokens_saida": 0, "custo": 0, "modelo": "deepseek-v4-flash", "truncada": False}
            print(f"ERRO: {exc}")
        respostas["deepseek"] = r

        print("  pt_direct (producao atual)...", end=" ", flush=True)
        r = responder_pt_direct(pergunta, historicos["pt_direct"])
        print(f"OK ({r['tempo']}s)")
        respostas["pt_direct"] = r

        resultados["casos"].append({"turno": i, "pergunta": pergunta, "respostas": respostas})

        for nome in BACKENDS:
            historicos[nome].append({"role": "user", "content": pergunta})
            historicos[nome].append({"role": "assistant", "content": respostas[nome]["resposta"]})

    out_path = PROJECT_ROOT / "reports" / "piloto_agentico_perguntas_dificeis.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResultado salvo em: {out_path}")


if __name__ == "__main__":
    main()
