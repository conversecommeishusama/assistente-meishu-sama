#!/usr/bin/env python3
"""Restaura corpo PT de textos_portugues/ + A4B (convert —, depois relabel JP).

Nunca rebuild_a4b sobre A4B; rebuild só se inline — e chunks completos.

label_gokowa_a4b_from_jp.py agora recusa-se (fail-closed) a relabelar quando
a contagem de turnos JP vs PT diverge além de um limiar seguro, em vez de
assumir alinhamento posicional 1:1 desde o turno 0. Isso substitui o aviso
manual que existia aqui (ver histórico): a cadeia convert+label deixa de
poder introduzir a inversão generalizada que ocorreu no Suplemento.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

ROOT = Path(__file__).resolve().parents[1]
LIV = ROOT / "reports/livros_trabalho/pt"
PER = ROOT / "reports/periodicos_trabalho/pt"
PROD = ROOT / "textos_portugues"
GATE = SCRIPTS / "gate_gokowa_linha.py"
LABEL = SCRIPTS / "label_gokowa_a4b_from_jp.py"
CONVERT = SCRIPTS / "convert_gokowa_dialogue_a4b.py"
# livros_trabalho/pt pode conter afinações semânticas (rotulagem manual/agente)
# que não existem em textos_portugues nem são reproduzíveis por convert+label
# mecânico — descoberto depois de perder essa afinação nalguns ficheiros ao
# sobrescrever sem backup. Nunca mais sobrescrever sem guardar cópia.
LIV_BACKUP_DIR = ROOT / "reports/livros_trabalho/segmentacao_manual/pt_backup_pre_overwrite"


def restore_one(name: str, *, sync_periodicos: bool = True) -> int:
    prod_path = PROD / name
    out_path = LIV / name
    if not prod_path.is_file():
        raise SystemExit(f"sem textos_portugues: {name}")

    # Fail-closed: não destruir A4B já alinhado (convert+label perde turnos no Suplemento etc.)
    if out_path.is_file():
        pre = subprocess.run(
            [sys.executable, str(GATE), "--file", name, "--json"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        if pre.returncode == 0:
            print(f"SKIP {name}: gate já PASS; restore abortado")
            return 0
        import json

        try:
            before = json.loads(pre.stdout)[0]
        except (json.JSONDecodeError, IndexError, KeyError):
            before = {}
        if before.get("delta_i") == 0 and before.get("cjk_dialogue_lines", 99) < 40:
            print(
                f"WARN {name}: Δ=0 CJK={before.get('cjk_dialogue_lines')}; "
                "ficheiro já parece bem alinhado — restore vai sobrescrever com a produção "
                "e reconverter; confirme que é isso que quer antes de prosseguir",
                file=sys.stderr,
            )

    if out_path.is_file():
        LIV_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out_path, LIV_BACKUP_DIR / name)
    shutil.copy2(prod_path, out_path)
    for script in (CONVERT, LABEL):
        r = subprocess.run(
            [sys.executable, str(script), "--file", name]
            if script == CONVERT
            else [sys.executable, str(script), "--no-corpus", "--file", name],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        if r.returncode != 0 and script == CONVERT:
            print(r.stdout, r.stderr, file=sys.stderr)
            return 1
    if sync_periodicos:
        PER.mkdir(parents=True, exist_ok=True)
        shutil.copy2(out_path, PER / name)
    r = subprocess.run(
        [sys.executable, str(GATE), "--file", name],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr.strip(), file=sys.stderr)
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--no-sync", action="store_true")
    args = ap.parse_args()
    return restore_one(args.file, sync_periodicos=not args.no_sync)


if __name__ == "__main__":
    raise SystemExit(main())
