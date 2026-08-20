#!/usr/bin/env python3
"""Reconcilia as pt_anchor das specs dos Mioshie-shū (1-8) para o padrão
canônico (decisão do usuário de 2026-08-05, já aplicada no nº 7):

  pt_anchor = marcador de data real no texto consolidado (ex: "6 de fevereiro")
  pt_prefix = mesmo valor (título da sessão no cabeçalho)

A jp_anchor (base JP) NÃO é alterada.

Para cada sessão da spec:
  1. Localiza o marcador [data] correspondente no consolidado (revisao_literaria/orais)
     usando o title_pt da sessão (normalizado).
  2. Define pt_anchor = marcador (sem colchetes) e pt_prefix = marcador.
  3. Se o title_pt tiver sufixo especial (ex: "5 de agosto" vs marcador "5 de
     agosto"), mantém o title_pt mas usa o marcador como âncora.
  4. Valida que o marcador existe no consolidado (senão, NÃO altera e avisa).

Uso:
  .venv/bin/python scripts/reconciliar_ancoras_mioshie.py [--dry-run] [--arquivo N]
"""
import json
import re
import sys
from pathlib import Path

SPEC_DIR = Path("reports/livros_trabalho/segmentacao_manual")
ORAL_DIR = Path("revisao_literaria/orais")

MAP = {1: "19510920", 2: "19511025", 3: "19511125", 4: "19511215",
       5: "19520115", 6: "19510225", 7: "19520320", 8: "19520420"}


def norm(s: str) -> str:
    s = s.replace("º", "").replace("°", "").strip().lower()
    return re.sub(r"\s+", " ", s)


def main() -> int:
    dry = "--dry-run" in sys.argv
    apenas = None
    for a in sys.argv:
        if a.startswith("--arquivo"):
            apenas = int(a.split("=")[1])

    for n in range(1, 9):
        if apenas and n != apenas:
            continue
        stem = MAP[n]
        spec_files = list(SPEC_DIR.glob(f"{stem} - Mioshie-shū nº {n}.txt.json"))
        oral_files = list(ORAL_DIR.glob(f"{stem} - Mioshie-shū nº {n}.txt"))
        if not spec_files or not oral_files:
            print(f"[nº {n}] spec ou consolidado ausente")
            continue
        spec_path = spec_files[0]
        oral_path = oral_files[0]
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        oral = oral_path.read_text(encoding="utf-8")
        marcadores = re.findall(r"^\[([^\]]+)\]\s*$", oral, flags=re.M)
        marc_norm = {norm(m): m for m in marcadores}

        alterados = 0
        avisos = []
        for art in spec.get("articles", []):
            if art.get("kind") != "session":
                continue
            tpt = art.get("title_pt", "")
            tn = norm(tpt)
            if tn not in marc_norm:
                avisos.append(f"sessão [{tpt}]: sem marcador correspondente")
                continue
            marcador = marc_norm[tn]
            # o marcador SEM colchetes é a âncora
            ancora = marcador
            if art.get("pt_anchor") != ancora:
                art["pt_anchor"] = ancora
                art["pt_prefix"] = ancora
                # preserva notas existentes e acrescenta histórico
                notas = art.get("notes", "") or ""
                if "reconciliacao" not in notas:
                    nova_nota = f"2026-08-20 adequacao estrutural: pt_anchor repontada para o cabecalho de data '[{marcador}]' (retraducao nova reescreveu o corpo)."
                    art["notes"] = (notas + "\n" if notas else "") + nova_nota
                alterados += 1

        if dry:
            status = f"[dry-run] {stem}: {alterados} âncoras reconciliadas"
        else:
            spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
            status = f"✓ {stem}: {alterados} âncoras reconciliadas"
        print(status)
        for a in avisos:
            print(f"    AVISO: {a}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
