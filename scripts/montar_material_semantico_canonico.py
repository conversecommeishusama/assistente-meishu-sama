#!/usr/bin/env python3
"""Monta o material de leitura semântica (pares JP↔PT) a partir do TEXTO CANÔNICO.

Fonte da verdade (decisão do usuário 2026-08-21):
  - PT = staging canônico (reports/livros_trabalho/pt/) — onde os ajustes manuais foram aplicados
  - JP = textos_japones/ (fonte de verdade semântica)
  - NÃO usa checkpoint (não é referência — extrator bugado + ajustes manuais posteriores)

Suporta:
  - Diálogo (Gokōwa/Gosuiji): divide por rótulos Interlocutor:/Meishu-Sama: e pareia por posição
  - Prosa (Mioshie 9-33): a definir (blocos de sessão)

Uso:
  .venv/bin/python scripts/montar_material_semantico_canonico.py <colecao> <n_edicao>
  # colecao: gokowa|gosuiji
  # ex: .venv/bin/python scripts/montar_material_semantico_canonico.py gokowa 1
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
JP_DIR = RAIZ / "textos_japones"
STAGING_DIR = RAIZ / "reports" / "livros_trabalho" / "pt"
OUT_DIR = RAIZ / "reports" / "material_leitura_semantica_canonico"

# mapeamento por coleção: prefixo JP, prefixo staging PT, nome obra
COLECOES = {
    "gokowa": {
        "jp_prefix": "御光話録",
        "st_contains": "Gokōwa-roku",
        "rotulo": "Gokōwa",
    },
    "gosuiji": {
        "jp_prefix": "御垂示録",
        "st_contains": "Gosuiji-roku",
        "rotulo": "Gosuiji",
    },
}


def achar_jp(prefixo: str, n: int) -> Path | None:
    """Acha o arquivo JP da edição n (ex: 御光話録1号)."""
    for p in sorted(JP_DIR.glob(f"*{prefixo}*")):
        m = re.search(rf"{prefixo}(\d+)号", p.stem)
        if m and int(m.group(1)) == n:
            return p
    return None


def achar_staging(contains: str, n: int) -> Path | None:
    """Acha o arquivo de staging PT da edição n."""
    for p in sorted(STAGING_DIR.glob("*.txt")):
        m = re.search(rf"{contains} nº (\d+)", p.stem)
        if m and int(m.group(1)) == n:
            return p
    return None


def limpar_cabecalho(texto: str) -> str:
    """Remove o cabeçalho do arquivo JP (até o ---)."""
    idx = texto.find("---")
    return texto[idx + 3:] if idx != -1 else texto


def dividir_falas(texto: str) -> list[tuple[str, str]]:
    """Divide em falas por rótulos. Retorna [(quem, texto)]."""
    padrao = re.compile(r"(?m)^\s*(Interlocutor:|Meishu-Sama:)")
    matches = list(padrao.finditer(texto))
    partes = []
    for i, m in enumerate(matches):
        inicio = m.start()
        fim = matches[i + 1].start() if i + 1 < len(matches) else len(texto)
        quem = m.group(1).replace(":", "")
        partes.append((quem, texto[inicio:fim].strip()))
    return partes


def montar(n: int, col: dict) -> str:
    jp_path = achar_jp(col["jp_prefix"], n)
    st_path = achar_staging(col["st_contains"], n)
    if not jp_path or not st_path:
        return f"ERRO: não achei JP={jp_path} ou ST={st_path}"

    jp = limpar_cabecalho(jp_path.read_text(encoding="utf-8"))
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
        txt_jp_clean = re.sub(r"^(Interlocutor:|Meishu-Sama:)\s*", "", txt_jp).strip()
        txt_st_clean = re.sub(r"^(Interlocutor:|Meishu-Sama:)\s*", "", txt_st).strip()
        blocos.append(f"=== FALA {i} ({quem_st}) ===")
        blocos.append(f"JP: {txt_jp_clean}")
        blocos.append(f"PT: {txt_st_clean}")
        blocos.append("")
    return "\n".join(blocos)


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1
    colecao = sys.argv[1]
    n = int(sys.argv[2])
    if colecao not in COLECOES:
        print(f"coleção inválida: {colecao} (use gokowa|gosuiji)")
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    material = montar(n, COLECOES[colecao])
    if material.startswith("ERRO"):
        print(material)
        return 1
    out = OUT_DIR / f"material_semantico_{colecao}_{n}.txt"
    out.write_text(material, encoding="utf-8")
    print(f"{colecao} {n}: {material.count('=== FALA')} falas -> {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
