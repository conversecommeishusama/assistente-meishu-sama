"""Terceiro passe para os 213 casos da pilha C nunca lidos -- mesmo desenho
de compara_resolucoes_c.py, só apontado pros arquivos RESOLVE_213_*.

    python3 scripts/compara_213.py
    python3 scripts/compara_213.py --relatorio
"""
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import compara_resolucoes_c as C  # noqa: E402

R = RAIZ / "reports/varredura_padronizacao"
C.D1 = R / "RESOLVE_213_1.json"
C.D2 = R / "RESOLVE_213_2.json"
C.DEST = R / "COMPARA_213.json"

if __name__ == "__main__":
    C.main()
