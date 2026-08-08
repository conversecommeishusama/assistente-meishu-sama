#!/usr/bin/env python3
"""Verifica gates F1 e resume próximos passos F2 (sem promover nem reindexar)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from retranslate_core import list_jp_sources  # noqa: E402
from translation_mass_progress import load_progress  # noqa: E402

RUN = PROJECT_ROOT / "reports/translation_review/translation_mass/20260620T190000Z"


def main() -> int:
    done = load_progress(RUN / "progress.jsonl")
    quarantine = {f["jp_path"] for f in json.loads((RUN / "QUARENTENA.json").read_text()).get("files", [])}
    pending = [
        p
        for p in list_jp_sources()
        if str(p.relative_to(PROJECT_ROOT)) not in done
        and str(p.relative_to(PROJECT_ROOT)) not in quarantine
    ]
    plan_path = RUN / "promotion_plan.json"
    plan_count = 0
    if plan_path.exists():
        plan_count = len(json.loads(plan_path.read_text()).get("plan") or [])

    print("GATE F2 — verificação\n")
    print(f"  Concluídos ok/warn: {len(done)}")
    print(f"  Pendentes fila auto: {len(pending)}")
    print(f"  Quarentena: {len(quarantine)}")
    print(f"  Plano promoção (dry-run): {plan_count} ficheiros")
    print()
    if pending:
        print("  ⛔ F2 bloqueado — fila automática ainda não terminou:")
        for p in pending:
            print(f"     - {p.name[:70]}")
    else:
        print("  ✓ Fila automática vazia — pode autorizar promoção (se WARN/quarentena OK)")
    print()
    print("Comandos F2 (após sua autorização):")
    print("  python3 scripts/promote_translation_staging.py --apply")
    print("  .venv/bin/python scripts/build_clean_large_indexes.py --install")
    print("  sudo systemctl restart goshinsho.service")
    print("  .venv/bin/python scripts/run_acceptance_battery.py --retrieval-only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
