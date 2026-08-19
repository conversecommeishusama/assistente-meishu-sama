#!/usr/bin/env python3
"""Teste controlado: retraduzir ESCRITOS (Curso Kannon) com o processo atual.

Hipótese do usuário: o processo de retradução por trechos (DeepSeek) pode
superar a revisão literária dos escritos. Teste no Curso Kannon (prosa formal,
difícil). Se a retradução superar a revisada, é um bom sinal.

Método:
1. Extrai 3 trechos de ~2000 chars do JP do Curso Kannon (início/meio/fim).
2. Traduz cada um com o DeepSeek usando o PROMPT do executor (glossário
   completo + regras de reconstrução/anti-invenção/sujeito), com APENAS a
   adequação mecânica de DIÁLOGO → PROSA (referências a "fala"/"falante" →
   "texto"/"parágrafo"). Nenhuma capacidade é removida.
3. Salva os pares em /tmp/teste_retrad_escritos/ para avaliação cega pelo Claude
   (retradução nova vs revisada literariamente, ambas sobre o mesmo JP).

Uso:
    .venv/bin/python scripts/teste_retrad_escritos.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))
os.chdir(RAIZ)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(RAIZ / ".env")

from retraducao_completa_gokowa import (  # noqa: E402
    CONTEXTO_OBRA,
    EXEMPLO_REFERENCIA,
    PROMPT,
    carregar_glossario_completo,
)

OUT = Path("/tmp/teste_retrad_escritos")
JP_PATH = RAIZ / "textos_japones" / "19350000-観音講座　（１～７）.txt"
LIMITE_TRECHO = 2000

# Adequação DIÁLOGO → PROSA: substituições mecânicas no PROMPT do executor.
# Mantém TODAS as regras (reconstrução, anti-invenção, sujeito, glossário);
# apenas troca o vocabulário de "fala/falante" por "texto/parágrafo".
ADEQUACAO_PROSA = [
    # Estrutura de contexto
    ("é um registro manuscrito de uma sessão de perguntas e respostas com Meishu-Sama.",
     "é um curso escrito (prosa doutrinária formal) de Meishu-Sama, transcrito por um discípulo."),
    ("o INTERLOCUTOR que participa da conversa musical É o compositor Sr. Sugiyama",
     "o texto é prosa formal doutrinária, não diálogo — não há interlocutor; é a fala direta de Meishu-Sama"),
    # Instrução de tradução contínua (ETAPA 1)
    ("Este texto contém um DIÁLOGO com falas de Meishu-Sama e do "
     "Interlocutor (os rótulos 'Interlocutor:' / 'Meishu-Sama:' marcam a "
     "mudança de falante). Traduza o texto inteiro para o português de forma "
     "contínua e natural, preservando TODOS os sentidos e a ordem das falas. "
     "Não é necessário manter os rótulos no texto traduzido.",
     "Este texto é PROSA FORMAL doutrinária em japonês (curso escrito de Meishu-Sama). "
     "Traduza o texto inteiro para o português de forma contínua e natural, preservando "
     "TODOS os sentidos, a ordem das ideias e o tom solene e formal do original."),
    # Regra 1: papéis dos falantes → unidade de sentido
    ("Identifique os PAPÉIS dos falantes pelo contexto (quem é o compositor, quem é o intérprete, etc.) e traduza de modo que o leitor entenda a quem cada referência se dirige.",
     "Identifique a UNIDADE DE SENTIDO de cada trecho pelo contexto e traduza de modo que o leitor entenda exatamente o que cada referência significa no fluxo da exposição."),
    # Regra 3: amarrar as falas → amarrar os parágrafos
    ('Use conectivos naturais do português ("É que", "Mesmo assim", "Por isso") para amarrar as falas.',
     'Use conectivos naturais do português ("É que", "Mesmo assim", "Por isso", "Portanto") para amarrar os parágrafos e dar coesão à exposição.'),
    # Regra 6: reconstrução — fala telegráfica → prosa
    ("RECONSTRUÇÃO NECESSÁRIA PARA FLUIDEZ E CLAREZA: o japonês original é telegráfico/truncado\n   (registro de anotações). Você DEVE reconstruir a frase o quanto for necessário para que ela\n   soe natural, fluida e clara em português brasileiro — completando palavras elípticas,\n   reordenando, suavizando o truncamento. A régua é: mantenha TODO o sentido e TODOS os fatos\n   do original, NÃO omita nada, NÃO acrescente fato novo. Fidelidade de sentido é a régua,\n   não literalidade. Não fique preso à forma truncada — o leitor não precisa sofrer com a\n   forma bruta das anotações, desde que nada se perca.",
     "RECONSTRUÇÃO NECESSÁRIA PARA FLUIDEZ E CLAREZA: o japonês original é prosa formal do\n   início do século XX, com períodos longos e estrutura da época. Você DEVE adequar o período\n   para o português brasileiro contemporâneo — reordenando orações, ajustando o ritmo,\n   tornando a leitura fluida e natural, SEM perder o tom solene e doutrinário. A régua é:\n   mantenha TODO o sentido e TODOS os fatos do original, NÃO omita nada, NÃO acrescente fato\n   novo. Fidelidade de sentido é a régua, não literalidade. Não copie a sintaxe pesada do\n   japonês — o leitor deve ler com fluidez, sem que nada se perca."),
    # Regra 7: prevenção de inversão — falas → frases
    ("7. PREVENÇÃO DE INVERSÃO DE SUJEITO/PESSOA (REGRA AMPLA — vale para qualquer fala):",
     "7. PREVENÇÃO DE INVERSÃO DE SUJEITO/PESSOA (REGRA AMPLA — vale para qualquer frase):"),
    ("      — não invente \"eu\"/\"nós\"/\"você\" sem base. Se a fala anterior estabeleceu que o agente",
     "      — não invente \"eu\"/\"nós\"/\"você\" sem base. Se o trecho anterior estabeleceu que o agente"),
    ("      mantenha o feminino até o fim da fala. Se o referente é um terceiro (Nakayama,",
     "      mantenha o feminino até o fim do trecho. Se o referente é um terceiro (Nakayama,"),
    ("   deduza do CONTEXTO (fala anterior, lógica da frase, quem está falando). Só então",
     "   deduza do CONTEXTO (trecho anterior, lógica da frase, quem é o agente). Só então"),
    ("9. ANTI-INVENÇÃO (REGRA CRÍTICA — vale para qualquer fala):",
     "9. ANTI-INVENÇÃO (REGRA CRÍTICA — vale para qualquer trecho):"),
    ("10. PESSOA GRAMATICAL (REGRA CRÍTICA — erro real observado na fala 85):",
     "10. PESSOA GRAMATICAL (REGRA CRÍTICA — erro real observado no trecho 85):"),
    ("      que a ação é de/sobre um TERCEIRO, não o falante. Mantenha essa distância.",
     "      que a ação é de/sobre um TERCEIRO, não o autor. Mantenha essa distância."),
    # Regra 8: identificar sujeito — fala anterior → contexto
    ("Use o CONTEXTO DA FALA ANTERIOR (se fornecido) para resolver あれ/それ/彼/この人.",
     "Use o CONTEXTO PRÓXIMO (frase/parágrafo anterior) para resolver あれ/それ/彼/この人."),
    # Regra 9: anti-invenção — fala anterior → texto anterior
    ("Use a forma\n      impessoal ou deixe implícito, a menos que a fala ANTERIOR (contexto fornecido)\n      estabeleça claramente o referente.",
     "Use a forma\n      impessoal ou deixe implícito, a menos que o texto ANTERIOR (contexto fornecido)\n      estabeleça claramente o referente."),
    ("c. NUNCA invente CAUSA/instrumento: se o JP diz \"não se deve fazer\" (やってはいけない)\n      sem especificar o quê, NÃO escreva \"[injeções]\". O [colchete] só pode tornar\n      explícito o que o JP ou o contexto JÁ estabelecem explicitamente.",
     "c. NUNCA invente CAUSA/instrumento: se o JP diz \"não se deve fazer\" (やってはいけない)\n      sem especificar o quê, NÃO escreva \"[injeções]\". O [colchete] só pode tornar\n      explícito o que o JP ou o contexto JÁ estabelecem explicitamente."),
    ("f. Depois de traduzir, RELEIA conferindo: \"cada [colchete] e cada detalhe adicionado\n      tem base EXPLÍCITA no JP ou no contexto da fala anterior? Se não, remova.\"",
     "f. Depois de traduzir, RELEIA conferindo: \"cada [colchete] e cada detalhe adicionado\n      tem base EXPLÍCITA no JP ou no contexto do texto anterior? Se não, remova.\""),
    # Regra 10: pessoa gramatical — fala → frase
    ("MANTENHA EXATAMENTE a pessoa gramatical do japonês (1ª vs 3ª). O falante pode\n   estar RELATANDO a experiência de OUTRA pessoa — não é porque alguém narra um\n   caso que o caso é dele.",
     "MANTENHA EXATAMENTE a pessoa gramatical do japonês (1ª vs 3ª). O autor pode\n   estar RELATANDO a experiência de OUTRA pessoa — não é porque alguém narra um\n   caso que o caso é dele."),
    # Instrução final: "fala do personagem X" → "texto"
    ('Traduza esta FALA do personagem "{quem}".',
     'Traduza o TEXTO abaixo (prosa doutrinária formal).'),
    # Fim: GLOSSÁRIO mantido integralmente
]

# Contexto específico do Curso Kannon (adequado para prosa)
CONTEXTO_KANNON = """CONTEXTO DA OBRA (Curso Kannon / 観音講座, 1935, vols 1-7):
- É um curso doutrinário de Meishu-Sama (prosa formal, transcrito por um discípulo).
- Expõe a doutrina da Igreja Messiânica Mundial: o Propósito do Deus Supremo,
  o Plano Divino do Céu e da Terra, a criação, o mundo espiritual, a purificação,
  Johrei, a salvação.
- Tom: solene, didático, doutrinário — exposição formal, não diálogo.
- Termos consagrados: Ohikari, Johrei, Kannon-Sama, Plano Divino, Grande
  Purificação, Grande Acerto de Contas, nuvens espirituais, etc. (ver glossário).
"""


def _client():
    from openai import OpenAI
    return OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")


def extrair_corpo_jp() -> str:
    """Extrai o corpo do Curso Kannon (remove metadados) e retorna o texto."""
    txt = JP_PATH.read_text(encoding="utf-8")
    linhas = txt.splitlines()
    inicio = 0
    for i, l in enumerate(linhas):
        if l.startswith("Collection ID:"):
            inicio = i + 1
            break
    return "\n".join(linhas[inicio:])


def extrair_trechos(corpo: str, n: int = 3, limite: int = LIMITE_TRECHO) -> list[dict]:
    """Extrai n trechos de ~limite chars distribuídos no corpo (início/meio/fim).

    Garante que nenhum trecho ultrapasse `limite` de forma significativa:
    - primeiro tenta agrupar parágrafos inteiros até ~limite;
    - parágrafos MAIORES que o limite são cortados em fatias de ~limite na
      fronteira de frase (。！？.!?…) para nunca estourar.
    """
    pars = [p.strip() for p in re.split(r"\n\s*\n", corpo) if p.strip() and len(p.strip()) > 20]
    # remove os cabeçalhos (título, data, "第一講座", etc.)
    pars = [p for p in pars if not re.match(r"^[一二三四五六七八九十]+講座$", p)
            and not re.match(r"^昭和\d+", p)
            and not p.startswith("観音講座")]

    def fatiar_paragrafo(p: str) -> list[str]:
        """Corta um parágrafo grande em fatias de ~limite chars em fronteira de frase."""
        if len(p) <= limite:
            return [p]
        frases = re.split(r"(?<=[。！？.!?…])", p)
        fatias = []
        atual = ""
        for f in frases:
            if len(atual) + len(f) > limite and atual:
                fatias.append(atual)
                atual = f
            else:
                atual += f
        if atual:
            fatias.append(atual)
        return fatias

    # montar lista de segmentos (parágrafos inteiros ou fatias de grandes)
    segmentos = []
    for p in pars:
        if len(p) > limite:
            segmentos.extend(fatiar_paragrafo(p))
        else:
            segmentos.append(p)

    # agrupar segmentos em trechos de ~limite
    trechos = []
    atual = []
    tamanho = 0
    for seg in segmentos:
        if tamanho + len(seg) > limite and atual:
            trechos.append("\n\n".join(atual))
            atual = []
            tamanho = 0
        atual.append(seg)
        tamanho += len(seg)
    if atual:
        trechos.append("\n\n".join(atual))

    # selecionar n trechos distribuídos (início, meio, fim), preferindo os
    # que estão próximos do limite (amostra representativa de ~2000 chars)
    bons = [t for t in trechos if len(t) >= limite * 0.8] or trechos
    if len(bons) <= n:
        selecionados = bons
    else:
        indices = sorted(set([0, len(bons) // 2, len(bons) - 1]))
        selecionados = [bons[i] for i in indices[:n]]
    return [{"jp": t, "chars": len(t)} for t in selecionados]


def traduzir_prosa(jp: str, contexto: str, exemplo: str, glossario: str) -> str:
    """Traduz um trecho de prosa com o PROMPT do executor, adequado para escrita."""
    prompt_base = PROMPT.format(
        contexto=contexto,
        exemplo=exemplo,
        glossario_completo=glossario,
        jp=jp,
        quem="o texto",
    )
    # Adequação diálogo → prosa (mecânica, sem perder capacidade)
    for de, para in ADEQUACAO_PROSA:
        prompt_base = prompt_base.replace(de, para)

    # Regra GENÉRICA sobre estruturas não-prosaicas (anti-tutela: não cita caso
    # específico; aplica-se a qualquer trecho que contenha tabelas, diagramas,
    # listas de caracteres/kana ou decomposições fonéticas).
    prompt_base += """

## ESTRUTURAS NÃO-PROSAICAS (regra geral, aplica-se a QUALQUER trecho)
O texto pode conter blocos que não são prosa corrida: tabelas, diagramas,
listas alinhadas de caracteres, sequências de kana/silabário ou decomposições
fonéticas/etimológicas de palavras.

Regras para esses blocos:
- PRESERVE-OS INTEGRALMENTE: nunca omita uma tabela, um diagrama ou uma
  sequência de caracteres presente no original. A omissão de qualquer bloco é
  erro grave de fidelidade.
- Quando o bloco representar SOM ou FONÉTICA (sílabas, leituras, pronúncia,
  decomposição sonora de palavras), use a REPRESENTAÇÃO FONÉTICA (romanização)
  como forma principal, alinhada ao original se houver estrutura de colunas.
  O caractere gráfico (kanji/kana) só precisa ser mantido se o próprio texto
  estiver analisando a FORMA ESCRITA do caractere como tema — não quando está
  analisando o som.
- NUNCA deixe um bloco do original sem correspondência no português: se houver
  leitura fonética (furigana/kana/romaji) no original, reproduza-a no português.
- NUNCA acrescente tabela, coluna, linha ou caractere que não exista no original.
"""

    reforcos = [
        "",
        "\n\nTraduza o texto inteiro agora, sem omitir nada.",
        "\n\nSaída: só a tradução, sem comentários.",
        "\n\nNão deixe em branco. Traduza todo o texto.",
        "\n\nIMPORTANTE: sua resposta anterior veio vazia. Traduza o texto completo agora.",
        "\n\nAgora sim, escreva a tradução completa:",
    ]
    ultimo_erro = None
    for tentativa in range(8):
        reforco = reforcos[tentativa] if tentativa < len(reforcos) else "\n\nTraduza agora."
        try:
            resp = _client().chat.completions.create(
                model="deepseek-v4-flash",
                max_tokens=40000,
                messages=[{"role": "user", "content": prompt_base + reforco}],
                temperature=0.2,
            )
            raw = (resp.choices[0].message.content or "").strip().strip('"').strip()
            if not raw or len(re.sub(r"\s", "", raw)) < 10:
                raise ValueError("resposta vazia")
            return raw
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            print(f"    [retry {tentativa+1}] {type(e).__name__}: {str(e)[:100]}", flush=True)
            time.sleep(3 * (tentativa + 1))
    print(f"  ERRO: tradução falhou após retries: {ultimo_erro}")
    return ""


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    corpo = extrair_corpo_jp()
    trechos = extrair_trechos(corpo, n=3)
    glossario = carregar_glossario_completo()

    print(f"=== Teste retradução ESCRITOS (Curso Kannon) — {len(trechos)} trechos ===")
    resultados = []
    for i, t in enumerate(trechos):
        print(f"\n--- Trecho {i+1} ({t['chars']} chars JP) ---")
        # salvar JP
        (OUT / f"trecho_{i+1}_jp.txt").write_text(t["jp"], encoding="utf-8")
        # traduzir
        inicio = time.time()
        pt = traduzir_prosa(t["jp"], CONTEXTO_KANNON, EXEMPLO_REFERENCIA, glossario)
        tempo = time.time() - inicio
        if pt:
            (OUT / f"trecho_{i+1}_novo.txt").write_text(pt, encoding="utf-8")
            print(f"  -> {tempo:.1f}s | {len(t['jp'])} JP -> {len(pt)} PT")
            resultados.append({"idx": i + 1, "jp_chars": len(t["jp"]), "pt_chars": len(pt), "tempo_s": round(tempo, 1)})
        else:
            print(f"  -> FALHOU")
            resultados.append({"idx": i + 1, "jp_chars": len(t["jp"]), "pt_chars": 0, "tempo_s": 0, "falha": True})

    (OUT / "resultados.json").write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResultados salvos em {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
