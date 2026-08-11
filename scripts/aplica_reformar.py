"""Aplica no corpus as resoluções convergentes dos 221 casos "reformar" --
mesma mecânica de aplica_resolucoes_c.py, só apontada pros arquivos deste
lote.

    python3 scripts/aplica_reformar.py            # ensaio
    python3 scripts/aplica_reformar.py --aplicar
"""
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import aplica_resolucoes_c as X  # noqa: E402

R = RAIZ / "reports/varredura_padronizacao"
X.COMPARA = R / "COMPARA_REFORMAR.json"
X.REGISTRO = R / "APLICADO_REFORMAR.json"

if __name__ == "__main__":
    X.main()
