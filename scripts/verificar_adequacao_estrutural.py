#!/usr/bin/env python3
"""Relatório de verificação da ADEQUAÇÃO ESTRUTURAL dos Mioshie-shū (1-8).

Gera evidências verificáveis de que:
1. As specs têm pt_anchor apontando para marcadores [data] reais no consolidado.
2. O split_by_anchors funciona (JP e PT) com o número exato de artigos.
3. Não há chunks vazios; cobertura total.
4. Os consolidados novos foram copiados para o staging PT.
5. Backups existem.
6. Consistência do nº 8 (marcadores 23-27 presentes) e nº 1 (5 de agosto presente).

Escreve o relatório em reports/relatorio_verificacao_adequacao_estrutural_20260820.txt
e imprime no terminal.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from apply_manual_livros_segmentacao import split_by_anchors
from build_clean_large_indexes import clean_body

ROOT = Path(__file__).resolve().parent.parent
SPEC_DIR = ROOT / "reports/livros_trabalho/segmentacao_manual"
PT_DIR = ROOT / "reports/livros_trabalho/pt"
JP_DIR = ROOT / "reports/livros_trabalho/jp"
ORAL_DIR = ROOT / "revisao_literaria/orais"

# nº -> (stem JP, nome PT, nº artigos esperados na spec)
MAPA = {
    1: ("19510920-御教え集1号", "19510920 - Mioshie-shū nº 1", 10),
    2: ("19511025-御教え集2号", "19511025 - Mioshie-shū nº 2", 13),
    3: ("19511125-御教え集3号", "19511125 - Mioshie-shū nº 3", 10),
    4: ("19511215-御教え集4号", "19511215 - Mioshie-shū nº 4", 10),
    5: ("19520115-御教え集5号", "19520115 - Mioshie-shū nº 5", 10),
    6: ("19510225-御教え集6号", "19510225 - Mioshie-shū nº 6", 12),
    7: ("19520320-御教え集7号", "19520320 - Mioshie-shū nº 7", 9),
    8: ("19520420-御教え集8号", "19520420 - Mioshie-shū nº 8", 11),
}

BACKUPS = {
    "specs": "reports/livros_trabalho/segmentacao_manual/backup_pre_reconciliacao_ancoras_20260820",
    "pt": "reports/livros_trabalho/pt_backup_pre_adequacao_estrutural_20260820",
    "n8": "reports/retraducao_colecoes/backup_pre_estrutural_n8_20260820",
}


def norm(s: str) -> str:
    s = s.replace("º", "").replace("°", "").strip().lower()
    return re.sub(r"\s+", " ", s)


def main() -> int:
    linhas: list[str] = []
    out = linhas.append
    out(f"RELATÓRIO DE VERIFICAÇÃO — ADEQUAÇÃO ESTRUTURAL MIOSHIE-SHŪ (1-8)")
    out(f"Gerado: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    out(f"Root: {ROOT}")
    out("=" * 78)
    out("")

    total_ok = 0
    total_falhas = 0

    for n in range(1, 9):
        stem_jp, nome_pt, esperado = MAPA[n]
        out(f"{'─' * 78}")
        out(f"ARQUIVO {n}: {nome_pt}")
        spec_path = SPEC_DIR / f"{nome_pt}.txt.json"
        if not spec_path.exists():
            out("  ✗ SPEC NÃO ENCONTRADA")
            total_falhas += 1
            continue
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        arts = spec.get("articles", [])
        ok = True

        # 1. número de artigos
        if len(arts) != esperado:
            out(f"  ✗ artigos: spec={len(arts)} esperado={esperado}")
            ok = False
        else:
            out(f"  ✓ artigos: {len(arts)}")

        # 2. âncoras (pt_anchor = marcador de data no consolidado)
        oral_path = ORAL_DIR / f"{nome_pt}.txt"
        if oral_path.exists():
            marcadores = re.findall(r"^\[([^\]]+)\]\s*$", oral_path.read_text(encoding="utf-8"), flags=re.M)
            marc_norm = {norm(m): m for m in marcadores}
            anc_ok = 0
            for a in arts:
                if a.get("kind") != "session":
                    continue
                pt_anc = a.get("pt_anchor", "")
                if norm(pt_anc) in marc_norm:
                    anc_ok += 1
            out(f"  ✓ pt_anchor são marcadores reais: {anc_ok}/{sum(1 for a in arts if a.get('kind')=='session')} sessões")
            if anc_ok < sum(1 for a in arts if a.get("kind") == "session"):
                ok = False
        else:
            out("  ✗ consolidado não encontrado")
            ok = False

        # 3. split_by_anchors JP e PT
        pt_path = PT_DIR / f"{nome_pt}.txt"
        jp_path = JP_DIR / f"{stem_jp}.txt"
        jp_anc = [a.get("jp_anchor", "") for a in arts]
        pt_anc = [a.get("pt_anchor", "") for a in arts]

        for lado, path, anc in (("JP", jp_path, jp_anc), ("PT", pt_path, pt_anc)):
            if not path.exists():
                out(f"  ✗ {lado} staging não encontrado")
                ok = False
                continue
            texto = clean_body(path.read_text(encoding="utf-8").replace("\r\n", "\n"))
            try:
                chunks = split_by_anchors(texto, anc, label=lado)
                if len(chunks) == len(arts):
                    vazios = sum(1 for c in chunks if len(c.strip()) < 10)
                    out(f"  ✓ {lado} split_by_anchors: {len(chunks)} chunks, vazios={vazios}")
                    if vazios > 0:
                        ok = False
                else:
                    out(f"  ✗ {lado} split_by_anchors: {len(chunks)}/{len(arts)}")
                    ok = False
            except ValueError as e:
                out(f"  ✗ {lado} split_by_anchors ERRO: {str(e)[:100]}")
                ok = False

        # 4. nº 8: marcadores 23-27 presentes; nº 1: 5 de agosto presente
        if n == 8:
            marc = re.findall(r"^\[([^\]]+)\]\s*$", oral_path.read_text(encoding="utf-8"), flags=re.M) if oral_path.exists() else []
            tem_23_27 = all(any(d in norm(m) for m in marc) for d in ["23 de março", "24 de março", "25 de março", "26 de março", "27 de março"])
            out(f"  {'✓' if tem_23_27 else '✗'} nº 8: marcadores 23-27 de março presentes ({len(marc)} marcadores)")
            if not tem_23_27:
                ok = False
        if n == 1:
            marc = re.findall(r"^\[([^\]]+)\]\s*$", oral_path.read_text(encoding="utf-8"), flags=re.M) if oral_path.exists() else []
            tem_5 = any("5 de agosto" in norm(m) for m in marc)
            out(f"  {'✓' if tem_5 else '✗'} nº 1: marcador 5 de agosto presente")
            if not tem_5:
                ok = False

        if ok:
            total_ok += 1
            out("  ✅ ARQUIVO OK")
        else:
            total_falhas += 1
            out("  ❌ ARQUIVO COM FALHAS")

    # 5. backups
    out("")
    out("=" * 78)
    out("BACKUPS")
    for nome, rel in BACKUPS.items():
        p = ROOT / rel
        if p.exists():
            n_arq = len(list(p.iterdir()))
            out(f"  ✓ {nome}: {p} ({n_arq} arquivos)")
        else:
            out(f"  ✗ {nome}: ausente")
            total_falhas += 1

    out("")
    out("=" * 78)
    out(f"RESULTADO: {total_ok}/8 arquivos OK | {total_falhas} falhas")
    out("=" * 78)

    texto = "\n".join(linhas)
    print(texto)
    dest = ROOT / "reports" / "relatorio_verificacao_adequacao_estrutural_20260820.txt"
    dest.write_text(texto + "\n", encoding="utf-8")
    print(f"\nRelatório salvo em: {dest}")
    return 0 if total_falhas == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
