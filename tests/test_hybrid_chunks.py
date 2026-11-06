import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from build_clean_large_indexes import split_chunks, split_teaching_units  # noqa: E402


def test_split_teaching_units_respects_hash_t():
    text = "Prefácio do livro.\n\n#T Ensinamento A\nCorpo A longo.\n\n#T Ensinamento B\nCorpo B."
    units = split_teaching_units(text)
    assert len(units) == 3
    assert units[0].startswith("Prefácio")
    assert units[1].startswith("#T Ensinamento A")
    assert units[2].startswith("#T Ensinamento B")


def test_hybrid_never_mixes_two_teachings_in_one_chunk():
    a = "A" * 2000
    b = "B" * 2000
    text = f"#T Primeiro\n{a}\n\n#T Segundo\n{b}"
    chunks = split_chunks(text, max_chars=3200, overlap_chars=100)
    assert len(chunks) >= 2
    for chunk in chunks:
        has_first = "AAAA" in chunk
        has_second = "BBBB" in chunk
        assert not (has_first and has_second)


def test_long_single_teaching_can_split():
    body = "Parágrafo. " * 800
    text = f"#T Ensinamento Longo\n{body}"
    chunks = split_chunks(text, max_chars=3200, overlap_chars=120)
    assert len(chunks) > 1
    assert chunks[0].startswith("#T Ensinamento Longo")
