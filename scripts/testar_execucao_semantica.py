#!/usr/bin/env python3
"""Teste comparativo: reescrita integral (atual) vs reescrita localizada (semântica).

Processa o MESMO trecho com os DOIS sistemas e salva os resultados para
comparação de qualidade (fluidez, elegância, prazer de leitura, fidelidade).

Sistema A (atual): pede ao DeepSeek o texto revisado COMPLETO (reescrita integral).
Sistema B (semântico): pede ao DeepSeek EDIÇÕES LOCALIZADAS (trecho `de` -> `para`),
  cada uma validada (o `de` deve existir literalmente; âncora preservada).

Uso:
    python3 scripts/testar_execucao_semantica.py <trecho.txt>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "goshinsho"))

from goshinsho.services import ai_service

MODELO = "deepseek-v4-flash"
MAX_TOKENS = 32000

PROTOCOLO = """## Protocolo (resumo — padrão de editora internacional)
- Fluidez e ritmo de frase: reescrever construções arrastadas/truncadas, variar comprimento, eliminar repetição de conectivo, cortar redundância SEM cortar conteúdo.
- Precisão lexical: palavra mais exata e natural em português, sem calques. Vocabulário rico mas não artificial.
- Coesão entre parágrafos: transição natural, sem inventar frase nova.
- NUNCA: mudar sentido/fato/nome/data/número/ordem/citação; adicionar ou cortar informação; alterar conteúdo de citação entre aspas.
- Preservar integralmente: numeração de poemas/versos, autores, títulos, estrutura.

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


def sistema_reescrita_integral(trecho: str) -> str:
    """Sistema A (atual): modelo devolve o texto revisado completo."""
    prompt = f"""{PROTOCOLO}

## Tarefa
Reescreva o texto abaixo (entre <<<SRC>>> e <<<FIM_SRC>>>) aplicando o protocolo, SEM mudar sentido/fato/nome/número/ordem/citação. Preserve a numeração dos poemas (269., 270., ...) e a estrutura.

<<<SRC>>>
{trecho}
<<<FIM_SRC>>>

Retorne APENAS o texto revisado completo, sem comentários."""
    resp = _client().chat.completions.create(
        model=MODELO, messages=[{"role": "user", "content": prompt}],
        temperature=0, max_tokens=MAX_TOKENS,
    )
    return resp.choices[0].message.content or ""


def sistema_semantico_localizado(trecho: str) -> tuple[str, list[dict]]:
    """Sistema B (semântico): modelo propõe EDIÇÕES LOCALIZADAS, aplicadas com validação.

    O modelo retorna uma lista de {de, para}. Cada edição é aplicada apenas se
    `de` existir literalmente no texto (e for único), preservando o restante intacto.
    """
    prompt = f"""{PROTOCOLO}

## Tarefa
Proponha EDIÇÕES LOCALIZADAS para o texto abaixo. Proponha onde houver QUALQUER
ganho real de fluidez, cadência, coesão ou precisão — mesmo que o trecho esteja
gramaticalmente correto. Não deixe parágrafo com eco mecânico ou construção
arrastada sem proposta. Só deixe um trecho intacto se ele já estiver excelente
(isso deve ser a exceção, não a regra).
Regras:
- `de` deve ser um trecho LITERAL EXATO do texto atual (para a ferramenta encontrar).
- `para` é a versão revisada (fluidez/elegância) SEM mudar sentido.
- Não altere numeração, nomes, números, datas, citações.

## Texto atual
{trecho}

## Formato de saída (JSON puro, nada mais)
{{"edicoes": [{{"de": "trecho literal exato", "para": "novo texto"}}]}}"""

    resp = _client().chat.completions.create(
        model=MODELO, messages=[{"role": "user", "content": prompt}],
        temperature=0, max_tokens=MAX_TOKENS,
    )
    raw = resp.choices[0].message.content or ""
    edicoes = []
    m = re.search(r"\{.*\}", raw, re.S)
    if m:
        try:
            data = json.loads(m.group(0))
            edicoes = data.get("edicoes", [])
        except Exception:
            edicoes = []

    # Aplicar edições com validação de âncora
    texto = trecho
    aplicadas = []
    rejeitadas = []
    for ed in edicoes:
        de = ed.get("de", "")
        para = ed.get("para", "")
        if not de or not para:
            continue
        if texto.count(de) != 1:
            rejeitadas.append({"de": de, "motivo": f"aparece {texto.count(de)}x (exigido 1x)"})
            continue
        texto = texto.replace(de, para)
        aplicadas.append(ed)

    return texto, aplicadas + rejeitadas


def main() -> int:
    trecho_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/trecho_teste.txt")
    trecho = trecho_path.read_text(encoding="utf-8")

    print("=== SISTEMA A: REESCRITA INTEGRAL (atual) ===")
    print("Processando...")
    resultado_a = sistema_reescrita_integral(trecho)

    print("=== SISTEMA B: SEMÂNTICA LOCALIZADA ===")
    print("Processando...")
    resultado_b, edicoes = sistema_semantico_localizado(trecho)

    # Salvar resultados
    out = Path("/tmp/teste_semantica")
    out.mkdir(exist_ok=True)
    (out / "trecho_original.txt").write_text(trecho, encoding="utf-8")
    (out / "sistema_a_integral.txt").write_text(resultado_a, encoding="utf-8")
    (out / "sistema_b_semantico.txt").write_text(resultado_b, encoding="utf-8")
    (out / "edicoes_b.json").write_text(json.dumps(edicoes, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\nResultados salvos em {out}")
    print(f"  - trecho_original.txt ({len(trecho)} chars)")
    print(f"  - sistema_a_integral.txt ({len(resultado_a)} chars)")
    print(f"  - sistema_b_semantico.txt ({len(resultado_b)} chars)")
    print(f"  - edicoes_b.json ({len(edicoes)} edições propostas)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
