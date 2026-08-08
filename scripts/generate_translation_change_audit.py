#!/usr/bin/env python3
"""Generate before/after audit report for PT translation changes."""

from __future__ import annotations

import argparse
import difflib
import json
import re
import tarfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review"


@dataclass(frozen=True)
class PassSpec:
    name: str
    label: str
    before_tar: Path
    after_tar: Path | None  # None = read from disk


PASSES: tuple[PassSpec, ...] = (
    PassSpec(
        name="manual_review_paragraph_fixes",
        label="Revisão manual paragraph-gated (glossário)",
        before_tar=DEFAULT_OUTPUT_DIR / "manual_review_paragraph_fixes_20260619T083025Z_before.tar.gz",
        after_tar=None,
    ),
    PassSpec(
        name="portuguese_grammar_pass",
        label="Revisão gramatical",
        before_tar=DEFAULT_OUTPUT_DIR / "portuguese_grammar_pass_20260619T102004Z_before.tar.gz",
        after_tar=DEFAULT_OUTPUT_DIR / "portuguese_fluency_pass_20260619T102026Z_before.tar.gz",
    ),
    PassSpec(
        name="portuguese_fluency_pass",
        label="Revisão de fluidez",
        before_tar=DEFAULT_OUTPUT_DIR / "portuguese_fluency_pass_20260619T102026Z_before.tar.gz",
        after_tar=None,
    ),
)


def load_tar_texts(tar_path: Path) -> dict[str, str]:
    texts: dict[str, str] = {}
    with tarfile.open(tar_path, "r:gz") as tar:
        for member in tar.getmembers():
            if not member.isfile() or not member.name.endswith(".txt"):
                continue
            data = tar.extractfile(member)
            if data is None:
                continue
            texts[member.name] = data.read().decode("utf-8")
    return texts


def load_current_texts(paths: set[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in paths:
        path = PROJECT_ROOT / rel
        if path.exists():
            out[rel] = path.read_text(encoding="utf-8")
    return out


def sentence_spans(text: str) -> list[tuple[int, int, str]]:
    """Split into sentence-like spans for readable diffs."""
    spans: list[tuple[int, int, str]] = []
    for match in re.finditer(r"[^.!?\n—]+(?:[.!?…]+|—+|$)", text, flags=re.MULTILINE):
        chunk = match.group(0).strip()
        if chunk:
            spans.append((match.start(), match.end(), chunk))
    if not spans and text.strip():
        spans.append((0, len(text), text.strip()))
    return spans


def aligned_change_blocks(before: str, after: str) -> list[dict]:
    """Return changed sentence pairs with local context."""
    before_lines = before.splitlines()
    after_lines = after.splitlines()
    blocks: list[dict] = []

    matcher = difflib.SequenceMatcher(None, before_lines, after_lines)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        old_chunk = "\n".join(before_lines[i1:i2]).strip()
        new_chunk = "\n".join(after_lines[j1:j2]).strip()
        if not old_chunk and not new_chunk:
            continue
        blocks.append({
            "change_type": tag,
            "line_before_start": i1 + 1,
            "line_before_end": i2,
            "line_after_start": j1 + 1,
            "line_after_end": j2,
            "original": old_chunk,
            "revised": new_chunk,
        })
    return blocks


def earliest_baseline() -> dict[str, tuple[str, str]]:
    """Map pt_path -> (baseline_text, baseline_label). Earliest backup wins."""
    layers = [
        ("Revisão manual (glossário)", DEFAULT_OUTPUT_DIR / "manual_review_paragraph_fixes_20260619T083025Z_before.tar.gz"),
        ("Revisão gramatical", DEFAULT_OUTPUT_DIR / "portuguese_grammar_pass_20260619T102004Z_before.tar.gz"),
        ("Revisão de fluidez", DEFAULT_OUTPUT_DIR / "portuguese_fluency_pass_20260619T102026Z_before.tar.gz"),
    ]
    baseline: dict[str, tuple[str, str]] = {}
    for label, tar_path in layers:
        if not tar_path.exists():
            continue
        for rel, text in load_tar_texts(tar_path).items():
            if rel not in baseline:
                baseline[rel] = (text, label)
    return baseline


def compare_combined() -> list[dict]:
    baseline = earliest_baseline()
    current = load_current_texts(set(baseline))
    rows: list[dict] = []
    for rel in sorted(baseline):
        old, source = baseline[rel]
        new = current.get(rel)
        if new is None or old == new:
            continue
        blocks = aligned_change_blocks(old, new)
        if not blocks:
            continue
        rows.append({
            "pass": "combined_baseline_to_current",
            "pass_label": f"Baseline ({source}) → atual",
            "baseline_source": source,
            "pt_path": rel,
            "change_count": len(blocks),
            "blocks": blocks,
        })
    return rows


def compare_pass(spec: PassSpec) -> list[dict]:
    before_map = load_tar_texts(spec.before_tar)
    if spec.after_tar:
        after_map = load_tar_texts(spec.after_tar)
    else:
        after_map = load_current_texts(set(before_map))

    rows: list[dict] = []
    for rel in sorted(before_map):
        old = before_map[rel]
        if rel not in after_map:
            continue
        new = after_map[rel]
        if old == new:
            continue
        blocks = aligned_change_blocks(old, new)
        if not blocks:
            continue
        rows.append({
            "pass": spec.name,
            "pass_label": spec.label,
            "pt_path": rel,
            "change_count": len(blocks),
            "blocks": blocks,
        })
    return rows


def write_markdown(rows: list[dict], path: Path, *, title: str) -> None:
    lines = [
        f"# {title}",
        "",
        f"Gerado em: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        f"Total de ficheiros alterados: **{len(rows)}**",
        f"Total de blocos de alteração: **{sum(r['change_count'] for r in rows)}**",
        "",
        "---",
        "",
    ]
    current_pass = None
    for row in rows:
        if row["pass"] != current_pass:
            current_pass = row["pass"]
            lines.extend([f"## {row['pass_label']}", ""])
        lines.append(f"### `{row['pt_path']}` ({row['change_count']} alterações)")
        lines.append("")
        for idx, block in enumerate(row["blocks"], 1):
            lines.append(f"#### Alteração {idx} (linhas {block['line_before_start']}–{block['line_before_end']} → {block['line_after_start']}–{block['line_after_end']})")
            lines.append("")
            lines.append("**Original:**")
            lines.append("")
            lines.append("```")
            lines.append(block["original"])
            lines.append("```")
            lines.append("")
            lines.append("**Revisado:**")
            lines.append("")
            lines.append("```")
            lines.append(block["revised"])
            lines.append("")
        lines.append("---")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate PT translation change audit.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    all_rows: list[dict] = []
    summaries: list[dict] = []
    for spec in PASSES:
        if not spec.before_tar.exists():
            print(f"skip missing backup: {spec.before_tar}")
            continue
        if spec.after_tar and not spec.after_tar.exists():
            print(f"skip missing after tar: {spec.after_tar}")
            continue
        rows = compare_pass(spec)
        all_rows.extend(rows)
        summaries.append({
            "pass": spec.name,
            "label": spec.label,
            "files_changed": len(rows),
            "blocks": sum(r["change_count"] for r in rows),
            "before_backup": str(spec.before_tar),
            "after_source": str(spec.after_tar or "textos_portugues/ (atual)"),
        })

    combined_rows = compare_combined()
    if combined_rows:
        all_rows.extend(combined_rows)
        summaries.append({
            "pass": "combined_baseline_to_current",
            "label": "Consolidado (baseline mais antigo → atual)",
            "files_changed": len(combined_rows),
            "blocks": sum(r["change_count"] for r in combined_rows),
            "before_backup": "manual → grammar → fluency (primeiro disponível por ficheiro)",
            "after_source": "textos_portugues/ (atual)",
        })

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    jsonl_path = out_dir / "translation_change_audit.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for row in all_rows:
            if row["pass"] == "combined_baseline_to_current":
                continue
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    combined_jsonl_path = out_dir / "translation_change_audit_combined.jsonl"
    with combined_jsonl_path.open("w", encoding="utf-8") as f:
        for row in combined_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    md_path = out_dir / "translation_change_audit.md"
    per_pass_rows = [r for r in all_rows if r["pass"] != "combined_baseline_to_current"]
    write_markdown(per_pass_rows, md_path, title="Auditoria de alterações por passagem — original vs revisado")

    combined_md_path = out_dir / "translation_change_audit_combined.md"
    write_markdown(combined_rows, combined_md_path, title="Auditoria consolidada — baseline original vs texto atual")

    summary_path = out_dir / "translation_change_audit_summary.md"
    summary_lines = [
        "# Resumo da auditoria de alterações",
        "",
        f"Gerado em: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "",
        "| Passagem | Ficheiros | Blocos | Backup «antes» | Fonte «depois» |",
        "|----------|----------:|-------:|------------------|----------------|",
    ]
    for s in summaries:
        summary_lines.append(
            f"| {s['label']} | {s['files_changed']} | {s['blocks']} | `{Path(s['before_backup']).name}` | `{Path(s['after_source']).name if s['after_source'].endswith('.tar.gz') else s['after_source']}` |"
        )
    total_files = len({r["pt_path"] for r in all_rows})
    total_blocks = sum(r["change_count"] for r in all_rows)
    summary_lines.extend([
        "",
        f"**Total único:** {total_files} ficheiros, {total_blocks} blocos de comparação.",
        "",
        "Relatórios completos:",
        f"- `{jsonl_path.relative_to(PROJECT_ROOT)}` — JSONL por passagem",
        f"- `{combined_jsonl_path.relative_to(PROJECT_ROOT)}` — JSONL consolidado (baseline → atual)",
        f"- `{md_path.relative_to(PROJECT_ROOT)}` — comparação por passagem",
        f"- `{combined_md_path.relative_to(PROJECT_ROOT)}` — comparação consolidada",
        "",
        "Nota: cada passagem compara o backup imediatamente anterior ao respectivo `--apply`.",
    ])
    summary_path.write_text("\n".join(summary_lines), encoding="utf-8")

    print(json.dumps({
        "summaries": summaries,
        "total_files_unique": total_files,
        "total_blocks": total_blocks,
        "jsonl": str(jsonl_path),
        "combined_jsonl": str(combined_jsonl_path),
        "markdown": str(md_path),
        "combined_markdown": str(combined_md_path),
        "summary": str(summary_path),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
