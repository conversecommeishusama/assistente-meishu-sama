"""Terceiro passe para os 221 casos "reformar" -- mesmo desenho de
compara_resolucoes_c.py, só apontado pros arquivos RESOLVE_REFORMAR_*.

    python3 scripts/compara_reformar.py
    python3 scripts/compara_reformar.py --relatorio
"""
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import compara_resolucoes_c as C  # noqa: E402

R = RAIZ / "reports/varredura_padronizacao"
C.D1 = R / "RESOLVE_REFORMAR_1.json"
C.D2 = R / "RESOLVE_REFORMAR_2.json"
C.DEST = R / "COMPARA_REFORMAR.json"

if __name__ == "__main__":
    C.main()
