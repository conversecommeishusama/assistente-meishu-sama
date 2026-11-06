#!/usr/bin/env python3
"""Gera o material de leitura semântica (pares JP↔PT) para coleções orais.

Reutiliza o formato do `verificar_integridade_completa.py` (=== FALA N (quem) ===
/ JP: / PT:) mas de forma GENÉRICA: aceita Gokōwa-roku (diálogo, chaves
numéricas), Gosuiji-roku (diálogo, chaves numéricas) e Mioshie-shū 9-33
(prosa contínua, chaves t{n}).

Uso:
  .venv/bin/python scripts/gerar_material_semantico_orais.py [--colecao gokowa|gosuiji|mioshie_prosa|todas]
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CKPT_DIR = RAIZ / "reports" / "retraducao_colecoes"
OUT_DIR = RAIZ / "reports"


def _chave_ord(chave) -> int:
    """Ordena chaves de fala: numéricas (diálogo) OU t{n} (prosa contínua)."""
    if isinstance(chave, str) and chave.startswith("t") and chave[1:].isdigit():
        return int(chave[1:])
    try:
        return int(chave)
    except (TypeError, ValueError):
        return 0


def coletar_arquivos(colecao: str) -> list[str]:
    """Retorna os stems dos checkpoints da coleção, em ordem."""
    prefixos = {
        "gokowa": "御光話録",
        "gosuiji": "御垂示録",
        "mioshie_prosa": "御教え集",
    }
    pref = prefixos.get(colecao)
    if not pref:
        return []
    arquivos = sorted(
        p.stem for p in CKPT_DIR.glob(f"*{pref}*.json")
        if not p.name.startswith("backup") and "bak" not in p.name
    )
    if colecao == "mioshie_prosa":
        # só os 9-33 (prosa contínua) — exclui 1-8 (diálogo, já revisados)
        arquivos = [a for a in arquivos if _num_edicao(a) >= 9]
    return arquivos


def _num_edicao(stem: str) -> int:
    m = re.search(r'御教え集(\d+)号', stem)
    if m:
        return int(m.group(1))
    m = re.search(r'御光話録(\d+)号', stem)
    if m:
        return int(m.group(1))
    m = re.search(r'御垂示録(\d+)号', stem)
    if m:
        return int(m.group(1))
    return 0


def gerar_material(stem: str) -> str | None:
    """Gera o material de leitura de um checkpoint. Retorna o texto ou None."""
    ckpt_path = CKPT_DIR / f"{stem}.json"
    if not ckpt_path.exists():
        return None
    ckpt = json.loads(ckpt_path.read_text(encoding="utf-8"))
    falas = ckpt.get("falas", {})
    if not falas:
        return None

    chaves_ord = sorted(falas.keys(), key=_chave_ord)
    blocos = []
    for k in chaves_ord:
        f = falas[k]
        if not isinstance(f, dict):
            continue
        jp = (f.get("jp") or "").strip()
        pt = (f.get("pt_contextual") or "").strip()
        # remove rótulo duplicado se presente
        pt_clean = re.sub(r"^(Interlocutor|Meishu-Sama)[:：]\s*", "", pt)
        quem = f.get("quem", "")
        blocos.append(f"=== FALA {k} ({quem}) ===")
        blocos.append(f"JP: {jp}")
        blocos.append(f"PT: {pt_clean}")
        blocos.append("")
    return "\n".join(blocos)


def main() -> int:
    colecao = "todas"
    if "--colecao" in sys.argv:
        colecao = sys.argv[sys.argv.index("--colecao") + 1]

    nomes = {
        "gokowa": ("Gokōwa-roku", "御光話録"),
        "gosuiji": ("Gosuiji-roku", "御垂示録"),
        "mioshie_prosa": ("Mioshie-shū 9-33", "御教え集"),
    }

    if colecao == "todas":
        colecoes = list(nomes.keys())
    else:
        colecoes = [colecao]

    for col in colecoes:
        arquivos = coletar_arquivos(col)
        print(f"\n=== {nomes[col][0]}: {len(arquivos)} arquivos ===")
        for stem in arquivos:
            material = gerar_material(stem)
            if material is None:
                print(f"  [sem checkpoint] {stem}")
                continue
            n_ed = _num_edicao(stem)
            if col == "mioshie_prosa":
                out_name = f"material_leitura_semantica_mioshie_{n_ed}.txt"
            elif col == "gokowa":
                out_name = f"material_leitura_semantica_gokowa_{n_ed}.txt"
            else:
                out_name = f"material_leitura_semantica_gosuiji_{n_ed}.txt"
            out = OUT_DIR / out_name
            out.write_text(material, encoding="utf-8")
            n_falas = material.count("=== FALA")
            print(f"  {stem}: {n_falas} falas -> {out.name}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
