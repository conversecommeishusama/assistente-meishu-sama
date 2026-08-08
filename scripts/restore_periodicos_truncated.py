#!/usr/bin/env python3
"""Restaura corpos PT truncados em periodicos_trabalho a partir de staging de retradução."""

from __future__ import annotations

import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from audit_translation_glossary import load_translation_glossary  # noqa: E402
from fix_periodicos_work_headers import ARTICLE_SEP, format_article, parse_article, split_file  # noqa: E402
from periodicos_traducao_glossary import WORK_ROOT, audit_article_row, collect_articles  # noqa: E402

# entry_id -> staging path (PT embutido no ficheiro de staging)
TRUNCATED_SOURCES: dict[str, Path] = {
    "publication-jp-1211": PROJECT_ROOT
    / "reports/translation_review/retranslate_mass/20260619T142344Z/corpus/data/publication_sources/jp/tijotengoku/20-de-setembro-de-1949-sobre-os-espiritos-de-raposa-publication-jp-1211.txt",
}

MARKER = "fiz o seguinte diálogo:"


def extract_staging_continuation(staging_raw: str) -> str:
    """Extrai texto PT após o marcador de truncamento (diálogo)."""
    # O ficheiro repete o intro; usar a última ocorrência longa do marcador.
    idx = -1
    for m in re.finditer(re.escape(MARKER), staging_raw, flags=re.I):
        idx = m.end()
    if idx < 0:
        return ""
    tail = staging_raw[idx:].strip()
    # Remover cabeçalho duplicado se colado no meio
    tail = re.sub(r"^Publication source:.*?(?=\n\n|\nEu:)", "", tail, flags=re.S)
    return tail.strip()


def merge_body(work_body: str, continuation: str) -> str:
    if not continuation:
        return work_body
    base = work_body.rstrip()
    if MARKER.lower() in base.lower():
        # Cortar no marcador e anexar continuação limpa
        m = re.search(re.escape(MARKER), base, flags=re.I)
        if m:
            base = base[: m.end()].rstrip()
    if continuation.lower().startswith("eu:"):
        return base + "\n\n" + continuation
    return base + "\n\n" + continuation


def apply_glossary_fixes_to_body(body: str) -> str:
    """Correções mínimas no texto restaurado (proibidos + glossário)."""
    subs = [
        (r"\bTerapia Absoluta\b", "terapia"),
        (r"\bancestral deste corpo\b", "antepassado deste corpo"),
        (r"\bnome de um ancestral\b", "nome de um antepassado"),
        (r"\bIrradiação Espiritual\b", "Irradiação Espiritual"),  # keep
    ]
    out = body
    for old, new in subs:
        out = re.sub(old, new, out)
    return out


def restore_truncated(*, dry_run: bool = False) -> dict:
    glossary = load_translation_glossary()
    rows = {r["jp_art"].fields.get("entry_id"): r for r in collect_articles()}
    restored: list[dict] = []
    files_touched: set[str] = set()

    for entry_id, staging_path in TRUNCATED_SOURCES.items():
        row = rows.get(entry_id)
        if not row or not staging_path.exists():
            continue
        staging_raw = staging_path.read_text(encoding="utf-8")
        continuation = extract_staging_continuation(staging_raw)
        if not continuation:
            continue
        pa = row["pt_art"]
        new_body = apply_glossary_fixes_to_body(merge_body(pa.content, continuation))
        if new_body == pa.content:
            continue

        before = audit_article_row(row, glossary)
        trial = {
            "jp_art": row["jp_art"],
            "pt_art": type(pa)(pa.fields, pa.meta, new_body),
            "file": row["file"],
        }
        after = audit_article_row(trial, glossary)
        improved = len(after.get("hits", [])) < len(before.get("hits", []))
        substantial = len(new_body) > len(pa.content) * 1.15
        if not improved and not substantial:
            continue
        restored.append(
            {
                "entry_id": entry_id,
                "file": row["file"],
                "chars_before": len(pa.content),
                "chars_after": len(new_body),
                "hits_before": len(before.get("hits", [])),
                "hits_after": len(after.get("hits", [])),
            }
        )
        if not dry_run:
            row["_new_body"] = new_body
            files_touched.add(row["file"])

    if dry_run:
        return {"restored": restored, "dry_run": True}

    by_file: dict[str, list[tuple[str, str]]] = {}
    for entry_id, row in rows.items():
        if "_new_body" in row:
            by_file.setdefault(row["file"], []).append((entry_id, row["_new_body"]))

    for fname, updates in by_file.items():
        jp_path = WORK_ROOT / "jp" / fname
        pt_path = WORK_ROOT / "pt" / fname
        _, jp_blocks = split_file(jp_path.read_text(encoding="utf-8"))
        _, pt_blocks = split_file(pt_path.read_text(encoding="utf-8"))
        upd_map = dict(updates)
        out_pt: list[str] = []
        for jp_block, pt_block in zip(jp_blocks, pt_blocks):
            jp_art = parse_article(jp_block)
            eid = jp_art.fields.get("entry_id", "")
            if eid in upd_map:
                pt_art = parse_article(pt_block)
                out_pt.append(format_article(pt_art.fields, pt_art.meta, upd_map[eid]))
            else:
                out_pt.append(
                    pt_block if pt_block.lstrip().startswith(ARTICLE_SEP) else ARTICLE_SEP + pt_block
                )
        pt_header = pt_path.read_text(encoding="utf-8").split(ARTICLE_SEP)[0]
        pt_path.write_text(pt_header + "".join(out_pt), encoding="utf-8")

    zip_path = WORK_ROOT / "periodicos_trabalho.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(WORK_ROOT.rglob("*")):
            if path.is_file() and path.name != zip_path.name:
                zf.write(path, path.relative_to(WORK_ROOT).as_posix())

    audited = [audit_article_row(r, glossary) for r in collect_articles()]
    ok = sum(1 for a in audited if a["ok"])
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "restored": restored,
        "articles_ok": ok,
        "articles_flagged": len(audited) - ok,
        "zip": str(zip_path),
    }


def main() -> int:
    import argparse

    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    result = restore_truncated(dry_run=args.dry_run)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
