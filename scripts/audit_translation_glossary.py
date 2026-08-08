#!/usr/bin/env python3
"""Audit JP/PT publication-source pairs against the mandatory glossary.

This script is intentionally conservative: it does not rewrite translations.
It reports cases where the Japanese source contains a glossary term but the
paired Portuguese translation does not contain an expected Portuguese form.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUBLICATION_ENTRIES_PATH = PROJECT_ROOT / "data" / "publication_sources" / "entries.jsonl"
CLEAN_CORPUS_ENTRIES_PATH = PROJECT_ROOT / "data" / "clean_corpus" / "entries.jsonl"
GLOSSARY_PATH = PROJECT_ROOT / "glossario.json"
GLOSSARY_TRADUCAO_PATH = PROJECT_ROOT / "glossario_traducao.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review"


def load_translation_glossary() -> dict[str, object]:
    """Glossário canónico para tradução em massa (sem clusters de busca)."""
    path = GLOSSARY_TRADUCAO_PATH if GLOSSARY_TRADUCAO_PATH.exists() else GLOSSARY_PATH
    return json.loads(path.read_text(encoding="utf-8"))

CONNECTOR_PATTERN = re.compile(r"\s+(?:ou|e|or)\s+", flags=re.IGNORECASE)
ANNOTATION_PATTERN = re.compile(
    r"\b(?:na primeira ocorrência|na primeira aparição|depois apenas|após somente|ajustado conforme contexto)\b.*",
    flags=re.IGNORECASE,
)
QUOTE_CHARS = "\"'“”‘’"
LOW_SIGNAL_TERMS = {
    "自然",
    "説明",
    "社会",
    "新聞",
    "効果",
    "人類",
    "理屈",
    "学者",
    "文化",
    "頭脳",
    "科学",
    "幸福",
    "心配",
    "動物",
    "発展",
    "国家",
    "結核",
    "入信",
    "一生懸命",
    "奇蹟",
    "政治",
    "教育",
    "不安",
    "戦争",
    "仏教",
}


@dataclass(frozen=True)
class EntryPair:
    key: tuple[str, str, str]
    pt: dict
    jp: dict


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "").casefold()
    normalized = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def phrase_present(text: str, phrase: str) -> bool:
    phrase = phrase.strip()
    if not phrase:
        return False
    normalized_text = normalize_text(text)
    normalized_phrase = normalize_text(phrase)
    if not normalized_phrase:
        return False
    return normalized_phrase in normalized_text


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_entries(path: Path) -> list[dict]:
    entries = []
    with path.open(encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def clean_candidate(candidate: str) -> str:
    candidate = candidate.strip().strip(QUOTE_CHARS).strip()
    candidate = ANNOTATION_PATTERN.sub("", candidate).strip()
    candidate = re.sub(r"\s*\[[^\]]+\]\s*", " ", candidate).strip()
    candidate = re.sub(r"\s*\([^)]{30,}\)\s*", " ", candidate).strip()
    return re.sub(r"\s+", " ", candidate).strip().strip(QUOTE_CHARS).strip()


def split_glossary_value(value: object) -> list[str]:
    if isinstance(value, list):
        raw_items = [str(item) for item in value]
    else:
        raw_items = [str(value)]

    candidates: list[str] = []
    for raw in raw_items:
        raw = raw.replace("→", "-")
        raw = raw.split(";", 1)[0]
        raw = raw.split(". Termo", 1)[0]
        pieces = CONNECTOR_PATTERN.split(raw)
        for piece in pieces:
            for slash_piece in piece.split("/"):
                cleaned = clean_candidate(slash_piece)
                if cleaned:
                    candidates.append(cleaned)

    unique = []
    seen = set()
    for candidate in candidates:
        normalized = normalize_text(candidate)
        if len(normalized) < 3 or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(candidate)
    return unique


def entry_body(entry: dict) -> str:
    if "body" in entry:
        return entry.get("body") or ""
    clean_path = entry.get("clean_path")
    if not clean_path:
        return ""
    path = PROJECT_ROOT / clean_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def permanent_source_path(entry: dict) -> Path | None:
    if entry.get("entry_type") == "file":
        original_path = entry.get("original_path")
        return PROJECT_ROOT / original_path if original_path else None

    clean_text = entry_body(entry)
    match = re.search(r"^Original path:\s*(.+)$", clean_text, flags=re.MULTILINE)
    if not match:
        return None
    return PROJECT_ROOT / match.group(1).strip()


def permanent_entry_body(entry: dict) -> str:
    path = permanent_source_path(entry)
    if not path or not path.exists():
        return entry_body(entry)
    return path.read_text(encoding="utf-8")


def key_for_entry(entry: dict) -> tuple[str, str, str, str]:
    if entry.get("entry_type") == "file":
        return (
            "file",
            entry.get("paired_original_filename") or entry.get("original_filename", ""),
            "",
            "",
        )
    return (
        "publication_source",
        entry.get("source_category", ""),
        entry.get("source_date", ""),
        entry.get("display_source_name_pt") or entry.get("paired_title_pt") or entry.get("title", ""),
    )


def key_for_pt(entry: dict) -> tuple[str, str, str, str]:
    if "paired_title_pt" in entry and entry.get("paired_title_pt") == "":
        return (
            entry.get("source_category", ""),
            entry.get("source_date", ""),
            entry.get("title", ""),
        )
    return key_for_entry(entry)


def key_for_jp(entry: dict) -> tuple[str, str, str, str]:
    if "paired_title_pt" in entry and entry.get("paired_title_pt"):
        return (
            entry.get("source_category", ""),
            entry.get("source_date", ""),
            entry.get("paired_title_pt", ""),
        )
    return key_for_entry(entry)


def legacy_key_for_pt(entry: dict) -> tuple[str, str, str]:
    return (
        entry.get("source_category", ""),
        entry.get("source_date", ""),
        entry.get("title", ""),
    )


def legacy_key_for_jp(entry: dict) -> tuple[str, str, str]:
    return (
        entry.get("source_category", ""),
        entry.get("source_date", ""),
        entry.get("paired_title_pt", ""),
    )


def pair_entries(entries: list[dict]) -> tuple[list[EntryPair], list[dict]]:
    pt_by_key = {}
    for entry in entries:
        if entry.get("lang") != "pt":
            continue
        pt_by_key[key_for_pt(entry)] = entry
        pt_by_key[legacy_key_for_pt(entry)] = entry

    publication_pt = sorted(
        [entry for entry in entries if entry.get("lang") == "pt" and entry.get("entry_type") == "publication_source"],
        key=lambda entry: entry.get("entry_id", ""),
    )
    publication_jp = sorted(
        [entry for entry in entries if entry.get("lang") == "jp" and entry.get("entry_type") == "publication_source"],
        key=lambda entry: entry.get("entry_id", ""),
    )
    publication_pt_by_jp_id = {
        jp.get("entry_id"): pt for pt, jp in zip(publication_pt, publication_jp, strict=False)
    }

    pairs: list[EntryPair] = []
    unpaired: list[dict] = []
    for jp in [entry for entry in entries if entry.get("lang") == "jp"]:
        key = key_for_jp(jp)
        legacy_key = legacy_key_for_jp(jp)
        pt = pt_by_key.get(key) or pt_by_key.get(legacy_key)
        if not pt and jp.get("entry_type") == "publication_source":
            pt = publication_pt_by_jp_id.get(jp.get("entry_id"))
        if not pt:
            unpaired.append(jp)
            continue
        pairs.append(EntryPair(key=key, pt=pt, jp=jp))
    return pairs, unpaired


def should_check_term(japanese_term: str, pt_candidates: list[str]) -> bool:
    # Very short single-kanji entries are too broad for safe automatic auditing.
    if len(japanese_term) <= 1:
        return False
    if not pt_candidates:
        return False
    if any(len(normalize_text(candidate)) >= 3 for candidate in pt_candidates):
        return True
    return False


def audit_pair(pair: EntryPair, glossary: dict[str, object], use_permanent_sources: bool = False) -> list[dict]:
    if use_permanent_sources:
        jp_body = permanent_entry_body(pair.jp)
        pt_body = permanent_entry_body(pair.pt)
    else:
        jp_body = entry_body(pair.jp)
        pt_body = entry_body(pair.pt)
    findings = []

    for japanese_term, portuguese_value in glossary.items():
        if japanese_term not in jp_body:
            continue
        candidates = split_glossary_value(portuguese_value)
        if not should_check_term(japanese_term, candidates):
            continue
        if any(phrase_present(pt_body, candidate) for candidate in candidates):
            continue
        findings.append(
            {
                "severity": "missing_glossary_term",
                "japanese_term": japanese_term,
                "expected_pt": candidates,
            }
        )
    return findings


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_markdown_summary(path: Path, rows: list[dict], total_pairs: int, unpaired_count: int) -> None:
    affected_entries = len({row["pt_entry_id"] for row in rows})
    term_counts = Counter(row["japanese_term"] for row in rows)
    source_counts = Counter(row["source_category"] for row in rows)

    lines = [
        "# Translation Glossary Audit",
        "",
        f"- Pares JP/PT analisados: {total_pairs}",
        f"- Registros japoneses sem par PT: {unpaired_count}",
        f"- Achados terminológicos: {len(rows)}",
        f"- Textos portugueses afetados: {affected_entries}",
        "",
        "## Termos Mais Frequentes",
        "",
    ]
    if term_counts:
        for term, count in term_counts.most_common(25):
            lines.append(f"- `{term}`: {count}")
    else:
        lines.append("- Nenhum achado.")

    lines.extend(["", "## Fontes Mais Afetadas", ""])
    if source_counts:
        for source, count in source_counts.most_common(20):
            lines.append(f"- {source}: {count}")
    else:
        lines.append("- Nenhuma fonte afetada.")

    lines.extend(
        [
            "",
            "## Próximo Passo Seguro",
            "",
            "Revisar manualmente os achados de maior frequência antes de aplicar qualquer substituição automática.",
            "Este relatório não prova erro de tradução em todos os casos; ele indica divergência entre o original japonês e a forma obrigatória do glossário.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def high_confidence_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row["japanese_term"] not in LOW_SIGNAL_TERMS]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit JP/PT translations against glossario.json.")
    parser.add_argument(
        "--catalog",
        choices=("clean_corpus", "publication_sources"),
        default="clean_corpus",
        help="Catalog to audit. clean_corpus includes all indexed texts.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Limit number of paired entries audited.")
    parser.add_argument("--source", default="", help="Filter by source_category.")
    parser.add_argument(
        "--permanent-sources",
        action="store_true",
        help="Read original permanent source files instead of generated clean_corpus files.",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    glossary = load_json(GLOSSARY_PATH)
    entries_path = CLEAN_CORPUS_ENTRIES_PATH if args.catalog == "clean_corpus" else PUBLICATION_ENTRIES_PATH
    entries = load_entries(entries_path)
    pairs, unpaired = pair_entries(entries)

    if args.source:
        pairs = [pair for pair in pairs if pair.pt.get("source_category") == args.source]
    if args.limit:
        pairs = pairs[: args.limit]

    rows = []
    for pair in pairs:
        for finding in audit_pair(pair, glossary, use_permanent_sources=args.permanent_sources):
            rows.append(
                {
                    **finding,
                    "pt_entry_id": pair.pt.get("entry_id"),
                    "jp_entry_id": pair.jp.get("entry_id"),
                    "title_pt": pair.pt.get("title"),
                    "title_jp": pair.jp.get("title"),
                    "source_category": pair.pt.get("source_category"),
                    "source_date": pair.pt.get("source_date"),
                    "entry_type": pair.pt.get("entry_type"),
                    "catalog": args.catalog,
                    "source_mode": "permanent" if args.permanent_sources else "generated",
                    "pt_path": pair.pt.get("clean_path"),
                    "jp_path": pair.jp.get("clean_path"),
                    "pt_permanent_path": str(permanent_source_path(pair.pt).relative_to(PROJECT_ROOT))
                    if permanent_source_path(pair.pt)
                    else "",
                    "jp_permanent_path": str(permanent_source_path(pair.jp).relative_to(PROJECT_ROOT))
                    if permanent_source_path(pair.jp)
                    else "",
                }
            )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = args.output_dir / "glossary_audit_findings.jsonl"
    high_confidence_jsonl_path = args.output_dir / "glossary_audit_high_confidence.jsonl"
    summary_path = args.output_dir / "glossary_audit_summary.md"
    high_confidence_summary_path = args.output_dir / "glossary_audit_high_confidence_summary.md"
    filtered_rows = high_confidence_rows(rows)
    write_jsonl(jsonl_path, rows)
    write_jsonl(high_confidence_jsonl_path, filtered_rows)
    write_markdown_summary(summary_path, rows, len(pairs), len(unpaired))
    write_markdown_summary(high_confidence_summary_path, filtered_rows, len(pairs), len(unpaired))

    print(
        f"catalog={args.catalog} source_mode={'permanent' if args.permanent_sources else 'generated'} "
        f"pairs={len(pairs)} unpaired_jp={len(unpaired)} "
        f"findings={len(rows)} high_confidence={len(filtered_rows)}"
    )
    print(f"jsonl={jsonl_path}")
    print(f"high_confidence_jsonl={high_confidence_jsonl_path}")
    print(f"summary={summary_path}")
    print(f"high_confidence_summary={high_confidence_summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
