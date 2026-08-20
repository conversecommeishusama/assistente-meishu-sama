#!/usr/bin/env python3
"""Diagnóstico: cruza as 8 specs dos Mioshie-shū com os consolidados novos.

Para cada arquivo (1-8):
  - Lista as sessões da spec (title_jp / title_pt, início do jp_anchor e do pt_anchor)
  - Lista os marcadores [data] reais presentes no consolidado novo (revisao_literaria/orais)
  - Indica, para cada sessão da spec, se o pt_anchor antigo encontra correspondência
    textual exata (prefixo) no consolidado novo.
"""
import json
import re
import sys
from pathlib import Path

SPEC_DIR = Path("reports/livros_trabalho/segmentacao_manual")
ORAL_DIR = Path("revisao_literaria/orais")

# Mapeamento nº -> stem do spec (filename) e do consolidado
MAP = {
    1: "19510920",
    2: "19511025",
    3: "19511125",
    4: "19511215",
    5: "19520115",
    6: "19510225",
    7: "19520320",
    8: "19520420",
}


def normalize(s: str) -> str:
    """Remove espaços, quebras e normaliza para comparação frouxa."""
    if not s:
        return ""
    s = s.replace("\n", " ").replace("\r", " ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def main() -> int:
    report = []
    for n in range(1, 9):
        stem = MAP[n]
        spec_files = list(SPEC_DIR.glob(f"{stem} - Mioshie-shū nº {n}.txt.json"))
        if not spec_files:
            print(f"[{n}] SEM SPEC encontrada para {stem}")
            continue
        spec_path = spec_files[0]
        spec = json.loads(spec_path.read_text(encoding="utf-8"))

        oral_candidates = list(ORAL_DIR.glob(f"{stem} - Mioshie-shū nº {n}.txt"))
        if not oral_candidates:
            print(f"[{n}] SEM CONSOLIDADO para {stem}")
            continue
        oral_text = oral_candidates[0].read_text(encoding="utf-8")
        # Texto normalizado do consolidado para busca
        oral_norm = normalize(oral_text)

        # Marcadores de data no consolidado: linhas "[... de ...]" ou "[data]"
        markers = re.findall(r"^\[([^\]]+)\]\s*$", oral_text, flags=re.M)

        lines = []
        lines.append("=" * 90)
        lines.append(f"ARQUIVO {n}: {spec_path.name}")
        lines.append(f"  Marcadores de sessão no CONSOLIDADO novo: {markers}")
        lines.append(f"  Nº de artigos na spec: {len(spec.get('articles', []))}")
        lines.append("")

        for art in spec.get("articles", []):
            kind = art.get("kind", "")
            tjp = art.get("title_jp", "")
            tpt = art.get("title_pt", "")
            jpa = normalize(art.get("jp_anchor", ""))
            pta = normalize(art.get("pt_anchor", ""))
            # Prefixo a testar: os primeiros ~60 chars normalizados do pt_anchor
            # (ignora prefixos rotulados como "Interlocutor:", "Meishu-Sama:", "[Ensinamento]")
            test = pta
            test = re.sub(r"^(Interlocutor|Meishu-Sama|Ensinamento)\s*:\s*", "", test).strip()
            test = re.sub(r"^\[Ensinamento\]\s*", "", test).strip()
            probe = test[:70]
            found = probe and (probe in oral_norm or normalize(probe) in oral_norm)

            lines.append(f"  [{kind}] {tjp} | {tpt}")
            lines.append(f"     jp_anchor : {jpa[:70]}...")
            lines.append(f"     pt_anchor : {pta[:70]}...")
            lines.append(f"     >>> prefixo pt_anchor encontra no consolidado? {'SIM' if found else 'NAO'}")
            if not found and pta:
                # tenta buscar por tokens-chave (nome próprio da primeira frase)
                m = re.search(r"[A-ZÀ-Ú][a-zà-ú]+(?:\s+[A-ZÀ-Ú][a-zà-ú]+)*", test)
                if m:
                    key = m.group(0)
                    if key in oral_norm:
                        lines.append(f"     (mas o nome '{key}' aparece no consolidado)")
            lines.append("")

        report.append("\n".join(lines))

    print("\n".join(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
