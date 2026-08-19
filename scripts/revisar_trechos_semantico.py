#!/usr/bin/env python3
"""Aplica o executor semântico (reescrita localizada) aos 5 trechos de avaliação.

Lê os trechos originais (src_1..5.txt em /tmp/trechos_claude), aplica o
método semântico de edições localizadas (de->para com validação de âncora),
e salva os resultados revisados (revisado_semantico_1..5.txt) para avaliação
pelo Claude.

Uso:
    python3 scripts/revisar_trechos_semantico.py            # processa todos (1-5)
    python3 scripts/revisar_trechos_semantico.py 5          # só o trecho 5
    REVISAR_TRECHO=5 python3 scripts/revisar_trechos_semantico.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, "/var/www/goshinsho")
sys.path.insert(0, "/var/www/goshinsho/goshinsho")

from goshinsho.services import ai_service

MODELO = "deepseek-v4-flash"
# deepseek-v4-flash é reasoning model: gasta ~14-60k chars raciocinando antes
# de responder. 16000 tokens estouravam (content vazio); 40000 resolve.
MAX_TOKENS = 40000
TRECHOS = Path("/tmp/trechos_claude")

PROTOCOLO = """## Protocolo (padrão de editora internacional — revisão literária)
- Fluidez e ritmo de frase: reescrever construções arrastadas/truncadas, variar comprimento de frase para criar cadência, eliminar repetição de conectivo, cortar redundância SEM cortar conteúdo.
- Precisão lexical: palavra mais exata e natural em português, sem calques. Vocabulário rico mas nunca artificial.
- Coesão: transição natural entre ideias, sem inventar frase de sentido novo.
- NUNCA: mudar sentido/fato/nome/data/número/ordem/citação; adicionar ou cortar informação; alterar conteúdo de citação entre aspas.
- Preservar integralmente: numeração, nomes próprios, títulos, estrutura de parágrafos.

## Nível de exigência: editora internacional — AMBIÇÃO ESTÉTICA REAL
Você não está só corrigindo erros: está ELEVANDO a prosa a padrão de editora de
livros religiosos/filosóficos de alto nível. O texto atual pode estar "correto"
e ainda assim estar ABAIXO do nível. Trate cada trecho com olhar de editor
exigente.

Diretrizes de ambição (aplique sempre que houver ganho):
- Cadência e ritmo: reordene orações, alterne frases curtas e longas, elimine a
  monotonia sintática. Períodos picados demais podem fundir; períodos empilhados
  podem quebrar em dois.
- Força e precisão lexical: troque paráfrases genéricas e calques por palavra
  exata e viva. Elimine tiques como "coisas", "de certa forma", "tipo de",
  "dessa forma", "desse modo" repetidos.
- Eco mecânico: conectivos repetidos em sequência ("Além disso", "Portanto",
  "No entanto") e palavras repetidas no mesmo parágrafo devem variar (anáfora ou
  sinônimo exato).
- Coesão: garanta transição natural entre parágrafos, sem inventar frase nova.

Regras INEGOCIÁVEIS (vigem mesmo com ambição):
- NUNCA mudar sentido/fato/nome/data/número/ordem/citação.
- NUNCA adicionar ou cortar informação.
- NUNCA alterar conteúdo de citação entre aspas, numeração, títulos, divisórias, estrofes."""


def _client():
    return ai_service._client()


def _pedir_edicoes(texto: str) -> list[dict]:
    prompt = f"""{PROTOCOLO}

## Tarefa
Proponha EDIÇÕES LOCALIZADAS para o texto abaixo. Proponha onde houver QUALQUER
ganho real de fluidez, cadência, coesão ou precisão — mesmo que o trecho esteja
gramaticalmente correto. Não deixe parágrafo com eco mecânico ou construção
arrastada sem proposta. Só deixe um trecho intacto se ele já estiver excelente
(isso deve ser a exceção, não a regra).
Regras:
- `de` deve ser um trecho LITERAL EXATO do texto atual.
- `para` é a versão revisada (fluidez/elegância/cadência) SEM mudar sentido/fato/nome/número/ordem/citação.
- Não altere numeração, nomes próprios, números, datas, citações.

## Texto atual
{texto}

## Formato de saída (JSON puro, nada mais)
{{"edicoes": [{{"de": "trecho literal exato", "para": "novo texto"}}]}}"""

    for tentativa in range(3):
        reforco = ""
        if tentativa == 1:
            reforco = "\n\nIMPORTANTE: retorne APENAS o JSON puro, sem markdown."
        elif tentativa == 2:
            reforco = "\n\nATENÇÃO: formato EXATO: {\"edicoes\": [{\"de\": \"...\", \"para\": \"...\"}]}"
        resp = _client().chat.completions.create(
            model=MODELO, messages=[{"role": "user", "content": prompt + reforco}],
            temperature=0, max_tokens=MAX_TOKENS,
        )
        final = resp.choices[0].message.content or ""
        m = re.search(r"\{.*\}", final, re.S)
        if m:
            try:
                data = json.loads(m.group(0))
                if isinstance(data.get("edicoes"), list):
                    return data["edicoes"]
            except Exception:
                pass
    return []


def _aplicar(texto: str, edicoes: list[dict]) -> tuple[str, int, int]:
    novo = texto
    aplicadas = 0
    rejeitadas = 0
    for ed in edicoes:
        de = str(ed.get("de", "")).strip()
        para = str(ed.get("para", "")).strip()
        if not de or not para:
            continue
        if novo.count(de) != 1:
            rejeitadas += 1
            continue
        novo = novo.replace(de, para)
        aplicadas += 1
    return novo, aplicadas, rejeitadas


def main() -> int:
    # Índice opcional: argumento CLI (ex.: `... 5`) ou env REVISAR_TRECHO.
    alvo = None
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        alvo = int(sys.argv[1])
    elif os.environ.get("REVISAR_TRECHO", "").isdigit():
        alvo = int(os.environ["REVISAR_TRECHO"])

    faixa = [alvo] if alvo is not None else list(range(1, 6))
    print(f"=== Revisão semântica (trechos {faixa}) ===")
    for i in faixa:
        src_path = TRECHOS / f"src_{i}.txt"
        if not src_path.exists():
            print(f"  [{i}] src ausente")
            continue
        texto = src_path.read_text(encoding="utf-8")
        edicoes = _pedir_edicoes(texto)
        revisado, aplicadas, rejeitadas = _aplicar(texto, edicoes)
        (TRECHOS / f"revisado_semantico_{i}.txt").write_text(revisado, encoding="utf-8")
        print(f"  [{i}] {len(texto)} -> {len(revisado)} chars | {aplicadas} edições aplicadas, {rejeitadas} rejeitadas")

    print(f"\nResultados salvos em /tmp/trechos_claude/revisado_semantico_*.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
