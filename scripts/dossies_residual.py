"""Monta dossiês dos casos residuais dos lotes 213 (pilha C nunca lidos) e
221 (reformar) -- os que divergiram entre as duas leituras independentes,
ou nunca convergiram -- para leitura minha. Mesmo formato de
dossies_mesa_c.py, só juntando as duas fontes.

    python3 scripts/dossies_residual.py            # todos
    python3 scripts/dossies_residual.py 0 20        # fatia [0:20)
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import dossies_mesa_c as M  # noqa: E402

R = RAIZ / "reports/varredura_padronizacao"


def casos() -> list[dict]:
    out = []
    for d1n, d2n, cpn, tag in (
        ("RESOLVE_213_1.json", "RESOLVE_213_2.json", "COMPARA_213.json", "213"),
        ("RESOLVE_REFORMAR_1.json", "RESOLVE_REFORMAR_2.json", "COMPARA_REFORMAR.json", "REFORMAR"),
    ):
        M.R = R
        import json
        d1 = json.loads((R / d1n).read_text(encoding="utf-8"))
        d2 = json.loads((R / d2n).read_text(encoding="utf-8"))
        cp = json.loads((R / cpn).read_text(encoding="utf-8"))
        for k in sorted(d1):
            a, b = d1[k], d2.get(k)
            if not b:
                continue
            c = cp.get(k)
            if a.get("resolvido") and b.get("resolvido"):
                if not c or "erro" in c or c.get("concordam"):
                    continue
                origem, nota = "DIVERGEM", c.get("nota", "")
            elif a.get("resolvido") or b.get("resolvido"):
                origem, nota = "SO_UMA", ""
            else:
                origem, nota = "NENHUMA", ""
            out.append({**a, "t2": b.get("texto_final", ""), "r2": b.get("razao", ""),
                        "t1": a.get("texto_final", ""), "r1": a.get("razao", ""),
                        "origem": origem, "nota_cmp": nota, "lote": tag,
                        "chave": f"{tag}:{k}"})
    return out


M.casos = casos


def main() -> None:
    M.main()


if __name__ == "__main__":
    main()
