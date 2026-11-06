"""Testes da expansão por obra e seleção para o LLM."""

import unittest

from goshinsho.pipeline.retrieve import (
    LLM_MAX_DIRECT,
    _expand_entries_by_score,
    _select_for_llm,
    retrieve,
)
from goshinsho.pipeline.state import build_state


class RetrieveExpansionTests(unittest.TestCase):
    def test_asma_includes_abdomen_in_default_direct(self):
        state = build_state("onde ministrar johrei na asma?", response_mode="direct")
        chunks, _ = retrieve(state)
        joined = " ".join(chunks).lower()
        self.assertGreaterEqual(len(chunks), 10)
        self.assertLessEqual(len(chunks), LLM_MAX_DIRECT)
        self.assertTrue(
            any(kw in joined for kw in ("lateral", "laterais", "abdômen", "abdomen", "intercost")),
            f"Expected abdomen/intercostal teaching: {joined[:500]}",
        )

    def test_expand_adds_siblings_from_same_entry(self):
        state = build_state("ikebana", response_mode="direct")
        base_c, base_m = retrieve(state, max_output=8)
        if not base_c:
            self.skipTest("no chunks")
        expanded_c, expanded_m = _expand_entries_by_score(
            base_c,
            base_m,
            query=state.search_query,
        )
        self.assertGreaterEqual(len(expanded_c), len(base_c))

    def test_select_allows_multiple_from_same_entry_for_specific_query(self):
        chunks = [f"chunk {i} about asma johrei lateral" for i in range(8)]
        metas = [{"entry_id": "same-book", "fonte": "Curso de Johrei 5", "chunk_index": i} for i in range(8)]
        selected_c, selected_m = _select_for_llm(
            chunks,
            metas,
            query="onde ministrar johrei na asma?",
            max_output=6,
        )
        entries = {m.get("entry_id") for m in selected_m}
        self.assertEqual(len(selected_c), 6)
        self.assertEqual(len(entries), 1)


if __name__ == "__main__":
    unittest.main()
