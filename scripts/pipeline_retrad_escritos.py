#!/usr/bin/env python3
"""Pipeline completo (retradução→auditoria→ajuste) aplicado aos ESCRITOS.

Para a comparação justa (Curso Kannon), a retradução nova deve passar pelo
MESMO pipeline das orais:
  1. Retradução (já feita: /tmp/teste_retrad_escritos/trecho_*_novo.txt)
  2. AUDITORIA: auditar cada trecho (JP vs PT) com DeepSeek, SYSTEM_PROMPT do
     auditor + glossário. Verdititos ERRO_TRADUCAO/OK.
  3. AJUSTE: para cada ERRO_TRADUCAO, executor corrige (re-traduz com erro como
     reforço + glossário), re-audita, até 3 tentativas.

Resultado: /tmp/teste_retrad_escritos/trecho_*_final.txt (a versão "pipelinada"
que será comparada com a revisão literária).

Uso:
  .venv/bin/python scripts/pipeline_retrad_escritos.py
"""
from __future__ import annotations

import importlib.util
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

from retraducao_completa_gokowa import (
    CONTEXTO_OBRA,
    EXEMPLO_REFERENCIA,
    PROMPT,
    carregar_glossario_completo,
)  # noqa: E402
from teste_retrad_escritos import CONTEXTO_KANNON, ADEQUACAO_PROSA  # noqa: E402

# Auditor (SYSTEM_PROMPT + extrair_json)
_spec = importlib.util.spec_from_file_location(
    "auditor_base", RAIZ / "scripts" / "auditar_lote_gokowa_api.py"
)
_auditor = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_auditor)

PASTA = Path("/tmp/teste_retrad_escritos")
MODELO = "deepseek-v4-flash"
MAX_TOKENS = 40000
MAX_TENTATIVAS = 3

# SYSTEM_PROMPT HÍBRIDO: semântica + LITERAL/ESTRUTURAL (cobertura de blocos
# não-prosaicos: tabelas, diagramas, sequências de kana/kanji). A auditoria
# semântica pura não detectava omissão de tabela (ex.: T1 omitiu o gojūon).
SYSTEM_PROMPT_HIBRIDO = """Você é um auditor de tradução rigoroso e imparcial. Sua
única tarefa é comparar um trecho em japonês (JP) com sua tradução para o
português (PT) e julgar se a tradução está correta.

Você deve verificar DUAS dimensões, AMBAS obrigatórias:

A) SEMÂNTICA (sentido):
1. O PT transmite o mesmo significado do JP? (sentido preservado)
2. Houve inversão de sujeito/objeto? (quem faz a ação continua fazendo?)
3. Houve omissão de FRASE ou acréscimo de conteúdo inventado?
4. Termos corretos? (nomes próprios, datas, conceitos doutrinários)
5. Negativas corretas? (ex: "nem...nem" vs "ou...ou")
6. Inserções esclarecedoras [colchetes] estão corretas e não contradizem o JP?
7. A RECONSTRUÇÃO foi feita sem omitir/acrescentar fato?

B) LITERAL / ESTRUTURAL (cobertura — NUNCA pular esta dimensão):
O JP pode conter BLOCOS NÃO-PROSAICOS: tabelas, diagramas, listas alinhadas,
sequências de caracteres (kana/kanji/romaji), silabários, decomposições
fonéticas/etimológicas. Verifique elemento a elemento:
1. Todas as frases do JP têm correspondência no PT?
2. Todas as TABELAS, DIAGRAMAS, LISTAS e SEQUÊNCIAS DE CARACTERES do JP
   aparecem no PT (traduzidas, romanizadas ou preservadas)?
3. Nenhuma tabela/linha/diagrama/bloco do JP foi omitida?
Para verificar: procure no JP por blocos visuais (linhas curtas com caracteres
espaçados, sequências de kana como ア イ ウ エ オ, listas alinhadas, colunas) e
confirme que cada um tem correspondência no PT.

Se houver OMISSÃO de bloco/tabela/estrutura (mesmo que o sentido das frases ao
redor esteja certo), marque ERRO_TRADUCAO e aponte o bloco omitido.

GLOSSÁRIO DE REFERÊNCIA (autoridade terminológica — use para julgar se o termo
JP foi vertido para a forma correta em PT). Se o JP contém um termo abaixo e o
PT NÃO usa a forma indicada (ou usa um sinônimo que foge à forma fixada),
marque como ERRO_TRADUCAO e sugira a forma correta.

REGRAS SEMÂNTICAS ADICIONAIS:
- AMULETOS vs IMAGENS: amuletos (御守り, carregados no pescoço) = Ohikari/Kōmyō/
  Daikōmyō; imagens (御軸, adoradas) = Kōmyō Nyorai/Daikōmyō Nyorai. Não confundir.
- 大清算 (Grande Acerto de Contas) ≠ 大浄化 (Grande Purificação) — são distintos.
- Johrei, Ohikari, Kannon, Meishu-Sama — termos consagrados, preservar.
- O original pode ser registro truncado/telegráfico; a tradução DEVE fazer
  reconstrução para fluidez, com [colchetes] esclarecedores quando tornam explícito
  o que o contexto já indica — isso NÃO é erro, desde que não contradiga o JP nem
  invente fato novo.

Responda SOMENTE com um JSON válido, sem texto ao redor, no formato:
{{"veredito": "OK" | "ERRO_TRADUCAO", "erro": null | "<descrição curta do erro>", "correcao": "<correção sugerida, se ERRO_TRADUCAO>"}}

Para "OK", "erro" e "correcao" devem ser null.
Para "ERRO_TRADUCAO", preencha "erro" (o que está errado) e "correcao" (como corrigir).
IMPORTANTE: se a tradução usa os termos conforme o glossário acima, NÃO marque como erro."""




def _client():
    from openai import OpenAI
    return OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")


def adequar_prompt_prosa(prompt: str) -> str:
    """Aplica a adequação diálogo→prosa ao prompt do executor."""
    for de, para in ADEQUACAO_PROSA:
        prompt = prompt.replace(de, para)
    return prompt


def auditar_trecho(client, idx: int, jp: str, pt: str) -> dict:
    """Audita um trecho (JP vs PT) com DeepSeek. Retorna veredito."""
    prompt_usuario = (
        f"AUDITORIA DE TRADUÇÃO — trecho {idx} (prosa doutrinária formal)\n\n"
        f"--- JP (original) ---\n{jp}\n\n"
        f"--- PT (tradução a auditar) ---\n{pt}\n\n"
        "Compare o PT com o JP e responda com o JSON de veredito."
    )
    ultimo_erro = None
    for tentativa in range(6):
        try:
            resp = _client().chat.completions.create(
                model=MODELO,
                max_tokens=MAX_TOKENS,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT_HIBRIDO},
                    {"role": "user", "content": prompt_usuario},
                ],
            )
            texto = resp.choices[0].message.content or ""
            dados = _auditor.extrair_json(texto)
            if dados is None:
                raise ValueError("sem JSON")
            veredito = dados.get("veredito")
            if veredito in ("OK", "ERRO_TRADUCAO"):
                return dados
            raise ValueError(f"veredito inválido: {veredito}")
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            time.sleep(3 * (tentativa + 1))
    return {"veredito": "FALHA_API", "erro": str(ultimo_erro)[:200], "correcao": None}


def executor_corrigir(idx: int, jp: str, pt_atual: str, erro: dict) -> str:
    """Re-traduz o trecho com o erro da auditoria como reforço (glossário no prompt)."""
    prompt_base = PROMPT.format(
        contexto=CONTEXTO_KANNON,
        exemplo=EXEMPLO_REFERENCIA,
        glossario_completo=carregar_glossario_completo(),
        jp=jp,
        quem="o texto",
    )
    prompt_base = adequar_prompt_prosa(prompt_base)

    # Regra GENÉRICA de estruturas não-prosaicas (anti-tutela) — o executor
    # precisa saber preservar/romanizar tabelas e diagramas ao corrigir.
    prompt_base += """\n\n## ESTRUTURAS NÃO-PROSAICAS (regra geral)\nO texto pode conter blocos que não são prosa corrida: tabelas, diagramas,\nlistas alinhadas de caracteres, sequências de kana/silabário ou decomposições\nfonéticas/etimológicas de palavras.\n- PRESERVE-OS INTEGRALMENTE: nunca omita uma tabela, um diagrama ou uma\n  sequência de caracteres presente no original. A omissão de qualquer bloco é\n  erro grave de fidelidade.\n- Quando o bloco representar SOM ou FONÉTICA (sílabas, leituras, pronúncia,\n  decomposição sonora), use a REPRESENTAÇÃO FONÉTICA (romanização) como forma\n  principal, alinhada ao original se houver estrutura de colunas. O caractere\n  gráfico (kanji/kana) só precisa ser mantido se o texto estiver analisando a\n  FORMA ESCRITA como tema — não quando analisa o som.\n- NUNCA deixe um bloco do original sem correspondência no português.\n- NUNCA acrescente tabela, coluna, linha ou caractere que não exista no original.\n"""

    reforco = (
        "\n\nAUDITORIA APONTOU UM ERRO NESTA TRADUÇÃO. Corrija o problema "
        "semanticamente (JP/PT lado a lado), mantendo TODO o sentido do JP.\n"
        f"ERRO apontado: {erro.get('erro', '')}\n"
    )
    if erro.get("correcao"):
        reforco += f"CORREÇÃO SUGERIDA pela auditoria (avalie e aplique se correta): {erro['correcao']}\n"
    reforco += (
        "\nTEXTO ATUAL (para você corrigir):\n"
        f"{pt_atual}\n\n"
        "Responda apenas com a tradução corrigida, sem comentários."
    )

    reforcos = [
        "",
        "\n\nResponda APENAS com a tradução corrigida, sem comentários.",
        "\n\nSaída: só o texto traduzido corrigido.",
        "\n\nNão deixe em branco. Corrija e responda a tradução.",
        "\n\nIMPORTANTE: sua resposta anterior veio vazia. Escreva a tradução corrigida agora.",
    ]
    ultimo_erro = None
    for tentativa in range(8):
        r = reforcos[tentativa] if tentativa < len(reforcos) else "\n\nCorrija agora."
        try:
            resp = _client().chat.completions.create(
                model=MODELO,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt_base + reforco + r}],
                temperature=0.2,
            )
            raw = (resp.choices[0].message.content or "").strip().strip('"').strip()
            if raw and len(re.sub(r"\s", "", raw)) >= 10:
                return raw
            raise ValueError("resposta vazia")
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            time.sleep(3 * (tentativa + 1))
    return ""


def main() -> int:
    client = _client()
    print("=== Pipeline completo (retradução→auditoria→ajuste) — Curso Kannon ===")

    for idx in [1, 2, 3]:
        jp = (PASTA / f"trecho_{idx}_jp.txt").read_text(encoding="utf-8")
        pt_atual = (PASTA / f"trecho_{idx}_novo.txt").read_text(encoding="utf-8")
        print(f"\n--- Trecho {idx} (JP {len(jp)}c | PT {len(pt_atual)}c) ---")

        historico = []
        aprovado = False
        for tentativa in range(1, MAX_TENTATIVAS + 1):
            # AUDITORIA
            print(f"  [auditoria #{tentativa}]...", flush=True)
            veredito = auditar_trecho(client, idx, jp, pt_atual)
            v = veredito.get("veredito")
            print(f"    -> {v}" + (f": {veredito.get('erro','')[:120]}" if v == "ERRO_TRADUCAO" else ""), flush=True)
            historico.append({"tentativa": tentativa, "veredito": v, "erro": veredito.get("erro")})

            if v == "OK":
                aprovado = True
                break

            if v == "ERRO_TRADUCAO":
                # AJUSTE: executor corrige
                print(f"  [ajuste #{tentativa}]...", flush=True)
                corrigido = executor_corrigir(idx, jp, pt_atual, veredito)
                if not corrigido:
                    print(f"    ERRO: correção falhou", flush=True)
                    break
                pt_atual = corrigido
                (PASTA / f"trecho_{idx}_novo.txt").write_text(corrigido, encoding="utf-8")
                print(f"    -> corrigido ({len(corrigido)}c)", flush=True)
            else:  # FALHA_API
                print(f"    FALHA_API — tentando de novo", flush=True)
                continue

        # Salvar versão final
        (PASTA / f"trecho_{idx}_final.txt").write_text(pt_atual, encoding="utf-8")
        status = "APROVADO" if aprovado else "NAO_APROVADO"
        print(f"  -> FINAL: {status} | {len(pt_atual)}c")
        (PASTA / f"trecho_{idx}_historico.json").write_text(
            json.dumps(historico, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    print("\nPipeline concluído. Versões finais em trecho_*_final.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
