#!/usr/bin/env python3
"""Roda o benchmark do stack de produção apontando para um diretório de índices.

Uso:
    python scripts/run_benchmark_producao_por_diretorio.py \
        --index-dir experiments/uploaded_indexes \
        --out reports/benchmark_producao_corpus_novo.json

    python scripts/run_benchmark_producao_por_diretorio.py \
        --index-dir backups/indices_pre_promocao_20260827 \
        --out reports/benchmark_producao_corpus_antigo.json

Monkeypatcha UPLOADED_INDEX_DIR ANTES de importar as funções que leem o
diretório (search_service._index_file resolve contra essa variável), e roda
exatamente o mesmo teste de scripts/benchmark_producao_stack.py.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index-dir", required=True, help="Diretório com chunks/metadados/faiss")
    parser.add_argument("--out", required=True, help="Arquivo JSON de saída")
    parser.add_argument("--japanese", action="store_true", help="Avaliar também hits em kanji (jp)")
    args = parser.parse_args()

    index_dir = (PROJECT_ROOT / args.index_dir).resolve()
    if not index_dir.is_dir():
        print(f"ERRO: diretório não existe: {index_dir}", file=sys.stderr)
        return 2

    # Monkeypatch do diretório de índices ANTES de qualquer carregamento.
    import goshinsho.services.search_service as ss

    ss.UPLOADED_INDEX_DIR = index_dir
    print(f"[{Path(args.index_dir).name}] UPLOADED_INDEX_DIR -> {index_dir}", flush=True)

    from benchmark_v2_vs_legacy import CASES, score_case  # noqa: E402
    from goshinsho.config import Config  # noqa: E402
    from goshinsho.pipeline.retrieve import retrieve  # noqa: E402
    from goshinsho.pipeline.state import build_state  # noqa: E402
    from goshinsho.services.retrieval_fallback import augment_with_legacy_fallback  # noqa: E402

    EXTRA = [
        {"id": "johrei_solo", "query": "johrei", "want": ("johrei", "jorei", "浄霊")},
        {"id": "ohikari_solo", "query": "ohikari", "want": ("ohikari", "omamori", "御守")},
    ]

    def retrieve_producao(query: str, *, max_output: int = 16):
        Config.DEFINITIONAL_GLOSSARY_TERM = True
        Config.SOURCE_HIERARCHY_WRITTEN_FIRST = False
        Config.LEGACY_MOTOR_FALLBACK = True
        state = build_state(query, [])
        chunks, metas = retrieve(state, max_output=max_output)
        return augment_with_legacy_fallback(state, chunks, metas, max_output=max_output)

    cases = list(CASES) + EXTRA
    rows = []
    total = 0

    print(f"\n=== Stack produção — {Path(args.index_dir).name} ({len(cases)} casos) ===\n")
    print(f"{'id':<22} {'pts':>4}  {'hit':>5} {'phr':>5} {'rank':>5}  top1")
    print("-" * 70)

    for case in cases:
        chunks, metas = retrieve_producao(case["query"])
        sc = score_case(case, chunks, metas, japanese_mode=args.japanese)
        sc["legacy_fb"] = sum(1 for m in metas if m.get("search_tier") == "legacy_fallback")
        sc["top3"] = [(m.get("fonte") or "")[:50] for m in metas[:3]]
        total += sc["points"]
        rank = sc.get("target_rank") or "—"
        print(
            f"{case['id']:<22} {sc['points']:>4}  "
            f"{str(sc['hit']):>5} {str(sc['phrase']):>5} {str(rank):>5}  "
            f"{(sc['top3'][0] if sc['top3'] else '')}"
        )
        rows.append({"case": case, "results": sc})

    payload = {
        "corpus": Path(args.index_dir).name,
        "index_dir": str(index_dir),
        "config": {
            "DEFINITIONAL_GLOSSARY_TERM": True,
            "SOURCE_HIERARCHY_WRITTEN_FIRST": False,
            "LEGACY_MOTOR_FALLBACK": True,
        },
        "total": total,
        "rows": rows,
    }
    out_path = PROJECT_ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print("-" * 70)
    print(f"Total: {total} pts  |  salvo em {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
