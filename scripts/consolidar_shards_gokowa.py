#!/usr/bin/env python3
"""Consolida os checkpoints dos shards no checkpoint principal do laço.

Uso:
    python3 scripts/consolidar_shards_gokowa.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
OUT = RAIZ / "reports" / "amostragem_semantica_gokowa"
PRINCIPAL = OUT / "laco_retraducao_checkpoint.json"


def main() -> None:
    principal = {}
    if PRINCIPAL.exists():
        try:
            principal = json.loads(PRINCIPAL.read_text(encoding="utf-8"))
        except Exception:
            principal = {}
    if "falas" not in principal:
        principal["falas"] = {}

    total_falas = 0
    # Inclui shards originais E intervalos extras (laco_intervalo_*.json)
    arquivos = sorted(OUT.glob("laco_shard_*.json")) + sorted(OUT.glob("laco_intervalo_*.json"))
    for shard_file in arquivos:
        try:
            shard = json.loads(shard_file.read_text(encoding="utf-8"))
        except Exception:
            print(f"⚠️  não pôde ler {shard_file.name}")
            continue
        for k, v in shard.get("falas", {}).items():
            # não sobrescrever uma falha com dado anterior incompleto
            if v.get("status") in ("aprovado", "revisar", "max_rodadas"):
                principal["falas"][k] = v
        total_falas += len(shard.get("falas", {}))
        print(f"  shard {shard_file.name}: {len(shard.get('falas', {}))} falas")

    principal["total"] = len(principal["falas"])
    PRINCIPAL.write_text(json.dumps(principal, ensure_ascii=False, indent=2), encoding="utf-8")

    from collections import Counter
    cont = Counter(v.get("status", "?") for v in principal["falas"].values())
    print(f"\nConsolidado: {len(principal['falas'])} falas | {cont}")


if __name__ == "__main__":
    main()
