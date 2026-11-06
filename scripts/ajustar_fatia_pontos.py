#!/usr/bin/env python3
"""Ajusta uma FATIA (subconjunto) dos checkpoints pendentes — p/ paralelizar.

Cada instância processa apenas os arquivos da sua fatia (disjunta), evitando
conflito entre instâncias paralelas. Filtra arquivos com auditoria e sem ajuste.

Uso:
  .venv/bin/python scripts/ajustar_fatia_pontos.py <inicio> <fim>
  # ajusta os arquivos nas posições [inicio:fim] da lista de pendentes (ordenada)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
RETR = RAIZ / "reports" / "retraducao_colecoes"
AUD = RAIZ / "reports" / "auditoria_colecoes"


def no_escopo(nome: str) -> bool:
    if "御光話録" in nome or "御垂示録" in nome:
        # exclui Suplemento (processado à parte)
        if "（補）" in nome or "(補)" in nome:
            return False
        return True
    if "御教え集" in nome:
        m = re.search(r"御教え集(\d+)号", nome)
        return bool(m) and int(m.group(1)) <= 8
    return False


def ja_ajustado(ckpt_path: Path) -> bool:
    try:
        d = json.loads(ckpt_path.read_text(encoding="utf-8"))
        return bool(d.get("ajustes_aplicados"))
    except Exception:
        return False


def main() -> None:
    if len(sys.argv) < 3:
        print("uso: .venv/bin/python scripts/ajustar_fatia_pontos.py <inicio> <fim>")
        sys.exit(1)
    inicio, fim = int(sys.argv[1]), int(sys.argv[2])

    # checkpoints do escopo, ordenados, COM auditoria e SEM ajuste
    auditados = {p.stem for p in AUD.glob("*.json") if "backup" not in p.name}
    pendentes = []
    for ckpt in sorted(RETR.glob("*.json")):
        if ".bak" in ckpt.name or "lock" in ckpt.name:
            continue
        if not no_escopo(ckpt.stem):
            continue
        if ckpt.stem not in auditados:
            continue  # sem auditoria
        if ja_ajustado(ckpt):
            continue  # já ajustado
        pendentes.append(ckpt)

    fatia = pendentes[inicio:fim]
    print(f"Fatia [{inicio}:{fim}]: {len(fatia)} arquivos para ajustar (de {len(pendentes)} pendentes)")
    for ckpt in fatia:
        print(f"  → ajustando {ckpt.stem}", flush=True)
        r = subprocess.run(
            [sys.executable, "scripts/ajustar_pontos_auditoria.py", str(ckpt)],
            cwd=str(RAIZ),
        )
        # marca como ajustado (mesmo se houver não-resolvidos — vão p/ relatório)
        try:
            d = json.loads(ckpt.read_text(encoding="utf-8"))
            d["ajustes_aplicados"] = True
            d["ajustes_aplicados_em"] = __import__("time").strftime("%Y-%m-%d %H:%M:%S")
            ckpt.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"    ERRO ao marcar: {e}", flush=True)
        print(f"    ✅ {ckpt.stem} concluído", flush=True)
    print("Fatia concluída")


if __name__ == "__main__":
    main()
