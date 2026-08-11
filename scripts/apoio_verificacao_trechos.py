"""Ajuda os agentes de verificação a montar o contexto JP+PT em volta de
um trecho já corrigido -- mesma técnica de jp_relevante() em
dossies_mesa_c.py, generalizada.

Uso:
    python3 scripts/apoio_verificacao_trechos.py <obra> <artigo> "<final>"
    (imprime JP relevante + PT ao redor, prontos pra ler)
"""
from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

import verifica_fidelidade as V  # noqa: E402

JANELA_JP = 500
CTX_PT = 300


def contexto(obra: str, artigo: int, final: str) -> tuple[str, str]:
    jp, pt = V.textos(obra, artigo)
    if not jp:
        return "(japonês não localizado)", pt[:2000] if pt else "(PT não localizado)"
    p = pt.find(final[:60]) if final else -1
    if p < 0 and final:
        p = pt.find(final[:20])
    viz_pt = pt[max(0, p - CTX_PT):p + len(final) + CTX_PT] if p >= 0 else pt[:2000]
    if p >= 0 and len(pt):
        alvo = int(len(jp) * (p / len(pt)))
        jp_rel = jp[max(0, alvo - JANELA_JP):alvo + JANELA_JP]
    else:
        jp_rel = jp[:JANELA_JP * 2]
    return jp_rel, viz_pt


if __name__ == "__main__":
    obra, artigo, final = sys.argv[1], int(sys.argv[2]), sys.argv[3]
    jp, pt = contexto(obra, artigo, final)
    print("=== JP relevante ===")
    print(jp)
    print("\n=== PT ao redor (já com a correção aplicada) ===")
    print(pt)
