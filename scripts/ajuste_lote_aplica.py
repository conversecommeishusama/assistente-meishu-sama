"""Aplica UM caso do ajuste manual, com backup e validação de âncora.

Uso:
    python3 scripts/ajuste_lote_aplica.py <lote.json> <indice> <de> <para>

`de`/`para` vêm da linha de comando (e não do JSON) porque a decisão é
tomada caso a caso lendo o JP: o `para` do lote é só um guia e muitas vezes
precisa ser adaptado ao texto real.

Regras (protocolo dos 213):
- o `de` tem que ocorrer exatamente uma vez no arquivo (senão aborta);
- backup da fonte antes da primeira escrita da obra;
- só grava se `valida_ancoras` passar;
- grava FONTE e STAGING idênticos.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from mescla_e_aplica import valida_ancoras  # noqa: E402

PT_FONTE = RAIZ / "livros_publicacao_pt_revisado"
PT_STAGING = RAIZ / "reports/livros_trabalho/pt"
CARIMBO = "20260813"


def aplica(obra: str, de: str, para: str, ocorrencia: int = 0) -> str:
    alvo = PT_FONTE / obra
    texto = alvo.read_text(encoding="utf-8")
    n = texto.count(de)
    if n == 0:
        return f"ERRO: 'de' não encontrado"
    if n > 1 and ocorrencia == 0:
        return f"ERRO: 'de' ocorre {n}x (ambíguo); passe --ocorrencia N"
    if ocorrencia:
        pos, i = -1, 0
        for _ in range(ocorrencia):
            pos = texto.find(de, i)
            i = pos + 1
        novo = texto[:pos] + para + texto[pos + len(de):]
    else:
        novo = texto.replace(de, para)
    ok, motivo = valida_ancoras(obra, novo)
    if not ok:
        return f"ERRO: âncora quebrou ({motivo}) — não gravado"
    bak = alvo.with_name(alvo.name + f".bak_ajuste_{CARIMBO}")
    if not bak.exists():
        shutil.copy2(alvo, bak)
    alvo.write_text(novo, encoding="utf-8")
    (PT_STAGING / obra).write_text(novo, encoding="utf-8")
    return f"OK ({motivo})"


if __name__ == "__main__":
    import json
    lote = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    idx = int(sys.argv[2])
    de = sys.argv[3]
    para = sys.argv[4]
    occ = int(sys.argv[6]) if len(sys.argv) > 6 and sys.argv[5] == "--ocorrencia" else 0
    print(aplica(lote[idx]["obra"], de, para, occ))
