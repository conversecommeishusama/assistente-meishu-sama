#!/usr/bin/env python3
"""Auditoria completa de títulos JP/PT nos artigos periodicos_trabalho."""

from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
DEPLOY_SCRIPTS = Path("/var/www/goshinsho/scripts")
if DEPLOY_SCRIPTS.is_dir():
    sys.path.insert(0, str(DEPLOY_SCRIPTS))

from build_periodicos_work_files import (  # noqa: E402
    STAGING_PT_TITLE_OVERRIDES,
    TITLE_PT_OVERRIDES,
    clean_title,
    parse_pt_title_from_raw,
    read_file_text,
    resolve_pt_path,
    slug_key,
)
from fix_periodicos_work_headers import (  # noqa: E402
    parse_article,
    pick_pt_title,
    split_file,
)
from translation_header_parser import (  # noqa: E402
    PERIODICAL_FICHA_RE,
    SERIES_FICHA_RE,
    parse_jp_source_metadata,
)

from acervo_work_paths import work_root  # noqa: E402

WORK_ROOT = work_root()

ENTRIES_CANDIDATES = (
    PROJECT_ROOT / "data/publication_sources/entries.jsonl",
    Path("/var/www/goshinsho/data/publication_sources/entries.jsonl"),
)

CJK_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
JP_EDITORIAL_TITLE_RE = re.compile(r"^[＊*]|掲載|割愛|対談は|関連性がない")
TITLE_GLUE_RE = re.compile(
    r"^(Meishu-Sama:|Title:|\?|No entanto,|Em suma,|A respeito|Escreverei|Recentemente|Pelo exposto|Como acima|No ano passado|Dos meus)",
    re.I,
)
GENERIC_PT_TITLES = {
    "O Princípio da nossa terapia",
    "Palestra",
    "Sermão",
    "Conclusão",
    "Prefácio",
    "Introdução",
}


def entries_path() -> Path:
    for path in ENTRIES_CANDIDATES:
        if path.is_file():
            return path
    raise FileNotFoundError("entries.jsonl não encontrado")


def load_catalog() -> tuple[dict[str, dict], dict[str, dict], dict[str, dict]]:
    entries = [json.loads(line) for line in entries_path().read_text(encoding="utf-8").splitlines()]
    jp_by_id = {e["entry_id"]: e for e in entries if e.get("lang") == "jp"}
    pt_by_id = {e["entry_id"]: e for e in entries if e.get("lang") == "pt"}
    pt_by_slug = {slug_key(e["clean_path"]): e for e in entries if e.get("lang") == "pt"}
    return jp_by_id, pt_by_id, pt_by_slug


def meta_title(meta: str) -> str:
    for line in (meta or "").splitlines():
        if line.startswith("Title:"):
            return clean_title(line.split(":", 1)[1])
    return ""


def first_body_title_line(content: str) -> str:
    for para in re.split(r"\n\s*\n", content or ""):
        line = para.strip().splitlines()[0].strip() if para.strip() else ""
        if not line:
            continue
        if PERIODICAL_FICHA_RE.match(line) or SERIES_FICHA_RE.match(line):
            continue
        if line.startswith("**") and line.endswith("**"):
            line = line.strip("*").strip()
        if len(line) <= 120 and not line.startswith("（"):
            return clean_title(line)
    return ""


def first_jp_body_line(content: str) -> str:
    for line in (content or "").splitlines():
        s = line.strip()
        if s:
            return s
    return ""


def normalize_title(text: str) -> str:
    return re.sub(r"\s+", " ", clean_title(text or "")).casefold()


def staging_title(jp_entry: dict, pt_entry: dict | None) -> str:
    if not jp_entry.get("clean_path") and not (pt_entry or {}).get("clean_path"):
        return ""
    try:
        path = resolve_pt_path(jp_entry, pt_entry)
        if path and path.is_file():
            return parse_pt_title_from_raw(read_file_text(path))
    except (OSError, KeyError):
        pass
    return ""


def source_pt_title(jp_entry: dict, pt_entry: dict | None) -> str:
    if not pt_entry:
        return ""
    clean = pt_entry.get("clean_path") or jp_entry.get("clean_path") or ""
    if not clean:
        return clean_title(pt_entry.get("title") or "")
    try:
        path = Path("/var/www/goshinsho") / clean
        if not path.is_file():
            path = PROJECT_ROOT / clean
        if path.is_file():
            return parse_pt_title_from_raw(read_file_text(path))
    except OSError:
        pass
    return clean_title(pt_entry.get("title") or "")


def reference_pt_title(entry_id: str, jp_entry: dict, pt_entry: dict | None) -> tuple[str, str]:
    if entry_id in TITLE_PT_OVERRIDES:
        return TITLE_PT_OVERRIDES[entry_id], "override"
    src = source_pt_title(jp_entry, pt_entry)
    cat = clean_title(jp_entry.get("paired_title_pt") or "")
    st = staging_title(jp_entry, pt_entry)
    if src and cat and normalize_title(src) == normalize_title(cat):
        return src, "catalog+source"
    if src:
        return src, "source_pt"
    if cat:
        return cat, "catalog"
    if st:
        return st, "staging"
    return "", "none"


TOPIC_JP_HEALTH = re.compile(r"健康|病無|病気")
TOPIC_JP_ATHEISM = re.compile(r"無信仰|無神|不信")
TOPIC_PT_ATHEISM = re.compile(r"ateísmo|ateismo|descrença|incredul", re.I)
TOPIC_PT_HEALTH = re.compile(r"saúde|saude|doença|doenca|terapia|medicina", re.I)
TOPIC_PT_FAITH = re.compile(r"ateísmo|ateismo|descrença|incredul|sem fé|sem fe|fé|fe", re.I)


def suspected_topic_mismatch(title_jp: str, title_pt: str) -> bool:
    jp, pt = title_jp or "", title_pt or ""
    if TOPIC_JP_HEALTH.search(jp) and TOPIC_PT_ATHEISM.search(pt) and not TOPIC_PT_HEALTH.search(pt):
        return True
    if TOPIC_JP_ATHEISM.search(jp) and TOPIC_PT_ATHEISM.search(pt):
        return False
    if TOPIC_JP_ATHEISM.search(jp) and not TOPIC_PT_FAITH.search(pt):
        return True
    if TOPIC_JP_ATHEISM.search(jp) and TOPIC_PT_HEALTH.search(pt) and not TOPIC_PT_FAITH.search(pt):
        return True
    return False


def classify_row(row: dict) -> tuple[list[str], str]:
    flags: list[str] = []

    if not row["title_jp"]:
        flags.append("missing_title_jp")
    if not row["title_pt_work"]:
        flags.append("missing_title_pt")

    pt = row["title_pt_work"]
    if pt and CJK_RE.search(pt):
        flags.append("title_pt_cjk")
    if pt and len(pt) > 120:
        flags.append("title_pt_too_long")
    if pt and TITLE_GLUE_RE.search(pt):
        flags.append("title_glued_body")

    if row["title_jp"] and JP_EDITORIAL_TITLE_RE.search(row["title_jp"]):
        flags.append("jp_title_editorial")

    if row["title_pt_meta"] and row["title_pt_work"]:
        if normalize_title(row["title_pt_meta"]) != normalize_title(row["title_pt_work"]):
            flags.append("work_meta_mismatch")
    if row["title_pt_field"] and row["title_pt_work"]:
        if normalize_title(row["title_pt_field"]) != normalize_title(row["title_pt_work"]):
            flags.append("work_field_mismatch")
    if row["title_pt_body"] and row["title_pt_work"]:
        if normalize_title(row["title_pt_body"]) != normalize_title(row["title_pt_work"]):
            flags.append("work_body_mismatch")

    if row["title_pt_catalog"] and row["title_pt_work"]:
        if normalize_title(row["title_pt_catalog"]) != normalize_title(row["title_pt_work"]):
            flags.append("catalog_work_mismatch")

    if row["title_pt_staging"] and row["title_pt_work"]:
        if normalize_title(row["title_pt_staging"]) != normalize_title(row["title_pt_work"]):
            flags.append("staging_work_diff")

    if row["title_pt_source"] and row["title_pt_catalog"]:
        if normalize_title(row["title_pt_source"]) != normalize_title(row["title_pt_catalog"]):
            flags.append("catalog_source_diff")

    # Work diverge do catálogo e do source quando ambos concordam entre si.
    if row["title_pt_reference"] and row["title_pt_work"]:
        if (
            row["reference_source"] in {"catalog+source", "override"}
            and normalize_title(row["title_pt_reference"]) != normalize_title(row["title_pt_work"])
        ):
            flags.append("canonical_work_mismatch")

    if (
        row.get("has_override")
        and row["title_pt_work"]
        and normalize_title(row["title_pt_work"]) == normalize_title(row["title_pt_reference"])
        and "catalog_work_mismatch" in flags
    ):
        flags.remove("catalog_work_mismatch")
        flags.append("catalog_outdated")

    if row["title_pt_source"] and row["title_pt_work"]:
        if normalize_title(row["title_pt_source"]) != normalize_title(row["title_pt_work"]):
            flags.append("source_work_diff")

    if pt in GENERIC_PT_TITLES:
        flags.append("generic_title")

    if row.get("duplicate_title_cluster"):
        flags.append("duplicate_title_cluster")

    if suspected_topic_mismatch(row["title_jp"], row["title_pt_work"]):
        flags.append("suspected_topic_mismatch")
    if suspected_topic_mismatch(row["title_jp"], row["title_pt_catalog"]):
        flags.append("suspected_catalog_topic_mismatch")

    if row.get("jp_first_line") and row["title_jp"]:
        if normalize_title(row["jp_first_line"]) != normalize_title(row["title_jp"]):
            flags.append("jp_title_not_first_line")

    severity = "ok"
    critical = {
        "title_pt_cjk",
        "title_glued_body",
        "title_pt_too_long",
        "missing_title_pt",
        "canonical_work_mismatch",
    }
    warning = {
        "catalog_work_mismatch",
        "work_meta_mismatch",
        "work_field_mismatch",
        "work_body_mismatch",
        "duplicate_title_cluster",
        "generic_title",
        "suspected_topic_mismatch",
    }
    info = {
        "source_work_diff",
        "staging_work_diff",
        "catalog_source_diff",
        "catalog_work_mismatch",
        "catalog_outdated",
        "jp_title_not_first_line",
        "jp_title_editorial",
        "suspected_catalog_topic_mismatch",
    }
    if any(f in critical for f in flags):
        severity = "critical"
    elif any(f in warning for f in flags):
        severity = "warning"
    elif any(f in info for f in flags):
        severity = "info"

    return flags, severity


def collect_rows() -> list[dict]:
    jp_by_id, pt_by_id, pt_by_slug = load_catalog()
    rows: list[dict] = []

    for jp_file in sorted((WORK_ROOT / "jp").glob("*.txt")):
        pt_file = WORK_ROOT / "pt" / jp_file.name
        _, jp_blocks = split_file(jp_file.read_text(encoding="utf-8"))
        _, pt_blocks = split_file(pt_file.read_text(encoding="utf-8"))
        for jb, pb in zip(jp_blocks, pt_blocks):
            ja, pa = parse_article(jb), parse_article(pb)
            entry_id = ja.fields.get("entry_id", "")
            jp_entry = jp_by_id.get(entry_id, {})
            paired_id = ja.fields.get("paired_id") or jp_entry.get("paired_id") or ""
            pt_entry = pt_by_id.get(paired_id) or pt_by_slug.get(slug_key(jp_entry.get("clean_path", "")))

            jp_raw = ja.meta + "\n\n" + ja.content if ja.meta else ja.content
            jp_meta = parse_jp_source_metadata(jp_raw)
            title_jp = clean_title(ja.fields.get("title_jp") or jp_meta.get("Title") or jp_entry.get("title") or "")
            title_pt_work = clean_title(pick_pt_title(jp_meta, pa.content, ja.fields))
            title_pt_field = clean_title(pa.fields.get("title_pt", ""))
            title_pt_meta = meta_title(pa.meta)
            title_pt_body = first_body_title_line(pa.content)
            title_pt_catalog = clean_title(jp_entry.get("paired_title_pt") or ja.fields.get("title_pt") or "")
            title_pt_staging = staging_title(jp_entry, pt_entry)
            title_pt_source = source_pt_title(jp_entry, pt_entry)
            title_pt_reference, reference_source = reference_pt_title(entry_id, jp_entry, pt_entry)

            rows.append(
                {
                    "entry_id": entry_id,
                    "paired_id": paired_id,
                    "source_file": ja.fields.get("source_file", jp_entry.get("source_category", "")),
                    "sort_date": ja.fields.get("sort_date", jp_entry.get("source_date", "")),
                    "title_jp": title_jp,
                    "jp_first_line": first_jp_body_line(ja.content),
                    "title_pt_work": title_pt_work,
                    "title_pt_field": title_pt_field,
                    "title_pt_meta": title_pt_meta,
                    "title_pt_body": title_pt_body,
                    "title_pt_catalog": title_pt_catalog,
                    "title_pt_staging": title_pt_staging,
                    "title_pt_source": title_pt_source,
                    "title_pt_reference": title_pt_reference,
                    "reference_source": reference_source,
                    "has_override": entry_id in TITLE_PT_OVERRIDES,
                    "duplicate_title_cluster": False,
                    "duplicate_cluster_size": 0,
                    "flags": [],
                    "severity": "ok",
                }
            )

    by_pt: dict[str, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        key = normalize_title(row["title_pt_work"])
        if key:
            by_pt[key].append(i)

    for key, indices in by_pt.items():
        if len(indices) < 3:
            continue
        jp_titles = {normalize_title(rows[i]["title_jp"]) for i in indices}
        if len(jp_titles) < 2:
            continue
        for i in indices:
            rows[i]["duplicate_title_cluster"] = True
            rows[i]["duplicate_cluster_size"] = len(indices)

    for row in rows:
        row["flags"], row["severity"] = classify_row(row)
        row["ok"] = row["severity"] == "ok"

    return rows


def summarize(rows: list[dict]) -> dict:
    flag_counts: Counter[str] = Counter()
    for row in rows:
        for flag in row["flags"]:
            flag_counts[flag] += 1

    dup_titles = Counter(
        row["title_pt_work"]
        for row in rows
        if row["duplicate_title_cluster"]
    )

    return {
        "total_articles": len(rows),
        "ok": sum(1 for r in rows if r["ok"]),
        "info": sum(1 for r in rows if r["severity"] == "info"),
        "warning": sum(1 for r in rows if r["severity"] == "warning"),
        "critical": sum(1 for r in rows if r["severity"] == "critical"),
        "flagged": sum(1 for r in rows if r["flags"]),
        "priority_flagged": sum(1 for r in rows if r["severity"] in {"critical", "warning"}),
        "by_flag": dict(sorted(flag_counts.items(), key=lambda x: (-x[1], x[0]))),
        "top_duplicate_titles": dup_titles.most_common(15),
        "entries_path": str(entries_path()),
    }


def render_html(rows: list[dict], summary: dict, timestamp: str) -> str:
    flagged = [r for r in rows if r["severity"] in {"critical", "warning"}]
    flagged.sort(key=lambda r: ({"critical": 0, "warning": 1, "info": 2, "ok": 3}[r["severity"]], r["entry_id"]))

    def row_html(r: dict) -> str:
        cls = r["severity"]
        flags = ", ".join(r["flags"]) or "—"
        return (
            f"<tr class='{cls}'><td>{escape(r['entry_id'])}</td>"
            f"<td>{escape(r['source_file'])}</td>"
            f"<td lang='ja'>{escape(r['title_jp'][:80])}</td>"
            f"<td>{escape(r['title_pt_work'][:90])}</td>"
            f"<td>{escape(r['title_pt_catalog'][:90])}</td>"
            f"<td>{escape(r['title_pt_reference'][:90])}</td>"
            f"<td>{escape(flags)}</td></tr>"
        )

    dup_lines = "".join(
        f"<li><strong>{escape(title)}</strong> — {count} artigos</li>"
        for title, count in summary["top_duplicate_titles"]
    )

    flag_lines = "".join(
        f"<li><code>{escape(flag)}</code>: {count}</li>"
        for flag, count in summary["by_flag"].items()
    )

    return f"""<!DOCTYPE html>
<html lang="pt">
<head>
  <meta charset="utf-8">
  <title>Auditoria de títulos — {summary['total_articles']} artigos</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 1400px; margin: 2rem auto; padding: 0 1rem; line-height: 1.45; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
    th, td {{ border: 1px solid #ccc; padding: 6px 8px; vertical-align: top; }}
    th {{ background: #f3f4f6; position: sticky; top: 0; }}
    tr.critical {{ background: #fee2e2; }}
    tr.warning {{ background: #fef9c3; }}
    tr.info {{ background: #eff6ff; }}
    .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: .75rem; margin: 1rem 0; }}
    .stat {{ border: 1px solid #ddd; border-radius: 8px; padding: .75rem 1rem; background: #fafafa; }}
    .stat strong {{ display: block; font-size: 1.4rem; }}
    code {{ background: #f3f4f6; padding: 1px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>Auditoria de títulos JP/PT</h1>
  <p>Gerado: {escape(timestamp)} · Catálogo: <code>{escape(summary['entries_path'])}</code></p>
  <div class="stats">
    <div class="stat"><strong>{summary['total_articles']}</strong> artigos</div>
    <div class="stat"><strong>{summary['ok']}</strong> OK</div>
    <div class="stat"><strong>{summary['critical']}</strong> críticos</div>
    <div class="stat"><strong>{summary['warning']}</strong> avisos</div>
    <div class="stat"><strong>{summary['info']}</strong> info</div>
    <div class="stat"><strong>{summary['flagged']}</strong> com flags</div>
  </div>
  <h2>Flags (contagem)</h2>
  <ul>{flag_lines or '<li>Nenhuma</li>'}</ul>
  <h2>Títulos PT repetidos (≥3 artigos, JP distintos)</h2>
  <ul>{dup_lines or '<li>Nenhum cluster relevante</li>'}</ul>
  <h2>Artigos com issues prioritários ({len(flagged)})</h2>
  <table>
    <tr>
      <th>ID</th><th>Fonte</th><th>Título JP</th><th>Título PT (work)</th>
      <th>Catálogo</th><th>Referência</th><th>Flags</th>
    </tr>
    {''.join(row_html(r) for r in flagged)}
  </table>
</body>
</html>"""


def main() -> int:
    rows = collect_rows()
    summary = summarize(rows)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    flagged = [r for r in rows if r["flags"]]
    out = {
        "timestamp": timestamp,
        **summary,
        "articles": rows,
        "flagged_only": flagged,
    }

    json_path = WORK_ROOT / "TITULOS_AUDIT_FULL.json"
    html_path = WORK_ROOT / "TITULOS_AUDIT_FULL.html"
    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_html(rows, summary, timestamp), encoding="utf-8")

    deploy = Path("/var/www/goshinsho/reports/periodicos_trabalho")
    if deploy.is_dir():
        (deploy / "TITULOS_AUDIT_FULL.json").write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
        (deploy / "TITULOS_AUDIT_FULL.html").write_text(html_path.read_text(encoding="utf-8"), encoding="utf-8")

    public = {k: v for k, v in out.items() if k not in ("articles", "flagged_only")}
    print(json.dumps(public, ensure_ascii=False, indent=2))
    print(f"json={json_path}")
    print(f"html={html_path}")
    return 1 if summary["critical"] or summary["warning"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
