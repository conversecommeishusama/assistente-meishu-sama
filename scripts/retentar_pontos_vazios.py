#!/usr/bin/env python3
"""Re-tenta os pontos problema que ficaram vazios (com o bug da trava corrigido)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from retraducao_completa_gokowa import retraduzir, extrair_falas, JP  # noqa: E402

OUT = RAIZ / "reports" / "amostragem_semantica_gokowa" / "pontos_problema" / "retraducao_pontos_problema.json"


def main() -> None:
    if not OUT.exists():
        print("sem arquivo")
        return
    d = json.loads(OUT.read_text(encoding="utf-8"))
    falas_jp = extrair_falas(JP.read_text(encoding="utf-8"))

    retentados = 0
    for r in d:
        nome = r.get("nome", "?")
        pt = r.get("pt_novo", "")
        if pt and pt != "...":
            continue  # já ok

        idx = r.get("indice_jp", 0)
        jp = r.get("jp", "")
        quem = r.get("quem", "Meishu-Sama")
        ctx = ""
        if idx > 0 and idx < len(falas_jp):
            ctx = f"[{falas_jp[idx-1][0]}] {falas_jp[idx-1][1]}"

        print(f"=== Re-tentando {nome} (idx {idx}) ===", flush=True)
        novo = retraduzir(jp, quem, max_retries=12, contexto_anterior=ctx)
        r["pt_novo"] = novo
        print(f"PT NOVO: {novo[:150]}", flush=True)
        OUT.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        retentados += 1

    print(f"\nFIM — {retentados} pontos re-tentados")


if __name__ == "__main__":
    main()
