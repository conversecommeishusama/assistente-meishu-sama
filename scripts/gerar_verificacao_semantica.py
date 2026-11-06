#!/usr/bin/env python3
"""Gera o pacote de VERIFICAÇÃO SEMÂNTICA por sessão dos Mioshie-shū (1-8).

Para cada arquivo, para cada sessão da spec:
  - título (title_jp / title_pt)
  - jp_anchor (curto) e início do chunk JP (split_by_anchors no staging JP)
  - pt_anchor (marcador) e início do chunk PT (split_by_anchors no staging PT)

Escreve em reports/verificacao_semantica_mioshie_20260820/ um arquivo por nº,
para leitura humana/semântica.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_manual_livros_segmentacao import split_by_anchors
from build_clean_large_indexes import clean_body

ROOT = Path(__file__).resolve().parent.parent
SPEC_DIR = ROOT / "reports/livros_trabalho/segmentacao_manual"
PT_DIR = ROOT / "reports/livros_trabalho/pt"
JP_DIR = ROOT / "reports/livros_trabalho/jp"
OUT_DIR = ROOT / "reports" / "verificacao_semantica_mioshie_20260820"

MAPA = {
    1: ("19510920-御教え集1号", "19510920 - Mioshie-shū nº 1"),
    2: ("19511025-御教え集2号", "19511025 - Mioshie-shū nº 2"),
    3: ("19511125-御教え集3号", "19511125 - Mioshie-shū nº 3"),
    4: ("19511215-御教え集4号", "19511215 - Mioshie-shū nº 4"),
    5: ("19520115-御教え集5号", "19520115 - Mioshie-shū nº 5"),
    6: ("19510225-御教え集6号", "19510225 - Mioshie-shū nº 6"),
    7: ("19520320-御教え集7号", "19520320 - Mioshie-shū nº 7"),
    8: ("19520420-御教え集8号", "19520420 - Mioshie-shū nº 8"),
}

PREVIEW = 400  # chars de cada lado


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for n in range(1, 9):
        stem_jp, nome_pt = MAPA[n]
        spec = json.loads((SPEC_DIR / f"{nome_pt}.txt.json").read_text(encoding="utf-8"))
        arts = spec["articles"]
        jp_anc = [a.get("jp_anchor", "") for a in arts]
        pt_anc = [a.get("pt_anchor", "") for a in arts]

        jp_texto = clean_body((JP_DIR / f"{stem_jp}.txt").read_text(encoding="utf-8").replace("\r\n", "\n"))
        pt_texto = clean_body((PT_DIR / f"{nome_pt}.txt").read_text(encoding="utf-8").replace("\r\n", "\n"))
        jp_chunks = split_by_anchors(jp_texto, jp_anc, label="JP")
        pt_chunks = split_by_anchors(pt_texto, pt_anc, label="PT")

        L = []
        L.append(f"VERIFICAÇÃO SEMÂNTICA — {nome_pt}")
        L.append(f"artigos: {len(arts)} | JP chunks: {len(jp_chunks)} | PT chunks: {len(pt_chunks)}")
        L.append("=" * 80)
        for i, art in enumerate(arts):
            L.append("")
            L.append(f"### ARTIGO {i + 1}  [{art.get('kind')}]")
            L.append(f"  title_jp : {art.get('title_jp')}")
            L.append(f"  title_pt : {art.get('title_pt')}")
            L.append(f"  jp_anchor: {art.get('jp_anchor', '')[:100]}")
            L.append(f"  pt_anchor: {art.get('pt_anchor', '')}")
            if i < len(jp_chunks):
                jp = jp_chunks[i]
                L.append(f"  --- JP (início, {PREVIEW} chars) ---")
                L.append(f"  {jp[:PREVIEW].replace(chr(10), ' ')}")
            if i < len(pt_chunks):
                pt = pt_chunks[i]
                L.append(f"  --- PT (início, {PREVIEW} chars) ---")
                L.append(f"  {pt[:PREVIEW].replace(chr(10), ' ')}")
        dest = OUT_DIR / f"n{n:02d}_{stem_jp}.txt"
        dest.write_text("\n".join(L) + "\n", encoding="utf-8")
        print(f"✓ {dest.name} ({len(arts)} artigos)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
