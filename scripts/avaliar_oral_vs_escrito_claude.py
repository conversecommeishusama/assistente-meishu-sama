#!/usr/bin/env python3
"""Avaliação comparativa — retradução ORAL vs revisão literária ESCRITA via Claude.

O objetivo é responder à pergunta do usuário: vale a pena fazer a revisão
literária nas traduções orais? Pode ser que o texto oral (retradução direta
do japonês, sem revisão literária) já esteja com qualidade superior ao escrito
que passou por revisão literária.

Cada trecho é submetido à API do Claude (claude-sonnet-5) com:
  - o texto em português (sem o japonês, para não vazar contexto)
  - o glossário de tradução (glossario_traducao.json) para avaliar a aplicação
    da terminologia canônica
  - a informação explícita do TIPO do texto (oral/diálogo vs escrito/prosa)
    para que o avaliador leve em conta a diferença de gênero

Critérios avaliados (1-10):
  - fluencia: as frases fluem naturalmente?
  - sentido_original: o sentido do japonês original é preservado?
  - qualidade_tradutoria: qualidade da tradução em si
  - aplicacao_glossario: uso correto da terminologia canônica
  - qualidade_literaria: é um texto prazeroso de ler?

Uso:
    .venv/bin/python scripts/avaliar_oral_vs_escrito_claude.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, "/var/www/goshinsho")
sys.path.insert(0, "/var/www/goshinsho/goshinsho")

from anthropic import Anthropic

MODELO = os.environ.get("CLAUDE_EVAL_MODEL", "claude-sonnet-5")
MAX_TOKENS = 3000
TRECHOS = Path("/tmp/avaliacao_oral_vs_escrito")


def _claude_client() -> Anthropic:
    env_path = Path("/var/www/goshinsho/.env")
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key and env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("ANTHROPIC_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY não configurada no .env")
    return Anthropic(api_key=key)


def _carregar_glossario() -> str:
    """Carrega o glossário de tradução e monta uma lista compacta dos termos
    mais relevantes (doutrinários/críticos) para o prompt."""
    g = json.loads(Path("/var/www/goshinsho/glossario_traducao.json").read_text(encoding="utf-8"))

    # Termos críticos/doutrinários (os que mais importam para fidelidade)
    chaves_prioritarias = [
        "浄霊", "御浄霊", "御守り", "大光明", "光明", "御軸", "御神体", "大光明如来",
        "光明如来", "伊都能売", "御額", "言霊", "経綸", "霊線", "霊体", "曇り",
        "信者", "教導師", "五六七", "善言讃詞", "審神者", "大浄化", "大清算",
        "土人", "ニグロ", "黒人", "野蛮人", "小乗", "大乗", "末教", "メシヤ教",
        "救世教", "明主様", "御守護", "御霊紙", "御饌米", "祝詞", "御讃歌", "御神書",
        "光明", "祓い", "天国の", "地上天国", "霊界", "憑く", "生霊", "狐", "蛇",
        "龍神", "邪神", "動物霊", "祖先の霊", "精神異状", "精神病", "浄化", "再浄化",
        "薬毒", "毒素", "結核", "マイシン", "ストマイ", "パス", "肋膜", "カリエス",
    ]
    linhas = []
    for chave in chaves_prioritarias:
        if chave in g:
            linhas.append(f"  {chave} → {g[chave]}")
    # Se ainda estiver pequeno, complementar com as primeiras entradas
    if len(linhas) < 40:
        for chave in list(g.keys())[:200]:
            if chave not in chaves_prioritarias:
                linhas.append(f"  {chave} → {g[chave]}")
            if len(linhas) >= 90:
                break
    return "\n".join(linhas)


def _avaliar_trecho(client: Anthropic, metadado: dict, glossario: str) -> dict:
    trecho = (TRECHOS / f"{metadado['id']}.txt").read_text(encoding="utf-8")
    tipo = metadado["tipo"]  # 'oral' ou 'escrito'

    if tipo == "oral":
        desc_tipo = (
            "PALAVRA ORAL — é um DIÁLOGO de sessão de perguntas e respostas "
            "(testemunho do interlocutor + resposta de Meishu-Sama). Registro falado, "
            "com tom coloquial, repetições, pausas e interjeições próprias da fala. "
            "O estilo oral é naturalmente mais solto que a prosa escrita; isso NÃO é defeito."
        )
    else:
        desc_tipo = (
            "PALAVRA ESCRITA — é PROSA doutrinária formal, escrita para publicação "
            "(livro/panfleto). Estilo de ensaio, com vocabulário elevado e construção "
            "elaborada. Foi submetida a uma revisão literária para elevação a padrão de editora."
        )

    prompt = f"""Você é um avaliador independente de QUALIDADE TRADUTÓRIA E LITERÁRIA. Vou te mostrar um TRECHO em português (traduzido do japonês) de uma obra religiosa/filosófica da Igreja Messiânica Mundial (ensinamentos de Meishu-Sama).

## IMPORTANTE — tipo de texto
{desc_tipo}

Leve esse contexto em conta na avaliação: um texto ORAL (diálogo falado) e um texto ESCRITO (prosa de ensaio) têm exigências estilísticas diferentes. O que seria "redundância" numa prosa formal é natural num registro oral; o que seria "coloquial" num diálogo seria inadequado numa obra escrita. Avalie cada um pelo que o seu gênero exige.

## Glossário canônico (terminologia oficial da Igreja — a tradução DEVE seguir estas formas)
{glossario}

Verifique se o trecho usa as formas corretas do glossário quando o termo japonês correspondente aparece (ex.: Johrei, Komyo-Nyorai, Ohikari, espírito da palavra/kotodama, etc.). Termos traduzidos de forma não canônica (ex.: "purificação espiritual" em vez de "Johrei") são penalizados em "aplicacao_glossario".

## O TRECHO
{trecho}

## Avalie com notas de 1 a 10 em 5 critérios:
1. **fluencia** (1-10): as frases fluem naturalmente na língua portuguesa? Sem calques, sem construções arrastadas ou truncadas, sem soletrar o japonês na estrutura do português?
2. **sentido_original** (1-10): o sentido do original japonês (nomes, números, fatos, argumentos) está preservado? Há omissões, acréscimos ou inversões de sentido?
3. **qualidade_tradutoria** (1-10): qualidade da tradução como tradução — escolha lexical, regência, precisão semântica, adequação ao registro (oral ou escrito conforme o caso)?
4. **aplicacao_glossario** (1-10): uso correto e consistente da terminologia canônica do glossário?
5. **qualidade_literaria** (1-10): é um texto prazeroso de ler? Tem cadência, elegância, personalidade? Ou é mecânico/flat?

IMPORTANTE: não seja condescendente. Seja rigoroso como um editor internacional. Dê notas honestas. Também dê uma nota geral (nota_geral 1-10) ponderada.

## Formato de resposta (JSON puro, sem markdown)
{{"fluencia": 0-10, "sentido_original": 0-10, "qualidade_tradutoria": 0-10, "aplicacao_glossario": 0-10, "qualidade_literaria": 0-10, "nota_geral": 0-10, "critica": "3-5 frases específicas e honestas"}}"""

    resp = client.messages.create(
        model=MODELO,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = ""
    for bloco in (resp.content or []):
        if getattr(bloco, "type", "") == "text":
            raw += getattr(bloco, "text", "") or ""
    m = re.search(r"\{.*\}", raw, re.S)
    resultado = {}
    if m:
        try:
            resultado = json.loads(m.group(0))
        except Exception:
            resultado = {"erro_parse": raw[:300]}
    return {"id": metadado["id"], "rotulo": metadado["rotulo"], "tipo": metadado["tipo"], "avaliacao": resultado}


def main() -> int:
    client = _claude_client()
    metadados = json.loads((TRECHOS / "metadados.json").read_text(encoding="utf-8"))
    glossario = _carregar_glossario()

    print(f"=== Avaliação comparativa ORAL (retradução) vs ESCRITO (revisão literária) — {MODELO} ===")
    resultados = []
    for metadado in metadados:
        print(f"\n--- {metadado['id']} ({metadado['rotulo'][:45]}) ---")
        r = _avaliar_trecho(client, metadado, glossario)
        resultados.append(r)
        av = r.get("avaliacao", {})
        if av and "erro_parse" not in av:
            print(f"  Fluência: {av.get('fluencia','?')} | Sentido: {av.get('sentido_original','?')} | "
                  f"Trad.: {av.get('qualidade_tradutoria','?')} | Gloss.: {av.get('aplicacao_glossario','?')} | "
                  f"Lit.: {av.get('qualidade_literaria','?')} | Nota: {av.get('nota_geral','?')}")
            print(f"  Crítica: {av.get('critica','')[:300]}")
        else:
            print(f"  ERRO: {av}")

    out = Path("/var/www/goshinsho/reports/avaliacao_oral_vs_escrito_claude.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(resultados, ensure_ascii=False, indent=2), encoding="utf-8")

    # Médias por grupo
    print("\n=== MÉDIAS POR GRUPO ===")
    criterios = ["fluencia", "sentido_original", "qualidade_tradutoria", "aplicacao_glossario", "qualidade_literaria", "nota_geral"]
    for grupo, nome in [("oral", "ORAL (retradução)"), ("escrito", "ESCRITO (revisão literária)")]:
        grupo_res = [r for r in resultados if r.get("tipo") == grupo]
        if not grupo_res:
            continue
        print(f"\n{nome} ({len(grupo_res)} trechos):")
        for c in criterios:
            vals = [r["avaliacao"].get(c) for r in grupo_res if isinstance(r.get("avaliacao"), dict) and isinstance(r["avaliacao"].get(c), (int, float))]
            if vals:
                print(f"  {c}: {round(sum(vals)/len(vals), 1)}")
    print(f"\nResultado salvo em {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
