#!/usr/bin/env python3
"""Apoio mecânico do ajuste manual do LOTE2 (a DECISÃO é feita caso a caso,
lendo JP+PT; este módulo só localiza, valida âncora e grava fonte+staging)."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path("/var/www/goshinsho")
FONTE = ROOT / "livros_publicacao_pt_revisado"
STAGING = ROOT / "reports/livros_trabalho/pt"
JP = ROOT / "reports/livros_trabalho/jp"

sys.path.insert(0, str(ROOT / "scripts"))
from mescla_e_aplica import valida_ancoras  # noqa: E402

TS = "20260813T_lote2"


def _read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def loc(obra: str, needle: str, ctx: int = 260, arq: str = "pt") -> None:
    """Mostra todas as ocorrências de `needle` com contexto."""
    base = {"pt": FONTE, "jp": JP, "stg": STAGING}[arq]
    t = _read(base / obra)
    n = t.count(needle)
    print(f"### {arq} ocorrencias={n}")
    i = t.find(needle)
    while i != -1:
        print(f"--- @{i}")
        print(t[max(0, i - ctx): i + len(needle) + ctx])
        i = t.find(needle, i + 1)


def jpwin(obra: str, a: int, b: int) -> None:
    print(_read(JP / obra)[a:b])


def jpfind(obra: str, needle: str, ctx: int = 300) -> None:
    loc(obra, needle, ctx, arq="jp")


def jpprox(obra: str, needle: str, win: int = 1600) -> None:
    """Estima a posição JP proporcional à posição do trecho PT e imprime a
    janela — atalho de localização; a leitura/decisão continua manual."""
    pt = _read(FONTE / obra)
    jp = _read(JP / obra)
    i = pt.find(needle)
    if i == -1:
        print("PT: trecho não encontrado")
        return
    j = int(i / len(pt) * len(jp))
    print(f"### PT@{i}/{len(pt)} -> JP~{j}/{len(jp)}")
    print(jp[max(0, j - win): j + win])


def apply(obra: str, old: str, new: str, expect: int = 1) -> str:
    """Substitui `old` por `new` na FONTE, valida âncoras e grava fonte+staging.
    Retorna 'OK' ou mensagem de erro (nada é gravado em caso de erro)."""
    fp = FONTE / obra
    sp = STAGING / obra
    t = _read(fp)
    n = t.count(old)
    if n != expect:
        return f"ERRO: '{old[:40]}...' aparece {n}x (esperado {expect})"
    novo = t.replace(old, new)
    if novo == t:
        return "ERRO: texto inalterado"
    ok, motivo = valida_ancoras(obra, novo)
    if not ok:
        return f"ANCORA: {motivo}"
    bak = fp.with_name(fp.name + f".bak_ajuste_{TS}")
    if not bak.exists():
        shutil.copy2(fp, bak)
    fp.write_text(novo, encoding="utf-8")
    if sp.exists():
        st = _read(sp)
        if st.count(old) == n:
            sp.write_text(st.replace(old, new), encoding="utf-8")
        elif st == t:
            sp.write_text(novo, encoding="utf-8")
        else:
            return f"OK-FONTE (staging divergente: {st.count(old)}x) [{motivo}]"
    else:
        sp.write_text(novo, encoding="utf-8")
    return f"OK [{motivo}]"
