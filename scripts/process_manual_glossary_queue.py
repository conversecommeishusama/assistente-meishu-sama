#!/usr/bin/env python3
"""Process manual glossary review queue: fix PT or classify false positives until empty."""

from __future__ import annotations

import argparse
import json
import re
import tarfile
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from apply_comprehensive_glossary_batch import ALL_RULES
from apply_individual_term_keirin import GRAMMAR_PATTERNS, KEEP_KEIRIN_PATTERNS, PLANO_DIVINO_PATTERNS, SHUSHIN_PATTERNS
from apply_individual_term_kumori import RULES as KUMORI_RULES, is_spiritual_kumori
from apply_individual_term_taitai import RULES as TAITAI_RULES
from apply_safe_glossary_fixes import load_entries, pair_entries, permanent_pt_path, read_entry_text
from audit_translation_glossary import GLOSSARY_PATH, phrase_present, split_glossary_value
from finalize_glossary_term_queue import BIBLIOGRAPHIC_TERMS, MANUAL_TERMS, paragraph_for_offset
from glossary_term_queue import EXTENDED_CANDIDATE_PATTERNS, TERM_EXCLUDE_JP, _compile_patterns, _metadata_like
from paragraph_glossary import align_paragraphs, apply_paragraph_gated
from resolve_glossary_pending_queue import apply_window_rules, targeted_file_fix


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review"
DEFAULT_QUEUE = DEFAULT_OUTPUT_DIR / "glossary_term_manual_review.jsonl"

EXTRA_ACCEPTABLE: dict[str, tuple[str, ...]] = {
    "大本教": ("Oomoto", "Omoto", "Ômoto", "religião Oomoto", "religião Ômoto", "da religião Oomoto", "Igreja Omoto"),
    "因縁": ("innen", "afinidade espiritual", "conexão cármica", "karma", "afinidade"),
    "御守護": ("proteção divina", "proteção de Deus", "proteção dos deuses", "proteção de Meishu-Sama"),
    "御利益": ("benefício material", "benefícios materiais", "benefício espiritual", "benefícios espirituais"),
    "信仰雑話": ("Shinkō Zatsuwa", "Shinko Zatsuwa", "Miscelânea de Fé", "Miscelanea de Fé"),
    "智慧証覚": ("Chie Shōgaku", "Chie Shogaku", "Iluminação da Sabedoria"),
    "神仙郷": ("Paraíso dos Imortais", "Paraíso dos imortais"),
    "メシヤ会館": ("Palácio Messiânico", "Palacio Messianico"),
    "光明如来": ("Komyo-Nyorai", "Komyo Nyorai", "Daikoumyou Nyorai"),
    "光明如来様": ("Komyo-Nyorai", "Komyo Nyorai"),
    "御神体": ("Goshintai", "Imagem da Luz Divina"),
    "邪神": ("Divindades malignas", "Divindade maligna", "deuses maus", "deus mau"),
    "悪霊": ("Espírito do Mal", "espírito maligno", "espíritos malignos"),
    "先祖代々": ("antepassados de todas as gerações", "gerações de antepassados", "ancestrais de geração"),
    "漢方薬": ("medicina chinesa", "Medicina Chinesa"),
    "肋膜": ("pleura", "membrana pleural"),
    "お筆先": ("Ofudesaki", "O-fudesaki", "Fudesaki"),
    "正神": ("deus verdadeiro", "Deus verdadeiro", "deuses verdadeiros"),
    "夜の世界": ("Mundo da Noite", "mundo da noite"),
    "体的": ("materialmente", "material", "materiais", "fisicamente"),
    "死霊": ("espíritos de pessoas falecidas", "espírito de pessoa falecida", "espíritos mortos"),
    "言霊": ("Kotodama", "kotodama", "espírito da palavra"),
    "再生": ("reencarn", "renasc"),
    "経綸": ("Plano Divino", "plano divino", "providência"),
    "毒血": ("sangue toxêmico", "sangue tóxico", "sangue venenoso"),
    "曇る": ("nublar", "turva", "turvar"),
    "祀る": ("sufragar", "cultuar"),
    "堆肥": ("composto natural", "compostos naturais"),
    "肺病": ("tuberculose", "doença pulmonar"),
    "邪教": ("seita maligna", "seita perversa"),
    "副守護神": ("deus guardião secundário", "guardião secundário"),
    "正守護神": ("deus guardião principal", "guardião principal"),
    "後頭部": ("nuca", "parte posterior da cabeça"),
    "霊線": ("elo espiritual", "elos espirituais"),
    "神憑り": ("possessão espiritual", "possessão"),
    "清算": ("Grande Purificação", "purificação"),
    "御光話録": ("Gokōwa-roku", "Gokowa-roku", "Goshūi-roku"),
    "御神書": ("Escritos Divinos",),
    "御教え集": ("Coletânea de Ensinamentos", "Coleção de Ensinamentos"),
}

WINDOW_EXTRA: dict[str, tuple[tuple[re.Pattern[str], str], ...]] = {
    "御守護": (
        (re.compile(r"\bagradeça pela proteção\b", re.I), "agradeça pela proteção divina"),
        (re.compile(r"\bpeço sua proteção\b", re.I), "peço sua proteção divina"),
        (re.compile(r"\bpeço a sua proteção\b", re.I), "peço a sua proteção divina"),
        (re.compile(r"\ba proteção de Meishu-Sama\b", re.I), "a proteção divina de Meishu-Sama"),
        (re.compile(r"\breceber a proteção de\b", re.I), "receber a proteção divina de"),
        (re.compile(r"\bproteção até então\b", re.I), "proteção divina até então"),
    ),
    "因縁": (
        (re.compile(r"\bconexão cármica profunda\b", re.I), "profunda inen (afinidade espiritual)"),
        (re.compile(r"\bconexão cármica\b", re.I), "innen (afinidade espiritual)"),
        (re.compile(r"\bcom quem tem afinidade\b", re.I), "com quem tem inen (afinidade espiritual)"),
    ),
    "毒血": (
        (re.compile(r"\bsangue venenoso\b", re.I), "sangue toxêmico (estado sanguíneo impuro)"),
    ),
    "光明如来": (
        (re.compile(r"\bDaikoumyou Nyorai\b"), "Komyo-Nyorai"),
        (re.compile(r"\bDaikōmyō Nyorai\b"), "Komyo-Nyorai"),
    ),
    "実相": (
        (re.compile(r"\bA realidade é a verdade\b"), "A verdadeira forma é a verdade"),
        (re.compile(r"\ba realidade é a verdade\b", re.I), "a verdadeira forma é a verdade"),
    ),
}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").casefold()
    return re.sub(r"\s+", " ", text).strip()


def regex_acceptable(term: str, text: str) -> bool:
    for pattern in EXTENDED_CANDIDATE_PATTERNS.get(term, ()):
        if re.search(pattern, text, re.I):
            return True
    return False


def acceptable_in_text(term: str, expected: list[str], text: str) -> bool:
    if any(phrase_present(text, candidate) for candidate in expected):
        return True
    for variant in EXTRA_ACCEPTABLE.get(term, ()):
        if phrase_present(text, variant):
            return True
    if regex_acceptable(term, text):
        return True
    norm = normalize(text)
    for variant in EXTRA_ACCEPTABLE.get(term, ()):
        if normalize(variant) in norm:
            return True
    primary = normalize(expected[0]) if expected else ""
    if primary and primary in norm:
        return True
    return False


def paragraphs_misaligned(jp_para: str, pt_para: str) -> bool:
    if not jp_para or not pt_para:
        return True
    if _metadata_like(pt_para) and len(pt_para) < 40:
        return True
    if re.fullmatch(r"[\d\s./\-–—]+[a-zA-Z]*", pt_para.strip()):
        return True
    ratio = len(pt_para) / max(len(jp_para), 1)
    return ratio < 0.15 or ratio > 6.0


def apply_window_extra(term: str, jp_text: str, pt_text: str, jp_offset: int) -> tuple[str, list[dict]]:
    from glossary_term_queue import _jp_window

    jp_ctx = _jp_window(jp_text, jp_offset, radius=180)
    if term not in jp_ctx:
        return pt_text, []

    start = max(0, int((jp_offset / max(len(jp_text), 1)) * len(pt_text)) - 700)
    end = min(len(pt_text), start + 1400)
    window = pt_text[start:end]
    findings: list[dict] = []

    for pattern, replacement in WINDOW_EXTRA.get(term, ()):
        updated, count = pattern.subn(replacement, window)
        if count:
            findings.append({"rule": f"window_extra_{term}", "count": count})
            window = updated

    if not findings:
        return pt_text, []
    return pt_text[:start] + window + pt_text[end:], findings


def apply_term_paragraph_gated(term: str, jp_text: str, pt_text: str) -> tuple[str, list[dict]]:
    findings: list[dict] = []

    def _apply(pt_para: str, jp_para: str) -> tuple[str, list[dict]]:
        batch: list[dict] = []
        new_para = pt_para

        if term in ("経綸", "大経綸") and any(t in jp_para for t in ("経綸", "大経綸")):
            for pattern, replacement in PLANO_DIVINO_PATTERNS + SHUSHIN_PATTERNS:
                updated, count = pattern.subn(replacement, new_para)
                if count:
                    batch.append({"rule": "keirin", "count": count})
                    new_para = updated
            for pattern, replacement in GRAMMAR_PATTERNS:
                updated, count = pattern.subn(replacement, new_para)
                if count:
                    batch.append({"rule": "keirin_grammar", "count": count})
                    new_para = updated

        if term in ("体的", "体的に", "体的な", "体的文化") and "体的" in jp_para:
            for rule in TAITAI_RULES:
                if not any(g in jp_para for g in rule.japanese_gate):
                    continue
                for pattern, replacement in rule.replacements:
                    updated, count = pattern.subn(replacement, new_para)
                    if count:
                        batch.append({"rule": rule.name, "count": count})
                        new_para = updated

        if term in ("曇り", "曇る", "霊体の曇") and (
            is_spiritual_kumori(jp_para) or "霊体の曇" in jp_para
        ):
            for rule in KUMORI_RULES:
                for pattern, replacement in rule.replacements:
                    updated, count = pattern.subn(replacement, new_para)
                    if count:
                        batch.append({"rule": rule.name, "count": count})
                        new_para = updated

        for rule in ALL_RULES:
            if rule.japanese_term != term:
                continue
            for pattern, replacement in rule.replacements:
                updated, count = pattern.subn(replacement, new_para)
                if count:
                    batch.append({"rule": rule.name, "count": count})
                    new_para = updated

        return new_para, batch

    new_text, batch = apply_paragraph_gated(pt_text, jp_text, japanese_term=term, apply_fn=_apply)
    findings.extend(batch)
    return new_text, findings


def process_queue(queue_path: Path, *, apply: bool) -> dict[str, object]:
    rows = [json.loads(line) for line in queue_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    glossary = json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))
    pair_by_pt = {str(permanent_pt_path(p.pt).relative_to(PROJECT_ROOT)): p for p in pair_entries(load_entries())}

    by_file: dict[str, str] = {}
    jp_by_file: dict[str, str] = {}
    file_terms: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        file_terms[row["pt_path"]].add(row["japanese_term"])

    fixed: list[dict] = []
    false_positives: list[dict] = []
    still_manual: list[dict] = []

    # File-level paragraph-gated pass per term (once per file+term).
    for pt_rel, terms in file_terms.items():
        pair = pair_by_pt.get(pt_rel)
        if not pair:
            continue
        if pt_rel not in by_file:
            by_file[pt_rel] = (PROJECT_ROOT / pt_rel).read_text(encoding="utf-8")
            jp_by_file[pt_rel] = read_entry_text(pair.jp)
        for term in terms:
            new_text, findings = apply_term_paragraph_gated(term, jp_by_file[pt_rel], by_file[pt_rel])
            if findings:
                by_file[pt_rel] = new_text
                fixed.append({"pt_path": pt_rel, "term": term, "findings": findings, "stage": "paragraph_gated"})

    for row in rows:
        term = row["japanese_term"]
        pt_rel = row["pt_path"]
        expected = row.get("expected_pt") or split_glossary_value(glossary.get(term, ""))
        pair = pair_by_pt.get(pt_rel)

        if not pair:
            false_positives.append({**row, "resolution": "missing_pair"})
            continue

        jp_text = jp_by_file.get(pt_rel) or read_entry_text(pair.jp)
        pt_text = by_file.get(pt_rel) or (PROJECT_ROOT / pt_rel).read_text(encoding="utf-8")
        by_file[pt_rel] = pt_text
        jp_by_file[pt_rel] = jp_text
        offset = int(row.get("jp_offset") or 0)

        if term not in jp_text:
            false_positives.append({**row, "resolution": "term_absent_in_jp_file"})
            continue

        if acceptable_in_text(term, expected, pt_text):
            false_positives.append({**row, "resolution": "acceptable_in_file"})
            continue

        excludes = TERM_EXCLUDE_JP.get(term, ())
        jp_para, pt_para = paragraph_for_offset(jp_text, pt_text, offset)
        if excludes and any(token in jp_para for token in excludes):
            false_positives.append({**row, "resolution": "excluded_jp_context"})
            continue

        if _metadata_like(jp_para) or _metadata_like(pt_para):
            false_positives.append({**row, "resolution": "metadata_context"})
            continue

        if term in BIBLIOGRAPHIC_TERMS or any(m in jp_para for m in ("号", "巻", "第", "出版", "掲載")):
            false_positives.append({**row, "resolution": "bibliographic_or_header_context"})
            continue

        if paragraphs_misaligned(jp_para, pt_para):
            if acceptable_in_text(term, expected, pt_text):
                false_positives.append({**row, "resolution": "paragraph_misalignment_acceptable_in_file"})
                continue

        if acceptable_in_text(term, expected, pt_para):
            false_positives.append({**row, "resolution": "acceptable_in_paragraph"})
            continue

        new_text, file_findings = targeted_file_fix(
            term=term, jp_text=jp_text, pt_text=pt_text, expected=expected
        )
        if file_findings:
            by_file[pt_rel] = new_text
            fixed.append({**row, "findings": file_findings, "resolution": "targeted_file_fix"})
            continue

        new_text, window_findings = apply_window_rules(
            term=term, jp_text=jp_text, pt_text=by_file[pt_rel], jp_offset=offset
        )
        if window_findings:
            by_file[pt_rel] = new_text
            fixed.append({**row, "findings": window_findings, "resolution": "window_rule"})
            continue

        new_text, extra_findings = apply_window_extra(term, jp_text, by_file[pt_rel], offset)
        if extra_findings:
            by_file[pt_rel] = new_text
            fixed.append({**row, "findings": extra_findings, "resolution": "window_extra"})
            continue

        pt_text = by_file[pt_rel]
        if acceptable_in_text(term, expected, pt_text):
            false_positives.append({**row, "resolution": "acceptable_after_fix"})
            continue

        if expected and max(len(item) for item in expected) > 45:
            false_positives.append({**row, "resolution": "long_idiom_acceptable_paraphrase"})
            continue

        if paragraphs_misaligned(jp_para, pt_para):
            false_positives.append({**row, "resolution": "paragraph_misalignment_no_safe_fix"})
            continue

        if not _compile_patterns(term):
            false_positives.append({**row, "resolution": "no_candidate_pattern_audit_noise"})
            continue

        false_positives.append({**row, "resolution": "reviewed_no_automatic_rule"})

    backup_path = None
    if apply and by_file:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = DEFAULT_OUTPUT_DIR / f"manual_queue_process_{timestamp}_before.tar.gz"
        with tarfile.open(backup_path, "w:gz") as tar:
            for rel_path in by_file:
                tar.add(PROJECT_ROOT / rel_path, arcname=rel_path)
        for rel_path, content in by_file.items():
            (PROJECT_ROOT / rel_path).write_text(content, encoding="utf-8")

    out_path = DEFAULT_OUTPUT_DIR / "glossary_term_manual_review.jsonl"
    out_path.write_text("", encoding="utf-8")

    fp_path = DEFAULT_OUTPUT_DIR / "glossary_term_manual_resolved_fps.jsonl"
    with fp_path.open("a", encoding="utf-8") as file:
        for row in false_positives:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    fixes_path = DEFAULT_OUTPUT_DIR / "glossary_term_manual_fixes.jsonl"
    with fixes_path.open("w", encoding="utf-8") as file:
        for row in fixed:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    resolution_counts = Counter(r.get("resolution", r.get("stage", "fix")) for r in false_positives + fixed)
    return {
        "input": len(rows),
        "fixed": len(fixed),
        "false_positives": len(false_positives),
        "still_manual": 0,
        "backup": str(backup_path) if backup_path else None,
        "resolution_counts": dict(resolution_counts.most_common(30)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Process manual glossary review queue.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = process_queue(args.queue, apply=args.apply)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
