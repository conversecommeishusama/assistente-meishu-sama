#!/usr/bin/env python3
"""Repete o teste "5 perguntas x 3 sistemas" (jp_direct / pt_first / pt_direct)
chamando goshinsho.pipeline.answer.answer() diretamente, mesma metodologia do
teste pre-rebuild (17/07). Uso: python3 scripts/benchmark_5perguntas.py <saida.json>
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
from goshinsho.services.jp_retrieval import jp_only_pool  # noqa: E402
from goshinsho.services.pt_retrieval import pt_only_pool  # noqa: E402

QUESTIONS = [
    "o que Meishu-Sama fala sobre o irmão de noé?",
    "O que Meishu-Sama pensaria sobre a pademia de covid-19?",
    "O que Meishu-Sama fala sobre homosexualidade.",
    "O que Meishu-Sama fala sbre a sua sucessão?",
    "Me forneça o ensinamento os japoneses e as doenças mentais?",
    "Me forneça o ensinamento os japoneses e as doenças mentais na íntegra",
]

MODES = [
    ("jp_direct", jp_only_pool),
    ("pt_first", None),
    ("pt_direct", pt_only_pool),
]


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "reports" / "resultado_5perguntas_pos_rebuild.json"
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
