#!/usr/bin/env python3
"""Reroda só pt_direct nas perguntas 11-20 (as que ficaram mais rasas que
pt_first no benchmark anterior), depois do ajuste max_por_fonte 2->5, para
comparar diretamente contra o resultado antigo salvo em
reports/resultado_pt_direct_vs_pt_first.json."""
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

OLD = json.loads((PROJECT_ROOT / "reports" / "resultado_pt_direct_vs_pt_first.json").read_text(encoding="utf-8"))
ALVOS = [e for e in OLD if e["id"] >= 11]


def main():
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else PROJECT_ROOT / "reports" / "resultado_pt_direct_maxfonte5.json"
    data = []
    for entry in ALVOS:
        pergunta = entry["pergunta"]
        t0 = time.perf_counter()
        try:
            resposta = answer_v2(pergunta, [], language="Português", base_pool_fn=pt_only_pool)
            elapsed = round(time.perf_counter() - t0, 1)
            item = {"resposta": resposta, "elapsed_s": elapsed}
        except Exception as exc:  # noqa: BLE001
            elapsed = round(time.perf_counter() - t0, 1)
            item = {"erro": str(exc), "elapsed_s": elapsed}
        antes = entry["modos"]["pt_direct"]
        antes_len = len(antes.get("resposta") or "")
        depois_len = len(item.get("resposta") or "")
        print(
            f"[{entry['id']}/20] pt_direct: {item.get('elapsed_s')}s "
            f"(antes {antes_len} chars -> depois {depois_len} chars, pt_first era {len(entry['modos']['pt_first'].get('resposta') or '')} chars)",
            flush=True,
        )
        data.append({"id": entry["id"], "pergunta": pergunta, "pt_direct_antes": antes, "pt_direct_depois": item, "pt_first": entry["modos"]["pt_first"]})
        out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"gravado em {out_path}")


if __name__ == "__main__":
    main()
