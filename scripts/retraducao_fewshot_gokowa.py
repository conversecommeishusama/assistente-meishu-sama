#!/usr/bin/env python3
"""Retradução contextual do Gokōwa-roku (Suplemento) — prompt com EXEMPLO FEW-SHOT.

Usa a tradução de referência do usuário como exemplo few-shot no prompt,
explicando o que ela faz de certo, para guiar o agente a reproduzir o estilo.

Teste em trecho DIFERENTE do exemplo (conversa do koto/Beethoven, índices 10+).

Uso:
    python3 scripts/retraducao_fewshot_gokowa.py --pares=10-14
    python3 scripts/retraducao_fewshot_gokowa.py --todos
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

CONTEXTO_OBRA = """CONTEXTO DA OBRA (Gokōwa-roku Suplemento, 1º de janeiro de Showa 23 / 1948, reunião de Ano Novo):
- É um registro manuscrito de uma sessão de perguntas e respostas com Meishu-Sama.
- No início, houve um momento musical: o compositor Sr. Haseo Sugiyama cantou um poema do Grão-Mestre, acompanhado pelo Sr. Shusuke Fukui ao piano.
- Portanto, o INTERLOCUTOR que participa da conversa musical É o compositor Sr. Sugiyama (autor da música "Debune"/出船).
- "Debune" (出船) é uma canção japonesa, composição do interlocutor.
- Yoshie Fujiwara é um famoso cantor/intérprete que apresenta (canta) as composições de outros.
- Shinpei Nakayama é um famoso compositor japonês.
- A conversa é sobre música: koto (instrumento japonês), canções de ninar, Beethoven, Chopin, Schubert, Mozart, jazz, nagauta.
"""

# Tradução de REFERÊNCIA do usuário (few-shot) + explicação do que ela faz certo
EXEMPLO_USUARIO = """EXEMPLO DE TRADUÇÃO DE ALTA QUALIDADE (como deve ser o resultado):

Japonês original (sequência de falas da conversa musical):
Meishu-Sama: ああそうですか、あんたの『出船』は藤原義江がよくやりますね。
Interlocutor: ――藤原さんがほとんど紹介してくれました。
Meishu-Sama: 作曲家はいいものです。
Interlocutor: ――どうも貧乏で困ります。
Meishu-Sama: いや両方いいのは難しい。

Tradução de referência (do revisor humano):
Meishu-Sama: Ah, é mesmo? Yoshie Fujiwara tem apresentado muito a sua [composição] Debune.
Interlocutor: O senhor Fujiwara tem feito praticamente todas as apresentações.
Meishu-Sama: É que o compositor é excelente.
Interlocutor: Mesmo assim tenho sofrido com a pobreza.
Meishu-Sama: É difícil ter as duas coisas bem (ser compositor e prosperar).

POR QUE esta tradução é excelente (o que ela faz de certo):
1. ESCLARECE OS PAPÉIS: identifica que "sua" se refere à composição do interlocutor; que Fujiwara é o intérprete que apresenta as obras.
2. ESCLARECE AS REFERÊNCIAS: "[composição]" em colchetes deixa claro que "Debune" é uma obra; "(ser compositor e prosperar)" explica o que são "as duas coisas".
3. USA CONECTIVOS NATURAIS: "É que", "Mesmo assim" amarram as falas ao contexto anterior sem inventar conteúdo.
4. NÃO INVERTE SUJEITO/OBJETO: mantém Fujiwara como quem apresenta (agente), não como quem foi apresentado.
5. MANTÉM O TOM: preserva o lamento ("tenho sofrido com a pobreza") e o coloquialismo, sem polir demais.
"""

PROMPT = """{contexto}

{exemplo}

Agora traduza com a MESMA qualidade do exemplo acima. Aplique os MESMOS princípios:
- Identifique os papéis dos falantes pelo contexto e traduza de modo que o leitor entenda quem é quem.
- Esclareça referências ambíguas com [colchetes] quando necessário.
- Use conectivos naturais do português para amarrar as falas.
- NUNCA inverta sujeito/objeto. NUNCA mude quem fez a ação.
- Mantenha o tom do original (lamento, coloquialismo, etc.).
- Não invente conteúdo que não exista no japonês.

Traduza esta FALA do personagem "{quem}".

### JAPONÊS:
{jp}

### TRADUÇÃO (responda SÓ com o texto traduzido):
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


def retraduzir(jp: str, quem: str) -> str:
    from goshinsho.services.agentic_search import _client

    for tentativa in range(5):
        reforco = ""
        if tentativa == 1:
            reforco = "\n\nResponda APENAS a tradução, sem comentários."
        elif tentativa == 2:
            reforco = "\n\nSaída: só o texto traduzido, nada mais."
        resp = _client().chat.completions.create(
            model=MODELO,
            max_tokens=400,
            messages=[{"role": "user", "content": PROMPT.format(contexto=CONTEXTO_OBRA, exemplo=EXEMPLO_USUARIO, jp=jp, quem=quem) + reforco}],
            temperature=0.2,
        )
        raw = (resp.choices[0].message.content or "").strip().strip('"').strip()
        raw = re.sub(r"^(Meishu-Sama|Interlocutor):\s*", "", raw)
        if raw and len(raw) > 2:
            return raw
    return "(falha)"


def main() -> None:
    falas_jp = extrair_falas(JP.read_text(encoding="utf-8"))
    falas_pt = extrair_falas(PT.read_text(encoding="utf-8"))
    n = min(len(falas_jp), len(falas_pt))

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
        indices = list(range(n))

    print(f"Retradução FEW-SHOT de {len(indices)} falas...\n")
    resultados = []
    for i in indices:
        if i >= n:
            continue
        quem, jp = falas_jp[i]
        pt_atual = falas_pt[i][1]
        pt_novo = retraduzir(jp, quem)
        resultados.append({
            "indice": i,
            "quem": quem,
            "jp": jp,
            "pt_atual": pt_atual,
            "pt_fewshot": pt_novo,
        })
        print(f"=== [{i}] {quem} ===")
        print(f"  JP      : {jp}")
        print(f"  ATUAL   : {pt_atual}")
        print(f"  FEWSHOT : {pt_novo}")
        print()

    OUT.mkdir(parents=True, exist_ok=True)
    arq = OUT / "retraducao_fewshot_gokowa.json"
    arq.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Salvo: {arq} ({len(resultados)} falas)")


if __name__ == "__main__":
    main()
