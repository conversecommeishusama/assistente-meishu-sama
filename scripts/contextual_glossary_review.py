#!/usr/bin/env python3
"""Build contextual review reports for glossary audit findings.

This script does not modify source texts. It turns the glossary audit into a
reviewable queue: each finding includes the paired permanent JP/PT files,
snippets around the Japanese term, snippets around the expected Portuguese form
when present, and optional candidate Portuguese variants for known patterns.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from audit_translation_glossary import GLOSSARY_PATH, PROJECT_ROOT, split_glossary_value


DEFAULT_AUDIT = PROJECT_ROOT / "reports" / "translation_review" / "glossary_audit_high_confidence.jsonl"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review" / "contextual_glossary"


CANDIDATE_PATTERNS: dict[str, tuple[str, ...]] = {
    "栄光": (r"\bGlória\b", r"\bEiko\b"),
    "体的": (
        r"\bfisicamente\b",
        r"\bcorporalmente\b",
        r"\b(?:do|no|sob o) ponto de vista físico\b",
        r"\b(?:sob o|no|do) aspecto físico\b",
    ),
    "薬毒": (
        r"\bvenenos? (?:dos?|de) (?:medicamentos|remédios)\b",
        r"\btoxinas? (?:dos?|de) (?:medicamentos|remédios)\b",
        r"\btoxicidade dos medicamentos\b",
        r"\bintoxicaç(?:ão|ões) medicamentosas?\b",
    ),
    "天国": (r"\bReino dos Céus\b", r"\bReino do Céu\b", r"\bCéu\b"),
    "神霊": (
        r"\bespíritos? divinos?\b",
        r"\bespíritos? dos deuses\b",
        r"\bespíritos? de Deus\b",
        r"\bentidades? espirituais\b",
    ),
    "曇り": (
        r"\bnuvem espiritual\b",
        r"\bnuvens espirituais\b",
        r"\bturvaç(?:ão|ões)(?: espiritual(?:is)?)?\b",
        r"\bnebulosidade(?: espiritual)?\b",
        r"\bnubl\w+\b",
        r"\bobscurec\w+\b",
    ),
    "邪神": (
        r"\bdeuses maus\b",
        r"\bdeus mau\b",
        r"\bespíritos? malignos?\b",
        r"\bmaus espíritos\b",
        r"\bdivindades? maléficas?\b",
    ),
    "地上天国": (
        r"\bParaíso Terrestre\b",
        r"\bCéu na Terra\b",
        r"\bTerra do Céu na Terra\b",
        r"\bReino dos Céus na Terra\b",
    ),
    "自然農法": (
        r"\bAgricultura Natural\b",
        r"\bagricultura natural\b",
        r"\bmétodo de agricultura natural\b",
        r"\bmétodo agrícola natural\b",
    ),
    "注射": (
        r"\binjeç(?:ão|ões)\b",
        r"\bvacina(?:ção|ções)?\b",
        r"\bvacinas?\b",
        r"\baplicações? intravenosas?\b",
    ),
    "浄霊": (r"\bJorei\b", r"\bJohrei\b", r"\bpurificação espiritual\b"),
    "経綸": (
        r"\badministração divina\b",
        r"\bprovidência divina\b",
        r"\bplano de Deus\b",
        r"\bPlano Divino\b",
    ),
}


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def snippets(text: str, pattern: re.Pattern[str], radius: int = 150, limit: int = 5) -> list[dict[str, str]]:
    results = []
    for match in pattern.finditer(text):
        start = max(0, match.start() - radius)
        end = min(len(text), match.end() + radius)
        results.append({"match": match.group(0), "snippet": compact(text[start:end])})
        if len(results) >= limit:
            break
    return results


def compile_literal_pattern(values: list[str]) -> re.Pattern[str] | None:
    escaped = [re.escape(value) for value in values if value]
    if not escaped:
        return None
    return re.compile("|".join(escaped), flags=re.IGNORECASE)


def read_text(path_value: str) -> str:
    path = PROJECT_ROOT / path_value
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def classify(expected_hits: list[dict], candidate_hits: list[dict]) -> str:
    if expected_hits:
        return "expected_present_after_previous_fix"
    if candidate_hits:
        return "candidate_variant_found"
    return "needs_context_review"


def load_audit_rows(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate contextual glossary review reports.")
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-examples-per-term", type=int, default=20)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    glossary = json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))
    expected_by_term = {term: split_glossary_value(value) for term, value in glossary.items()}
    rows = load_audit_rows(args.audit)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    detail_path = args.output_dir / "all_terms_context_review.jsonl"
    summary_path = args.output_dir / "all_terms_context_summary.md"

    term_counts = Counter()
    class_counts = Counter()
    candidate_counts = Counter()
    examples_by_term: dict[str, list[dict]] = defaultdict(list)

    with detail_path.open("w", encoding="utf-8") as detail_file:
        for row in rows:
            term = row.get("japanese_term", "")
            pt_path = row.get("pt_permanent_path") or ""
            jp_path = row.get("jp_permanent_path") or ""
            if not term or not pt_path or not jp_path:
                continue

            pt_text = read_text(pt_path)
            jp_text = read_text(jp_path)
            expected_values = row.get("expected_pt") or expected_by_term.get(term, [])

            jp_pattern = re.compile(re.escape(term))
            expected_pattern = compile_literal_pattern(expected_values)
            candidate_pattern = (
                re.compile("|".join(CANDIDATE_PATTERNS[term]), flags=re.IGNORECASE)
                if term in CANDIDATE_PATTERNS
                else None
            )

            expected_hits = snippets(pt_text, expected_pattern) if expected_pattern else []
            candidate_hits = snippets(pt_text, candidate_pattern) if candidate_pattern else []
            jp_hits = snippets(jp_text, jp_pattern, limit=3)
            classification = classify(expected_hits, candidate_hits)

            review_row = {
                "classification": classification,
                "entry_type": row.get("entry_type"),
                "expected_pt": expected_values,
                "japanese_term": term,
                "jp_path": jp_path,
                "pt_path": pt_path,
                "source_category": row.get("source_category"),
                "source_date": row.get("source_date"),
                "title_pt": row.get("title_pt"),
                "jp_hits": jp_hits,
                "expected_hits": expected_hits,
                "candidate_hits": candidate_hits,
            }
            detail_file.write(json.dumps(review_row, ensure_ascii=False, sort_keys=True) + "\n")

            term_counts[term] += 1
            class_counts[classification] += 1
            if candidate_hits:
                candidate_counts[term] += 1
            if len(examples_by_term[term]) < args.max_examples_per_term:
                examples_by_term[term].append(review_row)

    with summary_path.open("w", encoding="utf-8") as summary_file:
        summary_file.write("# Contextual Glossary Review\n\n")
        summary_file.write(f"- Achados revisados: {sum(term_counts.values())}\n")
        summary_file.write(f"- Termos distintos: {len(term_counts)}\n")
        for key, value in class_counts.most_common():
            summary_file.write(f"- {key}: {value}\n")

        summary_file.write("\n## Termos com mais achados\n\n")
        for term, count in term_counts.most_common(40):
            expected = " / ".join(expected_by_term.get(term, []))
            candidate_count = candidate_counts.get(term, 0)
            summary_file.write(f"- `{term}`: {count} achados; candidatos detectados em {candidate_count}; esperado: {expected}\n")

        summary_file.write("\n## Como usar este relatório\n\n")
        summary_file.write("- `candidate_variant_found`: há uma forma portuguesa provável para revisão e possível regra.\n")
        summary_file.write("- `needs_context_review`: não foi detectada variante conhecida; precisa inspecionar trechos e criar regra específica.\n")
        summary_file.write("- `expected_present_after_previous_fix`: o texto permanente já contém a forma esperada; tende a desaparecer após nova auditoria.\n")

    print(f"findings={sum(term_counts.values())} terms={len(term_counts)}")
    print("classes=" + json.dumps(dict(class_counts), ensure_ascii=False, sort_keys=True))
    print(f"jsonl={detail_path}")
    print(f"summary={summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
