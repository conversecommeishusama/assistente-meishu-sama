"""Aplica no corpus as resoluções convergentes dos 213 casos da pilha C que
nunca tinham sido lidos -- mesma mecânica de aplica_resolucoes_c.py, só
apontada pros arquivos deste lote.

    python3 scripts/aplica_213.py            # ensaio
    python3 scripts/aplica_213.py --aplicar
"""
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import aplica_resolucoes_c as X  # noqa: E402

R = RAIZ / "reports/varredura_padronizacao"
X.COMPARA = R / "COMPARA_213.json"
X.REGISTRO = R / "APLICADO_213.json"

if __name__ == "__main__":
    X.main()
