#!/usr/bin/env python3
"""Run all glossary passes through round 3 and re-audit."""

from __future__ import annotations

import subprocess
import sys

SCRIPTS = Path = __import__("pathlib").Path(__file__).resolve().parents[1] / "scripts"

STEPS = [
    "apply_comprehensive_glossary_batch.py",
    "apply_individual_glossary_gated.py",
    "apply_individual_term_kannon_sama.py",
    "apply_individual_term_johrei.py",
    "apply_individual_term_keirin.py",
    "apply_individual_term_sorei.py",
    "apply_individual_term_haisetsu.py",
    "apply_individual_term_chusha.py",
    "apply_individual_term_kumori.py",
    "apply_individual_term_tengoku.py",
    "apply_individual_term_shinrei.py",
    "apply_individual_term_taitai.py",
    "apply_comprehensive_glossary_batch_round2.py",
    "apply_glossary_round3_final.py",
    "apply_portuguese_grammar_pass.py",
]

AUDIT = ["audit_translation_glossary.py", "--permanent-sources"]


def main() -> int:
    py = sys.executable
    for script in STEPS:
        print(f"\n=== {script} ===")
        r = subprocess.run([py, script, "--apply"], cwd=SCRIPTS)
        if r.returncode:
            return r.returncode
    print("\n=== audit ===")
    r = subprocess.run([py] + AUDIT, cwd=SCRIPTS)
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
