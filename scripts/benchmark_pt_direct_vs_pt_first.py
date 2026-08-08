#!/usr/bin/env python3
"""Benchmark maior de QUALIDADE (não só tempo): pt_direct vs pt_first,
20 perguntas cobrindo os cenários que motivaram a complexidade do pt_first
(tutela/doença, seguimento de conversa em espírito, tema raro/fallback
legacy, hierarquia de fonte oral x escrita, modo pastoral, pergunta vaga,
multi-tema, pedido "na íntegra"), mais as 6 perguntas do teste anterior
para continuidade. Uso: python3 scripts/benchmark_pt_direct_vs_pt_first.py <saida.json>
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from goshinsho.pipeline.answer import answer as answer_v2  # noqa: E402
from goshinsho.services.pt_retrieval import pt_only_pool  # noqa: E402

QUESTIONS = [
    # --- continuidade com o teste de 6 perguntas ---
    "o que Meishu-Sama fala sobre o irmão de noé?",
    "O que Meishu-Sama pensaria sobre a pademia de covid-19?",
    "O que Meishu-Sama fala sobre homosexualidade.",
    "O que Meishu-Sama fala sbre a sua sucessão?",
    "Me forneça o ensinamento os japoneses e as doenças mentais?",
    "Me forneça o ensinamento os japoneses e as doenças mentais na íntegra",
    # --- básico/definicional ---
    "O que é Johrei?",
    "O que é o Ohikari?",
    "Como se realiza o Johrei?",
    # --- tutela/doença (risco de roteamento por tema) ---
    "Meishu-Sama fala sobre câncer?",
    "O que Meishu-Sama ensina sobre tuberculose?",
    "O que Meishu-Sama ensina sobre depressão?",
    # --- pessoas/história ---
    "Quem foi Kotama Okada?",
    "O que aconteceu em 1935 na vida de Meishu-Sama?",
    # --- temas amplos/filosóficos ---
    "O que é o Reino do Paraíso na Terra?",
    "O que é a agricultura natural segundo Meishu-Sama?",
    "Qual a importância da arte para Meishu-Sama?",
    # --- pastoral / crise pessoal ---
    "Estou doente e não sei o que fazer, o que Meishu-Sama ensina sobre isso?",
    # --- vaga / multi-tema / rara ---
    "Fale sobre espíritos.",
    "O que é o Kannon Sama?",
]

MODES = [
    ("pt_first", None),
    ("pt_direct", pt_only_pool),
]


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "reports" / "resultado_pt_direct_vs_pt_first.json"
    data = []
    for idx, pergunta in enumerate(QUESTIONS, start=1):
        entry = {"id": idx, "pergunta": pergunta, "modos": {}}
        for nome, pool_fn in MODES:
            t0 = time.perf_counter()
            try:
                resposta = answer_v2(pergunta, [], language="Português", base_pool_fn=pool_fn)
                elapsed = round(time.perf_counter() - t0, 1)
                entry["modos"][nome] = {"resposta": resposta, "elapsed_s": elapsed}
            except Exception as exc:  # noqa: BLE001
                elapsed = round(time.perf_counter() - t0, 1)
                entry["modos"][nome] = {"erro": str(exc), "elapsed_s": elapsed}
            print(f"[{idx}/{len(QUESTIONS)}] {nome}: {entry['modos'][nome].get('elapsed_s')}s", flush=True)
        data.append(entry)
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"gravado em {out_path}")


if __name__ == "__main__":
    main()
