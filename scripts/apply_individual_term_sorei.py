#!/usr/bin/env python3
"""Individual glossary pass for 祖霊 / 先祖 / 祖先 and correlates.

Policy (see reports/translation_review/individual/parecer_traducao_sorei_senzo_sosen.md):
- 祖霊 -> espírito ancestral; cult verbs -> sufragar / culto em sufrágio
- 先祖 -> antepassado(s); wrong *ancestrais* pronouns -> antepassados
- 祖先 -> ancestrais (linhagem); 祖先の罪 -> pecado dos ancestrais
- 先祖代々 / 先祖代々之霊 -> fixed compounds
"""

from __future__ import annotations

import argparse
import json
import re
import tarfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from apply_safe_glossary_fixes import load_entries, pair_entries, permanent_pt_path, read_entry_text


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "reports" / "translation_review"

# Do not rewrite veneration of nobles, art, etc.
KEEP_VENERATION_PATTERNS = (
    r"\bvenerar uma pessoa\b",
    r"\bvenerar pessoa\b",
    r"\bvenerar o imperador\b",
    r"\bvenerar uma divindade\b",
    r"\bvenerar os deuses\b",
    r"\bvenerar a Deus\b",
    r"\bvenerar a divindade\b",
    r"\bvenerar o fundador\b",
    r"\bvenerar o Senhor\b",
    r"\bvenerar Buda\b",
    r"\bvenerar o Buda\b",
    r"\bvenerar a arte\b",
    r"\bvenerar a natureza\b",
    r"\bobjeto de veneração\b",
    r"\bveneração de uma pessoa\b",
    r"\bveneração de pessoa\b",
)

# Takamimusubi etc. — ancestral do mundo espiritual (not 祖霊)
KEEP_ANCESTRAL_LINEAGE_PATTERNS = (
    r"\bancestral do mundo espiritual\b",
    r"\bancestral do povo\b",
    r"\bancestral comum\b",
    r"\bancestral judeu\b",
)


@dataclass(frozen=True)
class Rule:
    name: str
    japanese_gate: tuple[str, ...]
    replacements: tuple[tuple[re.Pattern[str], str], ...]
    japanese_any: bool = False  # if True, match if any gate term in jp


def _gate(jp_text: str, rule: Rule) -> bool:
    if not rule.japanese_gate:
        return True
    if rule.japanese_any:
        return any(term in jp_text for term in rule.japanese_gate)
    return all(term in jp_text for term in rule.japanese_gate)


def should_keep_match(text: str, start: int, end: int) -> bool:
    for pattern in KEEP_VENERATION_PATTERNS + KEEP_ANCESTRAL_LINEAGE_PATTERNS:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            if not (match.end() <= start or match.start() >= end):
                return True
    return False


@dataclass(frozen=True)
class Change:
    rule: str
    pattern: str
    replacement: str
    count: int


def apply_rule_list(text: str, rule: Rule) -> tuple[str, list[Change]]:
    findings: list[Change] = []
    new_text = text
    for pattern, replacement in rule.replacements:
        def _replace(match: re.Match[str], replacement=replacement) -> str:
            if should_keep_match(new_text, match.start(), match.end()):
                return match.group(0)
            return replacement

        updated, count = pattern.subn(_replace, new_text)
        if count:
            findings.append(Change(rule.name, pattern.pattern, replacement, count))
            new_text = updated
    return new_text, findings


RULES: tuple[Rule, ...] = (
    Rule(
        name="sorei_espirito_ancestral",
        japanese_gate=("祖霊", "先祖", "祖先"),
        japanese_any=True,
        replacements=(
            (re.compile(r"\bespírito de ancestral\b", flags=re.IGNORECASE), "espírito ancestral"),
            (re.compile(r"\bespíritos de ancestral\b", flags=re.IGNORECASE), "espíritos ancestrais"),
            (re.compile(r"\bEspírito de Ancestral\b"), "Espírito Ancestral"),
            (re.compile(r"\bEspíritos de Ancestral\b"), "Espíritos Ancestrais"),
        ),
    ),
    Rule(
        name="senzo_dai_dai",
        japanese_gate=("先祖代々",),
        replacements=(
            (
                re.compile(r"(?<!espíritos )(?<!espírito )\bgerações de ancestrais\b", flags=re.IGNORECASE),
                "antepassados de todas as gerações",
            ),
            (
                re.compile(r"(?<!espíritos )(?<!espírito )\bancestrais de todas as gerações\b", flags=re.IGNORECASE),
                "antepassados de todas as gerações",
            ),
            (
                re.compile(r"\btabletes ancestrais\b", flags=re.IGNORECASE),
                "tabletes de sufrágio",
            ),
            (
                re.compile(r"\btablete ancestral\b", flags=re.IGNORECASE),
                "tablete de sufrágio",
            ),
        ),
    ),
    Rule(
        name="senzo_dai_dai_reii",
        japanese_gate=("先祖代々之霊",),
        replacements=(
            (
                re.compile(
                    r"\bespírito dos antepassados de todas as gerações\b",
                    flags=re.IGNORECASE,
                ),
                "espíritos ancestrais de todas as gerações",
            ),
            (
                re.compile(
                    r"\bespíritos dos antepassados de todas as gerações\b",
                    flags=re.IGNORECASE,
                ),
                "espíritos ancestrais de todas as gerações",
            ),
            (
                re.compile(
                    r"\bespírito dos antepassados de gerações\b",
                    flags=re.IGNORECASE,
                ),
                "espíritos ancestrais de todas as gerações",
            ),
            (
                re.compile(
                    r'(?<=")espírito dos antepassados de todas as gerações(?=")',
                    flags=re.IGNORECASE,
                ),
                "espíritos ancestrais de todas as gerações",
            ),
        ),
    ),
    Rule(
        name="senzo_antepassados",
        japanese_gate=("先祖",),
        replacements=(
            (re.compile(r"\bos ancestrais\b", flags=re.IGNORECASE), "os antepassados"),
            (re.compile(r"\bdos ancestrais\b", flags=re.IGNORECASE), "dos antepassados"),
            (re.compile(r"\baos ancestrais\b", flags=re.IGNORECASE), "aos antepassados"),
            (re.compile(r"\bpelos ancestrais\b", flags=re.IGNORECASE), "pelos antepassados"),
            (re.compile(r"\bseus ancestrais\b", flags=re.IGNORECASE), "seus antepassados"),
            (re.compile(r"\bnossos ancestrais\b", flags=re.IGNORECASE), "nossos antepassados"),
            (re.compile(r"\bmeus ancestrais\b", flags=re.IGNORECASE), "meus antepassados"),
            (re.compile(r"\bantigos ancestrais\b", flags=re.IGNORECASE), "antepassados mais antigos"),
            (re.compile(r"\bantigos antepassados\b", flags=re.IGNORECASE), "antepassados mais antigos"),
        ),
    ),
    Rule(
        name="sosen_senzo_pecado",
        japanese_gate=("先祖の罪",),
        replacements=(
            (
                re.compile(r"\bpecado dos ancestrais\b", flags=re.IGNORECASE),
                "pecado dos antepassados",
            ),
            (
                re.compile(r"\bpecados dos ancestrais\b", flags=re.IGNORECASE),
                "pecados dos antepassados",
            ),
        ),
    ),
    Rule(
        name="sosen_ancestrais",
        japanese_gate=("祖先の罪", "祖先の罪穢", "祖先には", "祖先も", "祖先を", "祖先と"),
        japanese_any=True,
        replacements=(
            (
                re.compile(r"\bpecado dos antepassados\b", flags=re.IGNORECASE),
                "pecado dos ancestrais",
            ),
            (
                re.compile(r"\bpecados dos antepassados\b", flags=re.IGNORECASE),
                "pecados dos ancestrais",
            ),
            (
                re.compile(r"\bimpureza dos antepassados\b", flags=re.IGNORECASE),
                "impureza dos ancestrais",
            ),
            (
                re.compile(r"\bimpurezas dos antepassados\b", flags=re.IGNORECASE),
                "impurezas dos ancestrais",
            ),
            (
                re.compile(r"\bdever para com os antepassados\b", flags=re.IGNORECASE),
                "dever para com os ancestrais",
            ),
            (
                re.compile(r"\bcomunicar aos antepassados\b", flags=re.IGNORECASE),
                "comunicar aos ancestrais",
            ),
            (
                re.compile(r"\bcomunicar às antepassados\b", flags=re.IGNORECASE),
                "comunicar aos ancestrais",
            ),
            (
                re.compile(r"\brelatório aos antepassados\b", flags=re.IGNORECASE),
                "relatório aos ancestrais",
            ),
            (
                re.compile(r"\brelatar aos antepassados\b", flags=re.IGNORECASE),
                "relatar aos ancestrais",
            ),
        ),
    ),
    Rule(
        name="culto_sufragio",
        japanese_gate=("祖霊", "先祖", "祖先", "祀"),
        japanese_any=True,
        replacements=(
            (
                re.compile(r"\bvenerar os espíritos ancestrais\b", flags=re.IGNORECASE),
                "sufragar os espíritos ancestrais",
            ),
            (
                re.compile(r"\bvenerar os antepassados\b", flags=re.IGNORECASE),
                "sufragar os antepassados",
            ),
            (
                re.compile(r"\bvenerar os ancestrais\b", flags=re.IGNORECASE),
                "sufragar os ancestrais",
            ),
            (
                re.compile(r"\bdevem venerar os espíritos ancestrais\b", flags=re.IGNORECASE),
                "devem sufragar os espíritos ancestrais",
            ),
            (
                re.compile(r"\bdeve venerar os espíritos ancestrais\b", flags=re.IGNORECASE),
                "deve sufragar os espíritos ancestrais",
            ),
            (
                re.compile(r"\btodos devem venerar\b", flags=re.IGNORECASE),
                "todos devem sufragar",
            ),
            (
                re.compile(r"\bcomo devem venerar os antepassados\b", flags=re.IGNORECASE),
                "como devem sufragar os antepassados",
            ),
            (
                re.compile(r"\bcomo deve venerar os antepassados\b", flags=re.IGNORECASE),
                "como deve sufragar os antepassados",
            ),
            (
                re.compile(r"\bcultuar os antepassados\b", flags=re.IGNORECASE),
                "sufragar os antepassados",
            ),
            (
                re.compile(r"\bcultuar os ancestrais\b", flags=re.IGNORECASE),
                "sufragar os ancestrais",
            ),
            (
                re.compile(r"\bcultuar o espírito\b", flags=re.IGNORECASE),
                "sufragar o espírito",
            ),
            (
                re.compile(r"\bcultuar os espíritos\b", flags=re.IGNORECASE),
                "sufragar os espíritos",
            ),
            (
                re.compile(r"\bcultuar os espíritos ancestrais\b", flags=re.IGNORECASE),
                "sufragar os espíritos ancestrais",
            ),
            (
                re.compile(r"\bcultuar seus próprios ancestrais\b", flags=re.IGNORECASE),
                "sufragar seus próprios ancestrais",
            ),
            (
                re.compile(r"\bcultuar o espírito do meu marido\b", flags=re.IGNORECASE),
                "sufragar o espírito do meu marido",
            ),
            (
                re.compile(r"\bcultuar esses espíritos\b", flags=re.IGNORECASE),
                "sufragar esses espíritos",
            ),
            (
                re.compile(r"\bcultuar uma parte do terreno\b", flags=re.IGNORECASE),
                "sufragar uma parte do terreno",
            ),
            (
                re.compile(r"\bcultuar o cônjuge anterior\b", flags=re.IGNORECASE),
                "sufragar o cônjuge anterior",
            ),
            (
                re.compile(r"\bcultuam o espírito\b", flags=re.IGNORECASE),
                "sufragam o espírito",
            ),
            (
                re.compile(r"\bcultuam os espíritos\b", flags=re.IGNORECASE),
                "sufragam os espíritos",
            ),
            (
                re.compile(r"\bcultuado em ambos\b", flags=re.IGNORECASE),
                "sufragado em ambos",
            ),
            (
                re.compile(r"\bnão devem ser cultuados separadamente\b", flags=re.IGNORECASE),
                "não devem ser sufragados separadamente",
            ),
            (
                re.compile(r"\bdevem ser cultuados\b", flags=re.IGNORECASE),
                "devem ser sufragados",
            ),
            (
                re.compile(r"\bdeve ser cultuado\b", flags=re.IGNORECASE),
                "deve ser sufragado",
            ),
            (
                re.compile(r"\bser cultuado em ambos\b", flags=re.IGNORECASE),
                "ser sufragado em ambos",
            ),
            (
                re.compile(r"\bQuanto mais pessoas cultuarem\b", flags=re.IGNORECASE),
                "Quanto mais pessoas sufragarem",
            ),
            (
                re.compile(r"\bQuanto mais pessoas cultuam\b", flags=re.IGNORECASE),
                "Quanto mais pessoas sufragam",
            ),
            (
                re.compile(r"\bnão cultuar os antepassados\b", flags=re.IGNORECASE),
                "não sufragar os antepassados",
            ),
            (
                re.compile(r"\bnão cultuar os ancestrais\b", flags=re.IGNORECASE),
                "não sufragar os ancestrais",
            ),
            (
                re.compile(r"\bpor não cultuar os antepassados\b", flags=re.IGNORECASE),
                "por não sufragar os antepassados",
            ),
            (
                re.compile(r"\bpor não serem cultuados\b", flags=re.IGNORECASE),
                "por não serem sufragados",
            ),
            (
                re.compile(r"\bpor não ser cultuado\b", flags=re.IGNORECASE),
                "por não ser sufragado",
            ),
            (
                re.compile(r"\bculto aos antepassados\b", flags=re.IGNORECASE),
                "culto em sufrágio aos antepassados",
            ),
            (
                re.compile(r"\bculto aos ancestrais\b", flags=re.IGNORECASE),
                "culto em sufrágio aos ancestrais",
            ),
            (
                re.compile(r"\bculto aos espíritos ancestrais\b", flags=re.IGNORECASE),
                "culto em sufrágio aos espíritos ancestrais",
            ),
            (
                re.compile(r"\bveneração aos antepassados\b", flags=re.IGNORECASE),
                "sufrágio aos antepassados",
            ),
            (
                re.compile(r"\bveneração aos ancestrais\b", flags=re.IGNORECASE),
                "sufrágio aos ancestrais",
            ),
            (
                re.compile(r"\bpara de venerar os antepassados\b", flags=re.IGNORECASE),
                "deixa de sufragar os antepassados",
            ),
            (
                re.compile(r"\bdeixar de venerar os antepassados\b", flags=re.IGNORECASE),
                "deixar de sufragar os antepassados",
            ),
            (
                re.compile(r"\bvenerar no xintoísmo\b", flags=re.IGNORECASE),
                "sufragar no xintoísmo",
            ),
            (
                re.compile(r"\bpor venerar os antepassados\b", flags=re.IGNORECASE),
                "por sufragar os antepassados",
            ),
        ),
    ),
    Rule(
        name="sorei_espiritos_antepassados",
        japanese_gate=("祖霊",),
        replacements=(
            (
                re.compile(r"\bespíritos dos antepassados\b", flags=re.IGNORECASE),
                "espíritos ancestrais",
            ),
            (
                re.compile(r"\bespírito dos antepassados\b", flags=re.IGNORECASE),
                "espírito ancestral",
            ),
            (
                re.compile(r"\bos antepassados ficarão furiosos\b", flags=re.IGNORECASE),
                "os espíritos ancestrais ficarão furiosos",
            ),
            (
                re.compile(r"\bos antepassados ficam furiosos\b", flags=re.IGNORECASE),
                "os espíritos ancestrais ficam furiosos",
            ),
            (
                re.compile(r"\bos antepassados se irritam\b", flags=re.IGNORECASE),
                "os espíritos ancestrais se irritam",
            ),
        ),
    ),
    Rule(
        name="goshusen_honorific",
        japanese_gate=("御先祖",),
        replacements=(
            (
                re.compile(r"\bantepassados venerados\b", flags=re.IGNORECASE),
                "antepassados a quem se faz sufrágio",
            ),
        ),
    ),
)


def has_ancestor_terms(japanese_text: str) -> bool:
    markers = ("祖霊", "先祖", "祖先", "御先祖", "祀")
    return any(marker in japanese_text for marker in markers)


def apply_sorei(pt_text: str, japanese_text: str) -> tuple[str, list[Change]]:
    if not has_ancestor_terms(japanese_text):
        return pt_text, []

    findings: list[Change] = []
    new_text = pt_text
    for rule in RULES:
        if not _gate(japanese_text, rule):
            continue
        updated, batch = apply_rule_list(new_text, rule)
        findings.extend(batch)
        new_text = updated
    return new_text, findings


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply individualized 祖霊/先祖/祖先 glossary fixes.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    planned = []

    for pair in pair_entries(load_entries()):
        japanese_text = read_entry_text(pair.jp)
        if not has_ancestor_terms(japanese_text):
            continue
        pt_path = permanent_pt_path(pair.pt)
        pt_text = pt_path.read_text(encoding="utf-8")
        new_text, findings = apply_sorei(pt_text, japanese_text)
        if not findings or new_text == pt_text:
            continue
        planned.append(
            {
                "pt_entry_id": pair.pt.get("entry_id"),
                "jp_entry_id": pair.jp.get("entry_id"),
                "entry_type": pair.pt.get("entry_type"),
                "title": pair.pt.get("title"),
                "source_category": pair.pt.get("source_category"),
                "source_date": pair.pt.get("source_date"),
                "pt_path": str(pt_path.relative_to(PROJECT_ROOT)),
                "jp_has_sorei": "祖霊" in japanese_text,
                "jp_has_senzo": "先祖" in japanese_text,
                "jp_has_sosen": "祖先" in japanese_text,
                "findings": [
                    {
                        "rule": change.rule,
                        "pattern": change.pattern,
                        "replacement": change.replacement,
                        "count": change.count,
                    }
                    for change in findings
                ],
                "_new_text": new_text,
            }
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = args.output_dir / "individual_sorei_batch.jsonl"
    with report_path.open("w", encoding="utf-8") as file:
        for row in planned:
            public_row = {key: value for key, value in row.items() if not key.startswith("_")}
            file.write(json.dumps(public_row, ensure_ascii=False, sort_keys=True) + "\n")

    backup_path = None
    if args.apply and planned:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_path = args.output_dir / f"individual_sorei_batch_{timestamp}_before.tar.gz"
        with tarfile.open(backup_path, "w:gz") as tar:
            for row in planned:
                path = PROJECT_ROOT / row["pt_path"]
                tar.add(path, arcname=row["pt_path"])
        for row in planned:
            path = PROJECT_ROOT / row["pt_path"]
            path.write_text(row["_new_text"], encoding="utf-8")

    rule_counts = Counter()
    for row in planned:
        for finding in row["findings"]:
            rule_counts[finding["rule"]] += finding["count"]

    print(f"mode={'apply' if args.apply else 'dry-run'} texts={len(planned)} replacements={sum(rule_counts.values())}")
    print("rules=" + json.dumps(dict(rule_counts), ensure_ascii=False, sort_keys=True))
    print(f"report={report_path}")
    if backup_path:
        print(f"backup={backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
