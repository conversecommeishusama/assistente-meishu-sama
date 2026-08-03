"""Testes de pós-processamento da pipeline v2."""

import unittest

from goshinsho.pipeline.format import strip_academic_opening
from goshinsho.pipeline.prompts import doctrinal_instructions


class PipelineFormatTests(unittest.TestCase):
    def test_strips_com_base_nos_trechos(self):
        raw = "Com base nos trechos fornecidos, Meishu-Sama menciona o ikebana."
        self.assertEqual(
            strip_academic_opening(raw),
            "Meishu-Sama menciona o ikebana.",
        )

    def test_preserves_inference_label(self):
        raw = "Meishu-Sama ensina sobre flores.\n\nInferência: talvez exista em outro texto."
        out = strip_academic_opening(raw)
        self.assertIn("Inferência", out)
        self.assertIn("flores", out)

    def test_preserves_inference_at_opening(self):
        raw = "Inferência: com base nos trechos sobre purificação, pode-se relacionar ao pulmão."
        out = strip_academic_opening(raw)
        self.assertIn("Inferência", out)
        self.assertIn("pulmão", out)

    def test_deep_mode_requires_analysis_structure(self):
        deep = doctrinal_instructions(direct=False, fontes=["Koza 2", "Koza 5"])
        self.assertIn("MODO APROFUNDADO", deep)
        self.assertIn("### Análise", deep)
        self.assertIn("Compreensão aplicada", deep)
        self.assertNotIn("MODO DIRECTO", deep)

    def test_direct_mode_is_in_depth_with_confirmatory_citation(self):
        # 2026-07-30: modo directo deixou de ser "sem citações" -- passou a
        # exigir citação confirmatória por tema (mesma mudança aplicada ao
        # modo agêntico, ver agentic_search.py SYSTEM_PROMPT_REGRA9_CITACOES).
        direct = doctrinal_instructions(direct=True)
        self.assertIn("MODO DIRECTO", direct)
        self.assertNotIn("### Análise", direct)
        self.assertIn("citação confirmatória", direct.lower())
        self.assertIn("proibido", direct.lower())
        self.assertIn("nuances", direct.lower())
        self.assertIn("PROFUNDIDADE E EXTENSÃO", direct)
        self.assertNotIn("parágrafos curtos bastam", direct.lower())

    def test_deep_mode_builds_on_direct_with_citations(self):
        deep = doctrinal_instructions(direct=False, fontes=["Koza 2", "Koza 5"])
        self.assertIn("modo directo aprofundado", deep.lower())
        self.assertIn("mesmo ensino aprofundado", deep.lower())


if __name__ == "__main__":
    unittest.main()
