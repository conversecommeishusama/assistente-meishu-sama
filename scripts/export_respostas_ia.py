#!/usr/bin/env python3
"""Respostas finais da IA (como o usuário vê) — sem exportar trechos."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

from benchmark_v2_vs_legacy import CASES  # noqa: E402
from goshinsho.pipeline.answer import answer as answer_v2  # noqa: E402
from goshinsho.services.ai_service import answer_question as answer_legacy  # noqa: E402
from goshinsho.services.search_service import buscar_trechos, buscar_trechos_sem_tutelas  # noqa: E402

OUT_JSON = PROJECT_ROOT / "reports" / "benchmark_respostas_ia.json"
OUT_MD = PROJECT_ROOT / "reports" / "benchmark_respostas_ia.md"

MODES = [
    (
        "v2_melhorado",
        lambda q: answer_v2(q, [], language="Português"),
    ),
    (
        "legacy_completo",
        lambda q: answer_legacy(q, [], language="Português", search_func=buscar_trechos),
    ),
    (
        "legacy_motor_sem_tutelas",
        lambda q: answer_legacy(
            q, [], language="Português", search_func=buscar_trechos_sem_tutelas
        ),
    ),
]


def _save(report: list[dict]) -> None:
    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Respostas da IA — análise subjetiva (visão do usuário final)",
        "",
        f"{len(CASES)} perguntas × {len(MODES)} sistemas.",
        "",
        "Modos:",
        "- **v2_melhorado** — chat v2 (pipeline actual)",
        "- **legacy_completo** — ai_service + buscar_trechos (tutelas incluídas)",
        "- **legacy_motor_sem_tutelas** — ai_service + motor legacy sem tutelas",
        "",
        "---",
        "",
    ]
    for entry in report:
        lines += [f"## {entry['id']}", "", f"**Pergunta:** {entry['pergunta']}", ""]
        for mode, data in entry.get("modos", {}).items():
            lines += [f"### {mode}", ""]
            if "erro" in data:
                lines += [f"*Erro ({data.get('elapsed_s', '?')}s):* {data['erro']}", ""]
            else:
                lines += [
                    f"*Tempo: {data['elapsed_s']}s*",
                    "",
                    data["resposta"],
                    "",
                ]
        lines += ["---", ""]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    report: list[dict] = []
    total = len(CASES) * len(MODES)
    n = 0

    print(f"Gerando {total} respostas (só LLM + pesquisa interna)…\n", flush=True)

    for case in CASES:
        entry: dict = {"id": case["id"], "pergunta": case["query"], "modos": {}}
        print(f"=== {case['id']}", flush=True)

        for mode_name, answer_fn in MODES:
            n += 1
            print(f"  [{n}/{total}] {mode_name}…", flush=True)
            t0 = time.perf_counter()
            try:
                resposta = answer_fn(case["query"])
                entry["modos"][mode_name] = {
                    "resposta": resposta,
                    "elapsed_s": round(time.perf_counter() - t0, 1),
                }
            except Exception as exc:
                entry["modos"][mode_name] = {
                    "erro": str(exc),
                    "elapsed_s": round(time.perf_counter() - t0, 1),
                }
                print(f"    ERRO: {exc}", flush=True)

        report.append(entry)
        _save(report)
        print(f"  → guardado ({n}/{total})\n", flush=True)

    print(f"Concluído.\nJSON: {OUT_JSON}\nMarkdown: {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
