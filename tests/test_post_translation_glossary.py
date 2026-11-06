import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from post_translation_glossary import apply_post_translation_glossary, glossary_qa_issues  # noqa: E402
from run_deepseek_revision_pilot import load_glossary  # noqa: E402


def test_paragraph_glossary_fixes_linha_espiritual():
    glossary = load_glossary()
    jp = "霊線は人と人を結ぶ。"
    pt = "A linha espiritual liga as pessoas."
    out, report = apply_post_translation_glossary(jp, pt, glossary)
    assert "elo espiritual" in out.lower() or "Elo espiritual" in out
    assert report["fixes_applied"] >= 1


def test_audit_flags_missing_mandatory_term():
    glossary = {"メシヤ教": "Igreja Messiânica Mundial"}
    jp = "メシヤ教の教え。"
    pt = "O ensinamento da religião."
    out, report = apply_post_translation_glossary(jp, pt, glossary)
    assert "Igreja Messiânica" not in out
    assert report["residual_terms"] >= 1
    assert glossary_qa_issues(report) == ["glossary_residual_1"]
