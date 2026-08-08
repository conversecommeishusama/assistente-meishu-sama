#!/usr/bin/env python3
"""Estado das fases do plano de escala — relatório legível."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from retranslate_core import list_jp_sources  # noqa: E402
from translation_mass_progress import count_unique_done, load_progress_rows  # noqa: E402

RUN_DIR = PROJECT_ROOT / "reports" / "translation_review" / "translation_mass" / "20260620T190000Z"


def main() -> int:
    progress = RUN_DIR / "progress.jsonl"
    done = count_unique_done(path=progress) if progress.exists() else 0
    total = len(list_jp_sources())
    quarantine = 0
    qpath = RUN_DIR / "QUARENTENA.json"
    if qpath.exists():
        quarantine = len(json.loads(qpath.read_text()).get("files") or [])

    rows = load_progress_rows(progress) if progress.exists() else []
    warns = sum(1 for r in rows if r.get("status") == "warn")
    errors = sum(1 for r in rows if r.get("status") == "error")

    phases = [
        ("F1_traducao", done >= total - quarantine, f"{done}/{total} (quarentena {quarantine})"),
        ("F2_corpus_faiss", False, "aguarda promoção + reindex (autorização)"),
        ("F3_sinonimos", False, "mine_glossary_synonym_proposals.py → aprovação humana"),
        ("F4_bateria", False, "reports/acceptance/bateria_escala.json"),
        ("F5_inferencia", True, "prompts.py + inferencia-legitimada.mdc"),
        ("F6_confiabilidade", False, "auditoria pós-resposta (pendente)"),
        ("F7_escala", False, "beta fechado"),
    ]

    print("PLANO DE ESCALA — estado\n")
    for name, ok, detail in phases:
        mark = "✓" if ok else "·"
        print(f"  [{mark}] {name}: {detail}")
    print(f"\nWARN: {warns} | ERROR: {errors}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
