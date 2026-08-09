"""Diário do meu trabalho, escrito à medida que ele acontece.

Existe porque o usuário não deve precisar me acionar para saber se estou
trabalhando, nem esperar eu terminar para saber o que estou fazendo. Cada
entrada sai com carimbo de hora, no momento da ação -- não no fim.

    tail -f reports/varredura_padronizacao/DIARIO.md
"""
import sys
from datetime import datetime
from pathlib import Path

D = Path("/var/www/goshinsho/reports/varredura_padronizacao/DIARIO.md")

def anota(texto: str) -> None:
    with D.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%H:%M:%S}  {texto}\n")

if __name__ == "__main__":
    anota(" ".join(sys.argv[1:]))
