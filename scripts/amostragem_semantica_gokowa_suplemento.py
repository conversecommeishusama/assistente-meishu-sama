#!/usr/bin/env python3
"""Amostragem de verificação semântica JP↔PT linha a linha no Gokōwa-roku (Suplemento).

Envia pares de falas (JP original + PT traduzido) ao DeepSeek e classifica cada
par como:
  - fiel        : tradução correta, sentido preservado
  - truncado    : o PRÓPRIO original é truncado/entrecortado (anotação crua) — PT fiel
  - erro_sentido: a tradução INVERTE ou altera o sentido do original
  - ambiguo     : referência ambígua (nomes/sujeitos sem contexto) — precisaria nota editorial
  - diferenca   : há diferença de conteúdo (trecho faltando/sobrando)

Gera relatório em JSON e texto.

Uso:
    python3 scripts/amostragem_semantica_gokowa_suplemento.py [--primeiras N] [--par N]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
JP = RAIZ / "textos_japones" / "19480101-御光話録（補）.txt"
PT = RAIZ / "livros_publicacao_pt_revisado" / "19480101 - Gokōwa-roku (Suplemento).txt"
OUT = RAIZ / "reports" / "amostragem_semantica_gokowa"

MODELO = "deepseek-v4-flash"

PROMPT = """Você é um revisor de tradução japonês→português. Compare o trecho original japonês (JP) com sua tradução portuguesa (PT) e classifique a tradução.

Contexto: esta obra (Gokōwa-roku Suplemento) é um registro manuscrito de sessões de perguntas e respostas. O original japonês é naturalmente truncado — falas curtas, saltos de tópico, referências sem contexto (porque o anotador sabia quem falava). Isso NÃO é defeito da tradução.

Classifique como UMA das opções:
- "fiel" — tradução correta, sentido preservado
- "truncado_fiel" — o original é truncado/entrecortado E a tradução o reflete fielmente (mantém o estilo)
- "erro_sentido" — a tradução INVERTE ou distorce o sentido do original (erro real de tradução)
- "ambiguo" — a tradução está correta, mas fica ambígua/confusa para o leitor por falta de contexto (nomes, sujeitos, referências) — precisaria de nota editorial
- "diferenca" — há diferença real de conteúdo (PT omitiu/acrescentou algo significativo)

### JAPONÊS ORIGINAL (JP):
{jp}

### TRADUÇÃO PORTUGUESA (PT):
{pt}

### RESPOSTA (responda SOMENTE com JSON puro, nada além):
{{"classificacao": "...", "justificativa": "1 frase curta", "jp_resumo": "...", "pt_resumo": "..."}}
"""


def extrair_falas(texto: str) -> list[tuple[str, str]]:
    falas = []
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            continue
        m = re.match(r"^(Meishu-Sama|Interlocutor):\s*(.*)", linha)
        if m:
            falas.append((m.group(1), m.group(2)))
    return falas


def _extrair_json(raw: str) -> str | None:
    """Extrai um objeto JSON balanceado do texto bruto (robusto a markdown/ruído)."""
    if not raw:
        return None
    # remove blocos ```json ... ```
    raw = re.sub(r"```(?:json)?\s*", "", raw)
    start = raw.find("{")
    if start == -1:
        return None
    depth = 0
    in_str = False
    esc = False
    for i in range(start, len(raw)):
        c = raw[i]
        if in_str:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == '"':
                in_str = False
            continue
        if c == '"':
            in_str = True
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return raw[start : i + 1]
    return None


def chamar_deepseek(jp: str, pt: str) -> dict:
    from goshinsho.services.agentic_search import _client

    user_msg = PROMPT.format(jp=jp, pt=pt)

    # RETRY com reforço progressivo (padrão do harness 5263, 5 tentativas).
    # Usa UMA mensagem user, temperature=0 (padrão que funciona no ai_service).
    for tentativa in range(5):
        reforco = ""
        if tentativa == 1:
            reforco = "\n\nIMPORTANTE: responda APENAS o JSON puro, sem markdown, sem ```json, sem texto extra. Nada além do JSON."
        elif tentativa == 2:
            reforco = '\n\nATENÇÃO: sua resposta anterior foi inválida (vazia ou não-JSON). Responda EXATAMENTE neste formato, nada mais:\n{"classificacao": "fiel", "justificativa": "...", "jp_resumo": "...", "pt_resumo": "..."}'
        elif tentativa == 3:
            reforco = "\n\nResponda começando o JSON na primeira linha. Exemplo: {\"classificacao\":\"fiel\",\"justificativa\":\"...\",\"jp_resumo\":\"...\",\"pt_resumo\":\"...\"}"
        elif tentativa == 4:
            # última: repete o exemplo, bem curto, sem o texto longo do prompt
            reforco = "\n\nJSON: {\"classificacao\":\"fiel\",\"justificativa\":\"...\",\"jp_resumo\":\"...\",\"pt_resumo\":\"...\"}"

        resp = _client().chat.completions.create(
            model=MODELO,
            max_tokens=300,
            messages=[{"role": "user", "content": user_msg + reforco}],
            temperature=0,
        )
        raw = resp.choices[0].message.content or ""
        m = _extrair_json(raw)
        if m is not None:
            try:
                r = json.loads(m)
                if r.get("classificacao"):
                    return r
            except Exception:
                pass

    return {"classificacao": "erro", "justificativa": "resposta inválida após 3 tentativas", "raw": raw[:200]}


def main() -> None:
    primeiras = None
    so_par = None
    for a in sys.argv[1:]:
        if a.startswith("--primeiras"):
            primeiras = int(a.split("=")[1])
        elif a.startswith("--par"):
            so_par = int(a.split("=")[1])

    falas_jp = extrair_falas(JP.read_text(encoding="utf-8"))
    falas_pt = extrair_falas(PT.read_text(encoding="utf-8"))
    n = min(len(falas_jp), len(falas_pt))
    print(f"Falas JP: {len(falas_jp)} | PT: {len(falas_pt)} | comparando até {n}")

    OUT.mkdir(parents=True, exist_ok=True)
    resultados = []

    # seleção dos pares
    if so_par is not None:
        indices = [so_par]
    elif primeiras:
        indices = list(range(min(primeiras, n)))
    else:
        indices = list(range(n))

    for i in indices:
        quem, jp = falas_jp[i]
        _, pt = falas_pt[i]
        print(f"[{i}] JP: {jp[:60]}...")
        try:
            r = chamar_deepseek(jp, pt)
        except Exception as e:
            r = {"classificacao": "erro_api", "justificativa": str(e)[:150]}
        r["indice"] = i
        r["quem"] = quem
        r["jp"] = jp[:200]
        r["pt"] = pt[:200]
        resultados.append(r)
        print(f"    → {r.get('classificacao')}: {r.get('justificativa', '')[:80]}")

    # salvar
    arq_out = OUT / "resultado_amostragem.json"
    arq_out.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSalvo: {arq_out} ({len(resultados)} pares)")

    # resumo
    from collections import Counter
    cont = Counter(r.get("classificacao", "?") for r in resultados)
    print("\n=== Resumo ===")
    for k, v in cont.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
