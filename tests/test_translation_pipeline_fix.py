"""Regressão: layout sem duplicação + QA no texto final."""

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from retranslate_core import strip_metadata  # noqa: E402
from retranslate_qa import pt_text_for_ratio, validate_translation  # noqa: E402
from translation_protocol_core import (  # noqa: E402
    _split_paragraphs,
    apply_layout_protocol,
    cleanup_prose_duplication,
    dedupe_repeated_paragraphs,
    dedupe_repeated_sentence_runs,
    reflow_pt_by_jp_blocks,
    repair_scrambled_prose_opening,
)


class TranslationPipelineFixTests(unittest.TestCase):
    def test_reflow_does_not_duplicate_prose_without_ficha(self):
        jp_path = PROJECT_ROOT / (
            "data/publication_sources/jp/agricultura-natural/"
            "30-de-janeiro-de-1945-o-descompasso-do-aprendizado-publication-jp-1759.txt"
        )
        bad_path = PROJECT_ROOT / (
            "reports/translation_review/translation_mass/20260620T190000Z/corpus/"
            "data/publication_sources/jp/agricultura-natural/"
            "30-de-janeiro-de-1945-o-descompasso-do-aprendizado-publication-jp-1759.txt"
        )
        if not bad_path.exists():
            self.skipTest("mass corpus sample missing")

        jp_body = strip_metadata(jp_path.read_text(encoding="utf-8"))
        draft = "\n\n".join(_split_paragraphs(bad_path.read_text(encoding="utf-8"))[:7])

        once = reflow_pt_by_jp_blocks(jp_body, draft)
        twice = apply_layout_protocol(once, jp_body=jp_body, jp_raw=jp_path.read_text(encoding="utf-8"))

        self.assertLessEqual(len(twice), len(once) * 1.15, "layout must not duplicate body")
        self.assertLess(len(twice) / len(jp_body), 8.0, "ratio after single layout should be sane")

    def test_dedupe_strips_repeated_paragraphs(self):
        text = "Alpha paragraph one.\n\nBeta paragraph two.\n\nAlpha paragraph one.\n\nGamma."
        out = dedupe_repeated_paragraphs(text, min_chars=10)
        self.assertEqual(out.count("Alpha paragraph one."), 1)

    def test_pt_text_for_ratio_skips_header(self):
        pt = "Título\n\nEiko nº 1, publicado em 1 de janeiro do ano 26 (1951)\n\nCorpo do artigo aqui."
        body = pt_text_for_ratio(pt)
        self.assertNotIn("publicado em", body)
        self.assertIn("Corpo do artigo", body)

    def test_short_eiko_ratio_threshold(self):
        jp = "x" * 500
        pt = (
            "Título\n\nEiko nº 1, publicado em 1 de janeiro do ano 26 (1951)\n\n"
            + ("Palavra " * 180)
        )
        _, qa = validate_translation(jp, pt)
        ratio_issues = [i for i in qa.issues if i.startswith("expansao_suspeita")]
        self.assertEqual(ratio_issues, [], qa.issues)

    def test_cleanup_fixes_agriculture_mass_corpus(self):
        jp_path = PROJECT_ROOT / (
            "data/publication_sources/jp/agricultura-natural/"
            "30-de-janeiro-de-1945-o-descompasso-do-aprendizado-publication-jp-1759.txt"
        )
        jp_body = strip_metadata(jp_path.read_text(encoding="utf-8"))

        duplicated = (
            "Finalmente, há algo que requer atenção especial. "
            "No entanto, no ano passado distribuí esta edição especial ao ministro. "
            "Além disso, as importações de arroz aumentam a cada ano, e atualmente importamos "
            "mais de vinte milhões de koku por ano, pagando mais de cem bilhões de ienes por isso. "
            "Além disso, as importações de arroz aumentam a cada ano, e atualmente importamos "
            "mais de vinte milhões de koku por ano, pagando mais de cem bilhões de ienes por elas."
        )
        cleaned = cleanup_prose_duplication(duplicated)
        laid_out = apply_layout_protocol(cleaned, jp_body=jp_body, jp_raw=jp_path.read_text(encoding="utf-8"))

        self.assertFalse(laid_out.lower().startswith("finalmente,"))
        self.assertLess(len(cleaned), len(duplicated))
        ratio = len(pt_text_for_ratio(laid_out)) / len(jp_body)
        self.assertLess(ratio, 4.0, f"ratio still high: {ratio:.2f}")

    def test_dedupe_repeated_sentence_runs(self):
        s1 = "Alpha one. Beta two. Gamma three."
        s2 = "Delta four. Alpha one. Beta two. Gamma three."
        out = dedupe_repeated_sentence_runs(f"{s1} {s2}")
        self.assertEqual(out.count("Alpha one."), 1)

    def test_repair_scrambled_prose_opening(self):
        scrambled = (
            "Finalmente, há algo especial. "
            "Outro parágrafo. "
            "No entanto, distribuí esta edição especial ao ministro."
        )
        out = repair_scrambled_prose_opening(scrambled)
        self.assertTrue(out.lower().startswith("no entanto, distribuí"))
        self.assertNotIn("finalmente,", out.lower()[:40])


if __name__ == "__main__":
    unittest.main()
