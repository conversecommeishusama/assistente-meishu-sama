#!/usr/bin/env python3
"""Comparação JP original ↔ PT atual ↔ PT revisado (retradução DeepSeek).

Para os pares de falas do Gokōwa-roku (Suplemento), mostra lado a lado:
  1. JP original   (textos_japones)
  2. PT atual      (o que está nos volumes / fonte de verdade)
  3. PT revisado   (nova tradução do DeepSeek a partir do JP)

Uso:
    python3 scripts/comparar_jp_pt_atual_revisado.py --par 3
    python3 scripts/comparar_jp_pt_atual_revisado.py --pares 0-14
    python3 scripts/comparar_jp_pt_atual_revisado.py --todos
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

TRADUZIR_PROMPT = """Você é um tradutor fiel de japonês→português de textos do Meishu-Sama (Igreja Messiânica Mundial).

Traduza o trecho japonês abaixo para o português, seguindo estas regras:
1. Traduza fielmente, mantendo o tom e o estilo do original (inclusive se for truncado/coloquial — registros de conversas anotadas).
2. Preserve nomes próprios, títulos de obras, e termos consagrados (ex: Johrei, Ohikari, Daijo, Shojo, Kannon).
3. NÃO acrescente contexto ou explicações que não existam no original.
4. Se houver referência ambígua no original (ex: "o senhor", "o compositor"), mantenha a ambiguidade — não invente nomes.

### JAPONÊS PARA TRADUZIR:
{jp}

### TRADUÇÃO:
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
    if not raw:
        return None
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


def retraduzir(jp: str) -> str:
    from goshinsho.services.agentic_search import _client

    for tentativa in range(5):
        reforco = ""
        if tentativa == 1:
            reforco = "\n\nResponda APENAS a tradução, sem comentários, sem aspas externas."
        elif tentativa == 2:
            reforco = "\n\nTraduza agora. Saída: só o texto traduzido."
        resp = _client().chat.completions.create(
            model=MODELO,
            max_tokens=400,
            messages=[{"role": "user", "content": TRADUZIR_PROMPT.format(jp=jp) + reforco}],
            temperature=0,
        )
        raw = (resp.choices[0].message.content or "").strip()
        # limpar aspas/ruído
        raw = raw.strip('"').strip()
        if raw and len(raw) > 2:
            return raw
    return "(falha na retradução)"


def main() -> None:
    falas_jp = extrair_falas(JP.read_text(encoding="utf-8"))
    falas_pt = extrair_falas(PT.read_text(encoding="utf-8"))
    n = min(len(falas_jp), len(falas_pt))

    # seleção
    indices = []
    if "--todos" in sys.argv:
        indices = list(range(n))
    else:
        for a in sys.argv[1:]:
            if a.startswith("--pares"):
                lo, hi = a.split("=")[1].split("-")
                indices.extend(range(int(lo), int(hi) + 1))
            elif a.startswith("--par"):
                indices.append(int(a.split("=")[1]))
    if not indices:
        indices = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]

    linhas = []
    for i in indices:
        if i >= n:
            continue
        quem, jp = falas_jp[i]
        _, pt = falas_pt[i]
        print(f"\n=== [{i}] {quem} ===")
        print(f"  JP ORIGINAL : {jp}")
        print(f"  PT ATUAL    : {pt}")
        print("  Retraduzindo (DeepSeek)...")
        pt_rev = retraduzir(jp)
        print(f"  PT REVISADO : {pt_rev}")

        linhas.append({
            "indice": i,
            "quem": quem,
            "jp": jp,
            "pt_atual": pt,
            "pt_revisado": pt_rev,
        })

    OUT.mkdir(parents=True, exist_ok=True)
    arq = OUT / "comparacao_jp_pt_atual_revisado.json"
    arq.write_text(json.dumps(linhas, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSalvo: {arq} ({len(linhas)} pares)")


if __name__ == "__main__":
    main()
