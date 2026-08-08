#!/usr/bin/env python3
"""Paragraph-level glossary audit and term queue processor."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from apply_safe_glossary_fixes import load_entries, pair_entries, permanent_pt_path, read_entry_text
from audit_translation_glossary import (
    GLOSSARY_PATH,
    LOW_SIGNAL_TERMS,
    phrase_present,
    split_glossary_value,
)
from contextual_glossary_review import CANDIDATE_PATTERNS


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review"
DEFAULT_AUDIT = DEFAULT_OUTPUT_DIR / "glossary_audit_high_confidence.jsonl"

# Single-kanji glossary entries are usually contextual; skip automatic pending.
SKIP_AUTOMATIC_TERMS = LOW_SIGNAL_TERMS | {
    "熱",
    "道",
    "血",
    "我",
    "霊",
    "神",
    "心",
    "法",
    "天",
    "地",
    "人",
    "観音",
}

TERM_EXCLUDE_JP: dict[str, tuple[str, ...]] = {
    "曇り": ("曇天", "天気", "気象", "雨", "晴"),
    "先祖": ("先祖代々", "先祖代〄", "先祖代"),
    "道理": ("簡売", "簡単", "明らか", "分かりやす", "この道理を考", "よく分る", "調和", "神とは言い換えれば道理", "道理に叶", "道理に外", "道理に従", "道理を弁", "道理を守", "道理を分", "道理を信", "道理が分から", "道理はない", "道理も人間", "道理がないから"),
    "凝り": ("首肩", "肩の凝り", "非常に凝り"),
    "唯心観": ("唯心観念",),
    "瑞雲": ("瑞雲山",),
    "天国": ("福音", "マタイ", "御言葉", "聖書"),
    "注射": ("予防接種", "種痘", "ワクチン", "BCG"),
    "薬毒": (),
    "邪神": ("岡田は邪神", "岡田が邪神"),
    "修業": ("俳優", "団子"),
    "医術": ("西洋医学", "俳優"),
    "観音": ("観音様", "観音講座", "観音会", "観音経"),
    "霊術": ("浄霊術", "霊術師"),
    "明为様": ("自観大先生", "週刉朝日", "掲載された", "対談は", "ブレーデン"),
    "下熱": ("目下熱海", "目下"),
    "水霊": ("夢声", "Musei", "Shimizu"),
    "前世": ("何千年前世",),
    "現界": ("幽現界",),
}

EXTENDED_CANDIDATE_PATTERNS: dict[str, tuple[str, ...]] = {
    **CANDIDATE_PATTERNS,
    "迷信": (r"\bsuperstiç(?:ão|ões)\b", r"\bsupersticios[ao]\w*\b", r"\bcredos supersticiosos\b"),
    "霊線": (r"\blinhas espirituais\b", r"\blinha espiritual\b", r"\bcordões espirituais\b"),
    "先祖": (r"\bantepassados\b", r"\baos ancestrais\b", r"\baos antepassados\b"),
    "祖先": (r"\bantepassados\b", r"\baos ancestrais\b"),
    "祖霊": (r"\bespíritos dos antepassados\b", r"\bespíritos ancestrais\b"),
    "大乗": (r"\bMahayana\b", r"\bGrande Veículo\b"),
    "小乗": (r"\bHinayana\b", r"\bPequeno Veículo\b"),
    "明主様": (r"\bMeishu-sama\b", r"\bMeishu sama\b"),
    "御論文": (r"\bensaio\b", r"\bartigo\b", r"\btexto\b"),
    "霊界": (r"\breinos espirituais\b", r"\breino espiritual\b", r"\bmundo dos espíritos\b"),
    "神示": (r"\boráculos divinos\b", r"\brevelações divinas\b"),
    "善言讃詞": (r"\bZengen Sandji\b", r"\bOração Zengen\b"),
    "自観": (r"\bauto-contemplação\b", r"\bautocontemplação\b", r"\bJikan\b"),
    "霊体": (r"\bcorpos astrais\b", r"\bcorpo astral\b"),
    "生霊": (r"\balmas vivas\b", r"\bespíritos vivos\b", r"\bespírito vivo\b"),
    "死霊": (r"\bespíritos mortos\b", r"\balmas penadas\b"),
    "大本教": (r"\bOmoto\b", r"\bIgreja Omoto\b", r"\breligião Omoto\b"),
    "因縁": (r"\bkarma\b", r"\bcausalidade\b"),
    "固結": (r"\bendurecimento\b", r"\bcoagulação\b"),
    "黴菌": (r"\bgermes\b", r"\bbactérias\b"),
    "自然農法": (r"\bagricultura natural\b", r"\bAgricultura Natural\b"),
    "異物": (r"\bsubstâncias estranhas\b", r"\bsubstância estranha\b", r"\bcorpos estranhos\b"),
    "末紙": (r"\bMattō\b", r"\bedição especial\b"),
    "病菌": (r"\bmicróbios patogênicos\b", r"\bmicróbio patogênico\b", r"\bpatogênicos\b", r"\binfecci(?:oso|osa|osos|osas|osas)\b"),
    "道理": (r"\brazão evidente\b", r"\brazão clara\b", r"\blógica evidente\b", r"\bverdade clara\b", r"\bverdade tão clara\b", r"\bCaminho Perfeito\b"),
    "邪教": (r"\bcultos malignos\b", r"\breligião maligna\b", r"\breligiões malignas\b"),
    "心臓": (r"\bcoração\b", r"\bcardíac(?:o|a|as|os)\b", r"\bcirurgias cardíacas\b"),
    "明为様": (r"\bMeishu-Sama\b", r"\bMeishu sama\b"),
    "御神体": (r"\bGoshintai\b", r"\bImagem da Luz Divina\b"),
    "浄霊法": (r"\bmétodo de purificação\b", r"\bmétodo do Johrei\b"),
    "御利益": (r"\bbenefício material\b", r"\bbenefícios materiais\b", r"\bbenefício espiritual\b"),
    "御守護": (r"\bproteção divina\b", r"\bproteção de Deus\b", r"\bproteção dos deuses\b"),
    "御守り": (r"\bproteção divina\b", r"\bamuleto\b"),
    "祀る": (r"\bcultuar\b", r"\bvenerar\b", r"\badorar\b"),
    "御教え集": (r"\bColetânea de Ensinamentos\b", r"\bColeção de Ensinamentos\b"),
    "善言讃詞": (r"\bZengen Sandji\b", r"\bOração Zengen\b", r"\bOração de Louvor\b"),
    "漢方薬": (r"\bmedicina chinesa\b", r"\bMedicina Chinesa\b", r"\bremédio chinês\b"),
    "後頭部": (r"\bparte posterior da cabeça\b", r"\bnuca\b", r"\boccipital\b"),
    "副守護神": (r"\bdeus guardião secundário\b", r"\bguardião secundário\b"),
    "正守護神": (r"\bdeus guardião principal\b", r"\bguardião principal\b"),
    "肺病": (r"\btuberculose\b", r"\bdoença pulmonar\b"),
    "御論文": (r"\bensaio\b", r"\bartigo\b", r"\btexto de Meishu-Sama\b"),
    "体的": (r"\bmaterialmente\b", r"\bmaterial\b", r"\bcorporeamente\b", r"\bimpurezas materiais\b"),
    "水素": (r"\bhidrogênio\b", r"\belemento água\b", r"\belemento fogo\b"),
    "霊体": (r"\bcorpo espiritual\b", r"\bcorpos astrais\b", r"\bcorpo astral\b", r"\bespiritual\b"),
    "地上天国": (r"\breino celestial na terra\b", r"\breino dos céus na terra\b", r"\bparaíso na terra\b"),
    "天国": (r"\breino celestial\b", r"\breino dos céus\b", r"\bparaíso\b", r"\bcéu\b"),
    "学校": (r"\bescola\b", r"\bseminário\b", r"\bcentro de formação\b"),
    "宗教家": (r"\blíder religioso\b", r"\breligioso\b", r"\bhomem de religião\b"),
    "急所": (r"\bponto vital\b", r"\bpontos vitais\b", r"\bponto chave\b"),
    "排泄": (r"\bexcreção\b", r"\bexcretar\b", r"\bexcretad\b", r"\beliminação\b"),
    "薬毒": (r"\bveneno de medicamentos\b", r"\btoxina\b", r"\bmedicamento\b", r"\bfármaco\b"),
    "天狗": (r"\btengu\b", r"\bdemonio\b", r"\bdemônio\b"),
    "稲荷": (r"\bInari\b", r"\binari\b"),
    "浄霊": (r"\bJohrei\b", r"\bjohrei\b", r"\bpurificação espiritual\b"),
    "救世教": (r"\bKyusei\b", r"\bkyusei\b", r"\bDoutrina Absoluta\b"),
    "凝り": (r"\bsolidificação\b", r"\bcoagulação\b", r"\bendurecimento\b"),
    "浄化発生": (r"\bpurificação\b", r"\bpurificador\b", r"\bpurificar\b"),
    "神格": (r"\bdeificação\b", r"\bdeus\b", r"\bdivino\b"),
    "産土神": (r"\bdeus do solo\b", r"\bdeus local\b", r"\bespírito do solo\b"),
    "唯心主義": (
        r"\bidealismo\b",
        r"\bIdealismo\b",
        r"\bidealista\b",
        r"\bIdealista\b",
        r"\bidealistas\b",
        r"\bvisão idealista\b",
    ),
    "唯心为義": (
        r"\bidealismo\b",
        r"\bIdealismo\b",
        r"\bidealista\b",
        r"\bIdealista\b",
        r"\bidealistas\b",
        r"\bvisão idealista\b",
    ),
    "唯心为義者": (r"\bidealista\b", r"\bIdealista\b", r"\bidealistas\b"),
    "唯心思想": (r"\bidealismo\b", r"\bpensamento idealista\b"),
    "唯心観": (r"\bvisão idealista\b", r"\bidealismo\b"),
    "精神为義": (r"\bidealismo\b", r"\bIdealismo\b"),
    "物質为義": (r"\bidealismo\b", r"\bIdealismo\b"),
    "唯物为義": (r"\bidealismo\b", r"\bIdealismo\b"),
    "唯物为義者": (r"\bidealista\b", r"\bIdealista\b"),
}

_RUN_GLOSSARY_PATTERN_OVERRIDES: dict[str, tuple[str, ...]] = {}


def set_glossary_pattern_overrides(overrides: dict[str, tuple[str, ...]]) -> None:
    global _RUN_GLOSSARY_PATTERN_OVERRIDES
    _RUN_GLOSSARY_PATTERN_OVERRIDES = dict(overrides)


def load_glossary_pattern_overrides(path: Path | None) -> dict[str, tuple[str, ...]]:
    if not path or not path.exists():
        set_glossary_pattern_overrides({})
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    merged: dict[str, tuple[str, ...]] = {}
    for term, patterns in data.items():
        if isinstance(patterns, list):
            merged[term] = tuple(str(p) for p in patterns)
    set_glossary_pattern_overrides(merged)
    return merged


def save_glossary_pattern_overrides(path: Path, overrides: dict[str, tuple[str, ...]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serializable = {term: list(patterns) for term, patterns in sorted(overrides.items())}
    path.write_text(json.dumps(serializable, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def merge_glossary_pattern_overrides(
    base: dict[str, tuple[str, ...]],
    extra: dict[str, tuple[str, ...]],
) -> dict[str, tuple[str, ...]]:
    merged = dict(base)
    for term, patterns in extra.items():
        existing = merged.get(term, ())
        seen: set[str] = set(existing)
        added = tuple(p for p in patterns if p not in seen)
        if added:
            merged[term] = existing + added
    return merged


@dataclass(frozen=True)
class PendingItem:
    japanese_term: str
    pt_path: str
    expected_pt: list[str]
    jp_snippet: str
    pt_snippet: str
    reason: str
    jp_offset: int


def _compile_patterns(term: str) -> list[re.Pattern[str]]:
    patterns = EXTENDED_CANDIDATE_PATTERNS.get(term, ())
    extra = _RUN_GLOSSARY_PATTERN_OVERRIDES.get(term, ())
    return [re.compile(pattern, flags=re.IGNORECASE) for pattern in (*patterns, *extra)]


def _primary_expected(expected: list[str]) -> str | None:
    return expected[0] if expected else None


def _pt_window(jp_text: str, pt_text: str, jp_offset: int, radius: int = 450) -> str:
    if not jp_text:
        return pt_text[: radius * 2]
    ratio = jp_offset / max(len(jp_text), 1)
    center = int(ratio * len(pt_text))
    return pt_text[max(0, center - radius) : min(len(pt_text), center + radius)]


def _jp_window(jp_text: str, jp_offset: int, radius: int = 120) -> str:
    return jp_text[max(0, jp_offset - radius) : min(len(jp_text), jp_offset + radius)]


def _metadata_like(text: str) -> bool:
    markers = (
        "Publicado em",
        "---",
        "**",
        "Original path:",
        "Original publication reference",
        "Fonte:",
        "Nº ",
        "N° ",
        "Collection ID:",
        "Paired JP entry:",
        "Paired Portuguese title:",
        "Publication source:",
        "Language: pt",
        "Language: jp",
    )
    return any(marker in text for marker in markers) and len(text) < 280


def _index_like(text: str) -> bool:
    markers = (
        "\t",
        "索\t引",
        "略年譜",
        "あとがき",
        "目次",
        "岡田茂",
        "教祖",
        "・",
        "　　",
        "#昭和",
        "新聞恐怖",
        "御対談記",
        "自観大先生",
        "ジャーナリスト",
        "唯物主義と唯心主義",
        "大宅壮",
        "時局と霊界",
        "主義というもの",
        "為の字",
        "君に与う",
        "記事と嘘",
        "御対談記",
        "現当利益の宗教",
        "無神迷信",
        "自然農法の原理",
        "革命的増産",
        "道治国",
        "本数と大道",
        "肥料迷信",
        "堆肥の効",
        "文明の創造",
        "農法の技術",
        "まえがき",
    )
    toc_markers = (
        "自然農法の原理",
        "革命的増産",
        "道治国",
        "本数と大道",
        "肥料迷信",
        "堆肥の効",
        "文明の創造",
        "農法の技術",
    )
    if any(marker in text for marker in toc_markers):
        return True
    hits = sum(1 for marker in markers if marker in text)
    if hits >= 2:
        return True
    return hits >= 1 and len(text) < 220


def verify_audit_finding(
    *,
    term: str,
    expected: list[str],
    jp_text: str,
    pt_text: str,
    max_occurrence_checks: int = 12,
) -> tuple[str, PendingItem | None, dict | None]:
    excludes = TERM_EXCLUDE_JP.get(term, ())
    if any(phrase_present(pt_text, candidate) for candidate in expected):
        return "false_positive", None, {"reason": "expected_present_in_pt", "japanese_term": term}

    occurrences = [match.start() for match in re.finditer(re.escape(term), jp_text)]
    if not occurrences:
        return "false_positive_no_term", None, {"reason": "term_not_in_jp_file", "japanese_term": term}
    if max_occurrence_checks > 0 and len(occurrences) > max_occurrence_checks:
        occurrences = occurrences[:max_occurrence_checks]

    patterns = _compile_patterns(term)
    unresolved = 0
    fixable = False
    sample_pending: PendingItem | None = None
    sample_jp = ""
    sample_pt = ""

    for offset in occurrences:
        jp_ctx = _jp_window(jp_text, offset)
        pt_ctx = _pt_window(jp_text, pt_text, offset)
        if excludes and any(token in jp_ctx for token in excludes):
            continue
        if _metadata_like(jp_ctx) or _metadata_like(pt_ctx) or _index_like(jp_ctx):
            continue
        if any(phrase_present(pt_ctx, candidate) for candidate in expected):
            continue
        if any(pattern.search(pt_text) for pattern in patterns):
            continue
        if any(pattern.search(pt_ctx) for pattern in patterns):
            fixable = True
            sample_pending = PendingItem(
                japanese_term=term,
                pt_path="",
                expected_pt=expected,
                jp_snippet=jp_ctx,
                pt_snippet=pt_ctx,
                reason="candidate_variant_found",
                jp_offset=offset,
            )
            continue
        unresolved += 1
        sample_jp = jp_ctx
        sample_pt = pt_ctx
        sample_pending = PendingItem(
            japanese_term=term,
            pt_path="",
            expected_pt=expected,
            jp_snippet=sample_jp,
            pt_snippet=sample_pt,
            reason="missing_glossary_form",
            jp_offset=offset,
        )

    if fixable and unresolved == 0:
        return "fixable", sample_pending, None
    if unresolved == 0:
        return "false_positive", None, {"reason": "expected_or_acceptable_in_context", "japanese_term": term}
    if fixable:
        return "fixable", sample_pending, None
    return "pending", sample_pending, None


def build_queue_from_audit(audit_path: Path, glossary: dict[str, object]) -> tuple[list[PendingItem], list[dict], list[PendingItem]]:
    rows = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    pair_by_pt: dict[str, object] = {}
    for pair in pair_entries(load_entries()):
        pair_by_pt[str(permanent_pt_path(pair.pt).relative_to(PROJECT_ROOT))] = pair

    pending: list[PendingItem] = []
    false_positives: list[dict] = []
    fixable: list[PendingItem] = []
    seen: set[tuple[str, str]] = set()

    for row in rows:
        term = row["japanese_term"]
        pt_rel = row.get("pt_permanent_path") or row.get("pt_path", "")
        if not pt_rel.startswith("textos_portugues/"):
            continue
        key = (term, pt_rel)
        if key in seen:
            continue
        seen.add(key)
        if term in SKIP_AUTOMATIC_TERMS:
            false_positives.append({"japanese_term": term, "pt_path": pt_rel, "reason": "skip_automatic_term"})
            continue

        expected = row.get("expected_pt") or split_glossary_value(glossary.get(term, ""))
        pair = pair_by_pt.get(pt_rel)
        if not pair:
            continue
        jp_text = read_entry_text(pair.jp)
        pt_text = (PROJECT_ROOT / pt_rel).read_text(encoding="utf-8")

        status, item, fp = verify_audit_finding(term=term, expected=expected, jp_text=jp_text, pt_text=pt_text)
        if fp:
            fp["pt_path"] = pt_rel
            false_positives.append(fp)
        elif status == "fixable" and item:
            item = PendingItem(
                japanese_term=item.japanese_term,
                pt_path=pt_rel,
                expected_pt=item.expected_pt,
                jp_snippet=item.jp_snippet,
                pt_snippet=item.pt_snippet,
                reason=item.reason,
                jp_offset=item.jp_offset,
            )
            fixable.append(item)
        elif status == "pending" and item:
            pending.append(
                PendingItem(
                    japanese_term=item.japanese_term,
                    pt_path=pt_rel,
                    expected_pt=item.expected_pt,
                    jp_snippet=item.jp_snippet,
                    pt_snippet=item.pt_snippet,
                    reason=item.reason,
                    jp_offset=item.jp_offset,
                )
            )

    return pending, false_positives, fixable


def apply_fixable_items(items: list[PendingItem], *, apply: bool) -> tuple[list[dict], list[PendingItem]]:
    by_file: dict[str, str] = {}
    changes: list[dict] = []
    unresolved: list[PendingItem] = []

    for item in items:
        primary = _primary_expected(item.expected_pt)
        if not primary:
            unresolved.append(item)
            continue
        path = PROJECT_ROOT / item.pt_path
        if item.pt_path not in by_file:
            by_file[item.pt_path] = path.read_text(encoding="utf-8")
        pt_text = by_file[item.pt_path]
        jp_pair = next(
            (
                pair
                for pair in pair_entries(load_entries())
                if str(permanent_pt_path(pair.pt).relative_to(PROJECT_ROOT)) == item.pt_path
            ),
            None,
        )
        if not jp_pair:
            unresolved.append(item)
            continue
        jp_text = read_entry_text(jp_pair.jp)
        window = _pt_window(jp_text, pt_text, item.jp_offset, radius=700)
        updated = window
        replaced = False
        for pattern in _compile_patterns(item.japanese_term):
            new_window, count = pattern.subn(primary, updated)
            if count:
                updated = new_window
                replaced = True
                changes.append(
                    {
                        "japanese_term": item.japanese_term,
                        "pt_path": item.pt_path,
                        "replacement": primary,
                        "pattern": pattern.pattern,
                        "count": count,
                    }
                )
        if not replaced:
            unresolved.append(item)
            continue
        center = int((item.jp_offset / max(len(jp_text), 1)) * len(pt_text))
        start = max(0, center - 700)
        end = min(len(pt_text), center + 700)
        by_file[item.pt_path] = pt_text[:start] + updated + pt_text[end:]

    if apply and by_file:
        for rel_path, content in by_file.items():
            (PROJECT_ROOT / rel_path).write_text(content, encoding="utf-8")

    return changes, unresolved


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Paragraph glossary audit and queue processing.")
    parser.add_argument("--apply-candidates", action="store_true")
    parser.add_argument("--audit", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    glossary = json.loads(GLOSSARY_PATH.read_text(encoding="utf-8"))
    pending, false_positives, fixable = build_queue_from_audit(args.audit, glossary)
    changes, still_fixable = apply_fixable_items(fixable, apply=args.apply_candidates)
    pending.extend(still_fixable)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    queue_path = args.output_dir / "glossary_term_pending_queue.jsonl"
    fp_path = args.output_dir / "glossary_term_false_positives.jsonl"
    changes_path = args.output_dir / "glossary_term_candidate_fixes.jsonl"

    with queue_path.open("w", encoding="utf-8") as file:
        for item in pending:
            file.write(
                json.dumps(
                    {
                        "japanese_term": item.japanese_term,
                        "pt_path": item.pt_path,
                        "expected_pt": item.expected_pt,
                        "reason": item.reason,
                        "jp_snippet": item.jp_snippet,
                        "pt_snippet": item.pt_snippet,
                        "jp_offset": item.jp_offset,
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )

    with fp_path.open("w", encoding="utf-8") as file:
        for row in false_positives:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    with changes_path.open("w", encoding="utf-8") as file:
        for row in changes:
            file.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    term_counts = Counter(item.japanese_term for item in pending)
    print(f"pending={len(pending)} false_positives={len(false_positives)} candidate_fixes={len(changes)}")
    print("top_pending=" + json.dumps(dict(term_counts.most_common(20)), ensure_ascii=False))
    print(f"queue={queue_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
