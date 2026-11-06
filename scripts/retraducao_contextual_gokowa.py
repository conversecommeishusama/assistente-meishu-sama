#!/usr/bin/env python3
"""Retradução CONTEXTUAL do Gokōwa-roku (Suplemento) — estilo "leitor esclarecido".

Objetivo: reproduzir o estilo de tradução que esclarece o contexto (como a
tradução de referência do usuário), em vez de manter ambiguidades cruas.

Regras do estilo (extraídas da tradução de referência do usuário):
  1. Identificar os PAPÉIS dos falantes a partir do contexto (ex: o interlocutor
     é o compositor; Fujiwara é o intérprete).
  2. Esclarecer referências ambíguas quando o contexto permite ("a sua [composição]
     Debune", "É que o compositor é excelente").
  3. Usar conectivos naturais do português ("É que", "Mesmo assim") para amarrar
     as falas, sem inventar conteúdo.
  4. Adicionar [colchetes] apenas quando uma palavra precisa de esclarecimento
     que não existe no original (ex: "[composição]").
  5. Manter fidelidade estrita ao sentido do japonês — nunca inverter sujeito/objeto.

Uso:
    python3 scripts/retraducao_contextual_gokowa.py --pares=2-6
    python3 scripts/retraducao_contextual_gokowa.py --todos
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

# Contexto fixo da obra (para o modelo identificar papéis corretamente)
CONTEXTO_OBRA = """CONTEXTO DA OBRA (Gokōwa-roku Suplemento, 1º de janeiro de Showa 23 / 1948, reunião de Ano Novo):
- É um registro manuscrito de uma sessão de perguntas e respostas com Meishu-Sama.
- No início, houve um momento musical: o compositor Sr. Haseo Sugiyama cantou um poema do Grão-Mestre, acompanhado pelo Sr. Shusuke Fukui ao piano.
- Portanto, o INTERLOCUTOR que participa da conversa musical É o compositor Sr. Sugiyama (autor da música "Debune"/出船).
- "Debune" (出船) é uma canção japonesa, composição do interlocutor.
- Yoshie Fujiwara é um famoso cantor/intérprete que apresenta (canta) as composições de outros.
- Shinpei Nakayama é um famoso compositor japonês.
- A conversa é sobre música: koto (instrumento japonês), canções de ninar, Beethoven, Chopin, Schubert, Mozart, jazz, nagauta.
"""

# Exemplo few-shot — tradução de REFERÊNCIA do usuário (estilo desejado)
# Cada exemplo mostra o padrão: esclarecer papéis, conectar falas, [colchetes] p/ contexto.
EXEMPLO_REFERENCIA = """EXEMPLO DE TRADUÇÃO IDEAL (feita por um leitor experiente da obra):

FALA 1:
JP: ああそうですか、あんたの『出船』は藤原義江がよくやりますね。
PT: Ah, é mesmo? Yoshie Fujiwara tem apresentado muito a sua [composição] Debune.
(Explicação: "あんたの" = "sua" — refere-se ao interlocutor, que é o compositor.
 "藤原義江が...やります" = "Fujiwara apresenta" — ele é o intérprete. O colchete
 [composição] esclarece que Debune é uma composição, sem inventar texto.)

FALA 2:
JP: 藤原さんがほとんど紹介してくれました。
PT: O senhor Fujiwara tem feito praticamente todas as apresentações.
(Explicação: "紹介してくれました" = "apresentou [a obra]" — Fujiwara apresenta a
 COMPOSIÇÃO do interlocutor. NUNCA inverter: Fujiwara é quem apresenta.)

FALA 3:
JP: 作曲家はいいものです。
PT: Ser compositor é uma coisa boa.
(Explicação: o "は"+もの generaliza — refere-se à PROFISSÃO de ser compositor,
 não a um compositor específico. "Ser compositor" captura essa abstração.)

FALA 4:
JP: いや両方いいのは難しい。
PT: É difícil ter as duas coisas bem (ser compositor e prosperar).
(Explicação: o parêntese esclarece quais são "as duas coisas" no contexto —
 sem acrescentar conteúdo, apenas tornando explícito o que o contexto já diz.)

O que o exemplo ensina:
- Esclareça QUEM fala e PARA QUEM cada referência se dirige.
- Esclareça o que uma referência ambígua significa no contexto, com [colchetes] ou
  parênteses quando necessário (sem inventar conteúdo).
- Use conectivos naturais do português ("É que", "Mesmo assim", "Por isso") para
  amarrar as falas.
- NUNCA inverta sujeito/objeto (quem faz a ação fica fazendo).
- "は+もの" no japonês generaliza (a profissão/estado) — traduza com "Ser X é..."
"""

PROMPT = """{contexto}

{exemplo}

Você é um tradutor japonês→português que produz traduções no ESTILO do exemplo acima: que ESCLARECEM o contexto para o leitor, mantendo fidelidade estrita ao original.

Regras do estilo (reforço):
1. Identifique os PAPÉIS dos falantes pelo contexto (quem é o compositor, quem é o intérprete, etc.) e traduza de modo que o leitor entenda a quem cada referência se dirige.
2. Esclareça referências ambíguas quando o contexto permite — use [colchetes] ou parênteses para tornar explícito o que o contexto já indica, SEM inventar conteúdo.
3. Use conectivos naturais do português ("É que", "Mesmo assim", "Por isso") para amarrar as falas.
4. NUNCA inverta sujeito/objeto. NUNCA mude quem fez a ação.
5. Quando o japonês usar "は+もの" generalizando (a profissão/estado), traduza com "Ser X é...".
6. Respeite o tom truncado/coloquial quando o original for assim — esclareça sem "polir" demais.

Traduza esta FALA do personagem "{quem}".

### JAPONÊS:
{jp}

### TRADUÇÃO (responda SÓ com o texto traduzido, sem aspas externas):
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
            max_tokens=600,
            messages=[{"role": "user", "content": PROMPT.format(contexto=CONTEXTO_OBRA, exemplo=EXEMPLO_REFERENCIA, jp=jp, quem=quem) + reforco}],
            temperature=0.2,
        )
        raw = (resp.choices[0].message.content or "").strip().strip('"').strip()
        # remover prefixo "Meishu-Sama:"/"Interlocutor:" se o modelo repetir
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

    print(f"Retradução contextual de {len(indices)} falas...\n")
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
            "pt_contextual": pt_novo,
        })
        print(f"=== [{i}] {quem} ===")
        print(f"  JP      : {jp}")
        print(f"  ATUAL   : {pt_atual}")
        print(f"  CONTEXT : {pt_novo}")
        print()

    OUT.mkdir(parents=True, exist_ok=True)
    arq = OUT / "retraducao_contextual_gokowa.json"
    arq.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Salvo: {arq} ({len(resultados)} falas)")


if __name__ == "__main__":
    main()
