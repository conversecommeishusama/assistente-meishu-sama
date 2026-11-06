"""Testes das regras gerais de inferência no prompt."""

import unittest

from goshinsho.pipeline.prompts import doctrinal_instructions


class InferencePromptRulesTests(unittest.TestCase):
    def test_base_rules_include_inference_policy(self):
        text = doctrinal_instructions(direct=False, fontes=["Obra A"])
        self.assertIn("MEMÓRIA DO MODELO", text)
        self.assertIn("ASSUNTO ESPECÍFICO AUSENTE", text)
        self.assertIn("ROTULAGEM", text)
        self.assertIn("SEM PRESCRIÇÃO DE PONTES", text)

    def test_inference_labeling_is_mandatory(self):
        text = doctrinal_instructions(direct=True)
        self.assertIn("ROTULAGEM OBRIGATÓRIA", text)
        self.assertIn("não abordou directamente", text)
        text = doctrinal_instructions(direct=False, fontes=["Obra A"])
        self.assertNotIn("ABRANGÊNCIA TEMÁTICA", text)
        self.assertNotIn("pontos vitais de Johrei para uma doença", text.lower())


if __name__ == "__main__":
    unittest.main()
