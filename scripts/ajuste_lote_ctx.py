"""Mostra o parágrafo PT do caso e a JANELA JP equivalente (por posição
relativa dentro do artigo), para a leitura JP↔PT lado a lado.

Uso:
    python3 scripts/ajuste_lote_ctx.py <lote.json> <i> [<i> ...] [--w 1600]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from ajuste_lote_helper import (  # noqa: E402
    JP_DIR, PT_FONTE, jp_janelas, ocorrencias, paragrafo_de,
)
from aplica_no_artigo import janelas  # noqa: E402


def main() -> None:
    argv = sys.argv[1:]
    w = 1600
    if "--w" in argv:
        k = argv.index("--w")
        w = int(argv[k + 1])
        argv = argv[:k] + argv[k + 2:]
    lote = json.loads(Path(argv[0]).read_text(encoding="utf-8"))
    for a in argv[1:]:
        i = int(a)
        c = lote[i]
        obra = c["obra"]
        pt = (PT_FONTE / obra).read_text(encoding="utf-8")
        jt = (JP_DIR / obra).read_text(encoding="utf-8")
        pw = janelas(obra, pt) or [(0, len(pt))]
        jw = jp_janelas(obra)
        print(f"### CASO {i} [{c['tipo']}] {c['chave']}")
        print(f"DE  : {c['de']}\nPARA: {c['para']}")
        occ = ocorrencias(pt, c["de"])
        print(f"occ={len(occ)}  occ_para={len(ocorrencias(pt, c['para']))}")
        for p in occ:
            pa, pb = paragrafo_de(pt, p)
            print(f"--- PT [{pa}:{pb}]")
            print(pt[max(pa, p - w):min(pb, p + w)])
            art = next((k for k, (x, y) in enumerate(pw) if x <= p < y), None)
            if art is not None and art < len(jw):
                js, je, _ = jw[art]
                ax, ay = pw[art]
                rel = (p - ax) / max(1, ay - ax)
                q = js + int(rel * (je - js))
                print(f"--- JP art{art} janela rel [{q}] de [{js}:{je}]")
                print(jt[max(js, q - w):min(je, q + w)])
        print("=" * 60)


if __name__ == "__main__":
    main()
