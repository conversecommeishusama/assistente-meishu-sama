#!/usr/bin/env python3
"""Pacificação automática: audit → apply → audit até glossário estabilizar (680 artigos)."""

from __future__ import annotations

import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from audit_translation_glossary import load_translation_glossary  # noqa: E402
from fix_periodicos_work_headers import split_file  # noqa: E402
from periodicos_traducao_glossary import (  # noqa: E402
    FORBIDDEN_PATTERNS,
    WORK_ROOT,
    apply_file_pair,
    audit_article_row,
    collect_articles,
    load_entries,
)

MAX_ITERATIONS = 20


def run_audit(glossary: dict) -> tuple[list[dict], dict]:
    rows = collect_articles()
    audited = [audit_article_row(r, glossary) for r in rows]
    flagged = [a for a in audited if not a["ok"]]
    ok = len(audited) - len(flagged)

    forbidden_totals = {name: 0 for name, _ in FORBIDDEN_PATTERNS}
    for pt_file in (WORK_ROOT / "pt").glob("*.txt"):
        text = pt_file.read_text(encoding="utf-8")
        for name, pat in FORBIDDEN_PATTERNS:
            forbidden_totals[name] += len(pat.findall(text))

    missing_hits = sum(1 for a in flagged for h in a["hits"] if h.startswith("missing:"))

    summary = {
        "total_articles": len(audited),
        "articles_ok": ok,
        "articles_flagged": len(flagged),
        "ok_pct": round(ok / len(audited) * 100, 2) if audited else 0,
        "forbidden_totals": forbidden_totals,
        "missing_term_hits": missing_hits,
        "flagged_by_issue": {},
    }
    for a in flagged:
        for h in a["hits"]:
            summary["flagged_by_issue"][h] = summary["flagged_by_issue"].get(h, 0) + 1

    return audited, summary


def rebuild_zip() -> Path:
    zip_path = WORK_ROOT / "periodicos_trabalho.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(WORK_ROOT.rglob("*")):
            if path.is_file() and path.name != zip_path.name:
                zf.write(path, path.relative_to(WORK_ROOT).as_posix())
    return zip_path


def main() -> int:
    glossary = load_translation_glossary()
    jp_by_id = load_entries()
    history: list[dict] = []

    for iteration in range(1, MAX_ITERATIONS + 1):
        audited, summary = run_audit(glossary)
        audit_by_id = {a["entry_id"]: a for a in audited}

        round_info = {
            "iteration": iteration,
            "phase": "audit",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **summary,
        }
        history.append(round_info)

        print(json.dumps(round_info, ensure_ascii=False, indent=2))

        if summary["articles_flagged"] == 0:
            print("PACIFICADO: 680/680 OK")
            break

        total_patched = 0
        total_replacements = 0
        staging_reimports = 0
        for jp_file in sorted((WORK_ROOT / "jp").glob("*.txt")):
            pt_file = WORK_ROOT / "pt" / jp_file.name
            report, reps = apply_file_pair(jp_file, pt_file, jp_by_id, audit_by_id)
            total_patched += len(report)
            total_replacements += reps
            staging_reimports += sum(1 for r in report if r.get("action") == "staging_reimport")

        # Cabeçalhos §4.4-A
        import fix_periodicos_work_headers  # noqa: WPS433

        fix_periodicos_work_headers.main()

        apply_info = {
            "iteration": iteration,
            "phase": "apply",
            "articles_patched": total_patched,
            "total_replacements": total_replacements,
            "staging_reimports": staging_reimports,
        }
        history.append(apply_info)
        print(json.dumps(apply_info, ensure_ascii=False, indent=2))

        if total_replacements == 0 and staging_reimports == 0:
            # Sem progresso automático — parar para evitar loop infinito
            print("PARADO: nenhuma substituição/reimport nesta ronda")
            break

    # Auditoria final
    audited_final, summary_final = run_audit(glossary)
    timestamp = datetime.now(timezone.utc).isoformat()
    out = {
        "timestamp": timestamp,
        "glossary": "glossario_traducao.json",
        "iterations_run": len([h for h in history if h.get("phase") == "audit"]),
        "history": history,
        "final": summary_final,
        "flagged": [a for a in audited_final if not a["ok"]],
    }

    json_path = WORK_ROOT / "GLOSSARY_TRADUCAO_PACIFICACAO.json"
    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    zip_path = rebuild_zip()

    print(json.dumps({"final": summary_final, "report": str(json_path), "zip": str(zip_path)}, ensure_ascii=False, indent=2))

    import os

    forbidden_clean = all(v == 0 for v in summary_final.get("forbidden_totals", {}).values())
    seg = os.environ.get("ACERVO_SEGMENT", "periodicos")
    if seg != "periodicos" and forbidden_clean:
        # Livros/capítulos: termos proibidos zerados → OK; missing terms continuam no relatório
        return 0
    return 0 if summary_final["articles_flagged"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
