#!/usr/bin/env python3
"""Exporte rápido: trechos recuperados (sem LLM) para análise subjetiva."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from benchmark_v2_vs_legacy import CASES  # noqa: E402
from goshinsho.pipeline.retrieve import retrieve  # noqa: E402
from goshinsho.pipeline.state import build_state  # noqa: E402
from goshinsho.services.search_service import buscar_trechos, buscar_trechos_sem_tutelas  # noqa: E402

MAX_CHUNKS = 8
PREVIEW = 1200
OUT_JSON = PROJECT_ROOT / "reports" / "benchmark_trechos_subjetivos.json"
OUT_MD = PROJECT_ROOT / "reports" / "benchmark_trechos_subjetivos.md"

MODES = [
    ("v2_melhorado", lambda q: retrieve(build_state(q, []), max_output=16)),
    ("legacy_completo", lambda q: buscar_trechos(q)),
    ("legacy_motor_sem_tutelas", lambda q: buscar_trechos_sem_tutelas(q, max_output=16)),
]


def _fonte(meta: dict) -> str:
    return (meta.get("fonte") or meta.get("arquivo") or "?").strip()


def main() -> int:
    report = []
    print(f"Exportando {len(CASES)} perguntas × {len(MODES)} modos (só trechos, sem LLM)…\n")

    for case in CASES:
        q = case["query"]
        entry = {"id": case["id"], "pergunta": q, "modos": {}}
        print(case["id"], flush=True)
        for name, fn in MODES:
            t0 = time.perf_counter()
            chunks, metas = fn(q)
            elapsed = round(time.perf_counter() - t0, 1)
            trechos = []
            for i, (c, m) in enumerate(zip(chunks, metas)):
                if i >= MAX_CHUNKS:
                    break
                text = (c or "").strip()
                trechos.append({
                    "rank": i + 1,
                    "fonte": _fonte(m),
                    "texto": text[:PREVIEW] + ("…" if len(text) > PREVIEW else ""),
                })
            entry["modos"][name] = {
                "n_trechos": len(chunks),
                "elapsed_s": elapsed,
                "trechos": trechos,
            }
        report.append(entry)

    OUT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "# Trechos recuperados — análise subjetiva",
        "",
        "Sem resposta do LLM (só o que a pesquisa entrega ao modelo).",
        f"{len(CASES)} perguntas × {len(MODES)} modos.",
        "",
        "---",
        "",
    ]
    for entry in report:
        lines += [f"## {entry['id']}", "", f"**Pergunta:** {entry['pergunta']}", ""]
        for mode, data in entry["modos"].items():
            lines += [f"### {mode} ({data['elapsed_s']}s, {data['n_trechos']} trechos)", ""]
            for t in data["trechos"]:
                lines += [f"**{t['rank']}. {t['fonte']}**", "", t["texto"], "", "---", ""]
        lines += ["", "---", ""]

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nJSON: {OUT_JSON}")
    print(f"Markdown: {OUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
