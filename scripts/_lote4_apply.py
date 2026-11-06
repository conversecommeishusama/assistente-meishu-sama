#!/usr/bin/env python3
"""Aplicação caso a caso do LOTE4 (uma substituição por chamada, com âncora).

Uso (via import):
    from _lote4_apply import aplica
    aplica("Eiko.txt", "texto antigo exato", "texto novo")

Faz: backup único por obra -> substitui a ÚNICA ocorrência -> valida âncoras ->
grava fonte + staging idênticos. Nunca grava se a âncora quebrar.
"""
from __future__ import annotations

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from mescla_e_aplica import valida_ancoras  # noqa: E402

PT_FONTE = RAIZ / "livros_publicacao_pt_revisado"
PT_STAGING = RAIZ / "reports/livros_trabalho/pt"

STAMP = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
_backed: set[str] = set()


def _backup(obra: str) -> None:
    if obra in _backed:
        return
    src = PT_FONTE / obra
    dst = PT_FONTE / f"{obra}.bak_ajuste_lote4_{STAMP}"
    if not dst.exists():
        shutil.copy2(src, dst)
    _backed.add(obra)


def aplica(obra: str, de: str, para: str, *, esperado: int = 1) -> str:
    f = PT_FONTE / obra
    texto = f.read_text(encoding="utf-8")
    n = texto.count(de)
    if n != esperado:
        return f"ERRO: {n} ocorrências de {de[:60]!r} (esperado {esperado})"
    novo = texto.replace(de, para)
    ok, motivo = valida_ancoras(obra, novo)
    if not ok:
        return f"ANCORA_QUEBROU: {motivo}"
    _backup(obra)
    f.write_text(novo, encoding="utf-8")
    (PT_STAGING / obra).write_text(novo, encoding="utf-8")
    return f"OK ({motivo})"
