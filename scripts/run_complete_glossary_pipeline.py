#!/usr/bin/env python3
"""Run the complete glossary review pipeline without user prompts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = PROJECT_ROOT / "scripts"


STEPS = [
    ("comprehensive batch", [sys.executable, "apply_comprehensive_glossary_batch.py", "--apply"]),
    ("individual gated", [sys.executable, "apply_individual_glossary_gated.py", "--apply"]),
    ("individual 観音様", [sys.executable, "apply_individual_term_kannon_sama.py", "--apply"]),
    ("individual 浄霊", [sys.executable, "apply_individual_term_johrei.py", "--apply"]),
    ("individual 経綸", [sys.executable, "apply_individual_term_keirin.py", "--apply"]),
    ("individual 祖霊", [sys.executable, "apply_individual_term_sorei.py", "--apply"]),
    ("individual 排泄", [sys.executable, "apply_individual_term_haisetsu.py", "--apply"]),
    ("individual 注射", [sys.executable, "apply_individual_term_chusha.py", "--apply"]),
    ("individual 曇り", [sys.executable, "apply_individual_term_kumori.py", "--apply"]),
    ("individual 天国", [sys.executable, "apply_individual_term_tengoku.py", "--apply"]),
    ("individual 神霊", [sys.executable, "apply_individual_term_shinrei.py", "--apply"]),
    ("individual 体的", [sys.executable, "apply_individual_term_taitai.py", "--apply"]),
    ("source references", [sys.executable, "apply_source_reference_glossary_fixes.py", "--apply"]),
    ("comprehensive batch round 2", [sys.executable, "apply_comprehensive_glossary_batch_round2.py", "--apply"]),
    ("grammar pass 2", [sys.executable, "apply_portuguese_grammar_pass.py", "--apply"]),
    ("audit permanent", [sys.executable, "audit_translation_glossary.py", "--permanent-sources"]),
]


def main() -> int:
    for label, cmd in STEPS:
        print(f"\n{'=' * 60}\nSTEP: {label}\n{'=' * 60}")
        result = subprocess.run(cmd, cwd=SCRIPTS)
        if result.returncode != 0:
            print(f"FAILED: {label} (exit {result.returncode})")
            return result.returncode
    print("\nPipeline complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
