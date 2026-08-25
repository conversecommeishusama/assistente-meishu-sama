#!/usr/bin/env python3
"""Monta material lado a lado MIOSHIE 1-8 a partir do TEXTO CANÔNICO ATUAL.

Fonte de verdade (regra do usuário): O PRÓPRIO TEXTO.
  - PT = staging canônico ATUAL (reports/livros_trabalho/pt/)
  - JP = textos_japones/
  - NÃO usa checkpoint (não é referência).

Diálogos 1-8: alinha por rótulos Interlocutor:/Meishu-Sama: (pareamento já
confirmado 1:1 em 24/08, contagens idênticas). Servir de material de leitura
para a revisão semântica manual. NÃO edita nada.

Uso:
  python scripts/_montar_material_mioshie.py <n>
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
JP_DIR = RAIZ / "textos_japones"
STAGING_DIR = RAIZ / "reports" / "livros_trabalho" / "pt"
OUT_DIR = RAIZ / "reports" / "material_revsem_mioshie"


def limpar_cabecalho_jp(texto: str) -> str:
    idx = texto.find("---")
    return texto[idx + 3:] if idx != -1 else texto


def dividir_falas(texto: str) -> list[tuple[str, str]]:
    padrao = re.compile(r"(?m)^\s*(Interlocutor:|Meishu-Sama:|Ensinamento:)")
    matches = list(padrao.finditer(texto))
    partes = []
    for i, m in enumerate(matches):
        inicio = m.start()
        fim = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
        quem = m.group(1).replace(":", "")
        partes.append((quem, texto[inicio:fim].strip()))
    return partes


def montar(n: int) -> str:
    jp_path = next((p for p in sorted(JP_DIR.glob(f"*御教え集{n}号.txt"))), None)
    st_path = next((p for p in sorted(STAGING_DIR.glob("*.txt"))
                    if re.search(rf"Mioshie-shū nº {n}", p.stem)), None)
    if not jp_path or not st_path:
        return f"ERRO: JP={jp_path} ST={st_path}"

    jp = limpar_cabecalho_jp(jp_path.read_text(encoding="utf-8"))
    st = st_path.read_text(encoding="utf-8")

    jp_falas = dividir_falas(jp)
    st_falas = dividir_falas(st)

    if len(jp_falas) != len(st_falas):
        return (f"ERRO: contagem difere — JP={len(jp_falas)} ST={len(st_falas)} "
                f"({st_path.name}). Revisar manualmente antes.")

    blocos = []
    for i, (jp_f, st_f) in enumerate(zip(jp_falas, st_falas)):
        quem_jp, txt_jp = jp_f
        quem_st, txt_st = st_f
        txt_jp_clean = re.sub(r"^(Interlocutor:|Meishu-Sama:|Ensinamento:)\s*", "", txt_jp).strip()
        txt_st_clean = re.sub(r"^(Interlocutor:|Meishu-Sama:|Ensinamento:)\s*", "", txt_st).strip()
        blocos.append(f"=== FALA {i} ({quem_st}) ===")
        blocos.append(f"JP: {txt_jp_clean}")
        blocos.append(f"PT: {txt_st_clean}")
        blocos.append("")
    return "\n".join(blocos)


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    n = int(sys.argv[1])
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    material = montar(n)
    if material.startswith("ERRO"):
        print(material)
        return 1
    out = OUT_DIR / f"material_revsem_mioshie_{n}.txt"
    out.write_text(material, encoding="utf-8")
    print(f"Mioshie {n}: {material.count('=== FALA')} falas -> {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
