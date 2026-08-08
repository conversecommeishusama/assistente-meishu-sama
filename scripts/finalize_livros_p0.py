#!/usr/bin/env python3
"""P0 livros_acervo: renomear vírgulas, excluir stubs, documentar âmbito."""

from __future__ import annotations

import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/var/www/goshinsho")
if not ROOT.is_dir():
    ROOT = Path(__file__).resolve().parents[1]

WORK = ROOT / "reports/livros_trabalho"
JP_SRC = ROOT / "textos_japones"
PT_SRC = ROOT / "textos_portugues"
CORPUS = ROOT / "data/clean_corpus/entries.jsonl"
PUB = ROOT / "data/publication_sources/entries.jsonl"

# Renomear vírgula → hífen após data YYYYMMDD
COMMA_RENAMES = {
    "19520615,御垂示録10号.txt": "19520615-御垂示録10号.txt",
    "19530915,御垂示録24号.txt": "19530915-御垂示録24号.txt",
    "19511210,御垂示録4号.txt": "19511210-御垂示録4号.txt",
}

EXCLUDE_FROM_WORK = (
    "未刊行-自観叢書第11篇『神示の病理』.txt",
    "未刊行-自観叢書第14篇『天国の花]』.txt",
)

BOOK_CATEGORIES_CAPITULOS = {
    "Evangelho do Reino dos Céus",
    "Shinko Zatsuwa",
    "Jikan Sosho",
    "Salvando a América",
    "Terapia Revolucionária da Tuberculose",
    "Terapia de Fé para Tuberculose",
    "Guia Rápido da Igreja Messiânica Mundial",
    "Agricultura Natural",
    "Esboço da Medicina",
    "Verdadeira Natureza da Tuberculose",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def rename_acervo_files() -> list[dict]:
    changes = []
    for old, new in COMMA_RENAMES.items():
        for sub, base in (("textos_japones", JP_SRC), ("textos_portugues", PT_SRC)):
            src = base / old
            dst = base / new
            if src.is_file() and not dst.is_file():
                src.rename(dst)
                changes.append({"action": "rename", "from": f"{sub}/{old}", "to": f"{sub}/{new}"})
            elif dst.is_file():
                changes.append({"action": "already_renamed", "path": f"{sub}/{new}"})
    return changes


def update_entries_jsonl(path: Path, renames: dict[str, str]) -> int:
    if not path.is_file():
        return 0
    lines = path.read_text(encoding="utf-8").splitlines()
    updated = 0
    out_lines = []
    for line in lines:
        if not line.strip():
            continue
        row = json.loads(line)
        orig = row.get("original_path", "")
        for old, new in renames.items():
            if orig.endswith(old):
                row["original_path"] = orig.replace(old, new)
                updated += 1
                break
        out_lines.append(json.dumps(row, ensure_ascii=False))
    path.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    return updated


def remove_excluded_work_files() -> list[str]:
    removed = []
    excl_set = set(EXCLUDE_FROM_WORK)
    for sub in ("jp", "pt"):
        d = WORK / sub
        if not d.is_dir():
            continue
        for name in excl_set:
            p = d / name
            if p.is_file():
                p.unlink()
                removed.append(f"{sub}/{name}")
    return removed


def load_file_entries() -> list[dict]:
    rows = []
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("entry_type") == "file" and e.get("lang") == "jp":
            rows.append(e)
    return rows


def verify_capitulos_boundary(kept_filenames: set[str]) -> dict:
    pub_jp = []
    for line in PUB.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("lang") == "jp" and e.get("source_category") in BOOK_CATEGORIES_CAPITULOS:
            pub_jp.append(e)

    by_cat_pub = Counter(e["source_category"] for e in pub_jp)
    by_cat_file = Counter()
    for e in load_file_entries():
        name = Path(e["original_path"]).name
        if name in kept_filenames:
            by_cat_file[e.get("source_category", "?")] += 1

    overlap_cats = sorted(set(by_cat_pub) & set(by_cat_file))

    return {
        "livros_acervo_scope": "Monolitos em textos_japones/ + textos_portugues/ (1 ficheiro = 1 livro)",
        "capitulos_publication_scope": "Artigos JP em publication_sources/ das categorias-livro (capítulos partidos)",
        "capitulos_jp_article_count": len(pub_jp),
        "capitulos_by_category": dict(by_cat_pub),
        "livros_kept_by_category": dict(by_cat_file),
        "categories_in_both_layers": overlap_cats,
        "relationship": (
            "Os 238 artigos em publication_sources são capítulos/entradas catalogadas separadamente. "
            "Os monolitos em textos_* contêm o livro integral (ou volume). "
            "Não são duplicatas a excluir na P0: são camadas diferentes — livros_acervo edita o monolito; "
            "capitulos_publication (segmento futuro) edita os artigos partidos. "
            "Após promoção do monolito, os capítulos correspondentes devem ser sincronizados (P12)."
        ),
        "same_as_periodicos_logic": (
            "Análogo aos periódicos: 239 artigos publication_sources foram excluídos do pacote periodicos "
            "porque o conteúdo integral está no acervo monolítico. Aqui o inverso: os capítulos ficam FORA "
            "de livros_acervo e entram no segmento capitulos_publication."
        ),
        "confirmed_separate_segments": True,
    }


def inventario_kept() -> tuple[set[str], list[dict], dict]:
    excl = set(EXCLUDE_FROM_WORK)
    jp_all = {p.name for p in JP_SRC.glob("*.txt")}
    kept = jp_all - excl
    excluded_rows = []
    by_orig = {}
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        e = json.loads(line)
        if e.get("entry_type") == "file" and e.get("lang") == "jp":
            by_orig[Path(e["original_path"]).name] = e

    for name in sorted(excl):
        e = by_orig.get(name, {})
        excluded_rows.append({
            "filename": name,
            "entry_id": e.get("entry_id", ""),
            "source_category": e.get("source_category", ""),
            "title": e.get("title", ""),
            "reason": "unpublished_stub",
            "note": "Aviso de não publicação (~500 bytes); sem texto integral do volume.",
        })

    pairs = []
    missing_pt = []
    for name in sorted(kept):
        if (PT_SRC / name).is_file():
            pairs.append(name)
        else:
            missing_pt.append(name)

    cat = Counter(by_orig.get(n, {}).get("source_category", "?") for n in pairs)

    summary = {
        "segment": "livros_acervo",
        "timestamp": utc_now(),
        "source_jp_total": len(jp_all),
        "source_pt_total": len(list(PT_SRC.glob("*.txt"))),
        "excluded_count": len(excl),
        "kept_count": len(kept),
        "pairs": len(pairs),
        "missing_pt": missing_pt,
        "pair_ok": not missing_pt,
        "comma_renames_applied": COMMA_RENAMES,
        "by_category": dict(sorted(cat.items())),
    }
    return kept, excluded_rows, summary


def write_readme(summary: dict, boundary: dict) -> None:
    excl = summary["excluded_count"]
    kept = summary["kept_count"]
    cats = "\n".join(f"  - {k}: {v}" for k, v in summary["by_category"].items())
    text = f"""Pacote de trabalho — livros monolíticos (textos_japones / textos_portugues)

Segmento: livros_acervo (P0 aprovado)
Actualizado: {summary['timestamp']}

## Âmbito

INCLUÍDO ({kept} pares JP/PT):
  Fonte: textos_japones/*.txt ↔ textos_portugues/*.txt
  Layout: 1 ficheiro = 1 livro = 1 artigo (=== ARTIGO ===)
  Work files: reports/livros_trabalho/jp/ e pt/

EXCLUÍDO deste pacote ({excl} ficheiros):
  - 未刊行-自観叢書第11篇『神示の病理』.txt — stub (não publicado)
  - 未刊行-自観叢書第14篇『天国の花]』.txt — stub (não publicado)
  Ver: excluidos/inventario_exclusoes.jsonl
  Nota: permanecem no acervo fonte; só não entram no pacote editorial.

FORA DESTE SEGMENTO (segmento futuro: capitulos_publication):
  - {boundary['capitulos_jp_article_count']} artigos JP em publication_sources/
  - Categorias-livro: Evangelho, Jikan Sosho, Shinko Zatsuwa, tuberculose, etc.
  - Não duplicar trabalho: monolito aqui; capítulos partidos no segmento seguinte.

## Renomeações P0 (vírgula → hífen)

  19511210,御垂示録4号.txt → 19511210-御垂示録4号.txt
  19520615,御垂示録10号.txt → 19520615-御垂示録10号.txt
  19530915,御垂示録24号.txt → 19530915-御垂示録24号.txt

## Distribuição por categoria (livros incluídos)

{cats}

## Relação monolito ↔ capítulos

{boundary['relationship']}

Separador entre artigos: === ARTIGO ===
"""
    (WORK / "README.txt").write_text(text, encoding="utf-8")


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    (WORK / "excluidos").mkdir(parents=True, exist_ok=True)

    renames = rename_acervo_files()
    corpus_updates = update_entries_jsonl(CORPUS, COMMA_RENAMES)

    # Renomear work files se existirem
    for old, new in COMMA_RENAMES.items():
        for sub in ("jp", "pt"):
            d = WORK / sub
            s, t = d / old, d / new
            if s.is_file() and not t.is_file():
                s.rename(t)

    removed_work = remove_excluded_work_files()
    kept, excluded_rows, summary = inventario_kept()
    boundary = verify_capitulos_boundary(kept)

    excl_path = WORK / "excluidos" / "inventario_exclusoes.jsonl"
    excl_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in excluded_rows) + "\n",
        encoding="utf-8",
    )

    write_readme(summary, boundary)

    p0 = {
        **summary,
        "p0_status": "complete",
        "renames": renames,
        "corpus_entries_updated": corpus_updates,
        "work_files_removed": removed_work,
        "capitulos_boundary": boundary,
        "artifacts": [
            "manifest.json",
            "README.txt",
            "excluidos/inventario_exclusoes.jsonl",
            "INVENTARIO_P0.json",
        ],
    }
    (WORK / "manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (WORK / "INVENTARIO_P0.json").write_text(json.dumps(p0, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(p0, ensure_ascii=False, indent=2))
    return 0 if summary["pair_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
