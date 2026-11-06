import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from translation_header_parser import (  # noqa: E402
    enrich_entry_from_header,
    parse_translation_header,
    parse_pt_date_to_iso,
)


def test_parse_a1_new_format():
    text = """Gosuiji-roku nº 3, publicado em 25 de novembro do ano 26 da Era Showa (1951)

[1º de outubro]

Interlocutor: "..."
Meishu-Sama: ...
"""
    parsed = parse_translation_header(text)
    assert parsed is not None
    assert parsed.header_type == "A1"
    assert parsed.work_name == "Gosuiji-roku"
    assert parsed.issue_number == "3"
    assert parsed.display_title == "Gosuiji-roku nº 3"
    assert parsed.publication_date_iso == "1951-11-25"
    assert parsed.session_date == "1º de outubro"


def test_parse_a1_legacy_multiline():
    text = """Gosuiji-roku nº 3

『Gosuiji-roku』nº 3, publicado em 25 de novembro de 1951 (Showa 26)

[1º de outubro]
"""
    parsed = parse_translation_header(text)
    assert parsed is not None
    assert parsed.header_type == "A1"
    assert parsed.work_name == "Gosuiji-roku"
    assert parsed.issue_number == "3"
    assert parsed.display_title == "Gosuiji-roku nº 3"


def test_parse_a3_mioshie():
    text = """Mioshie-shū nº 1, publicado em 20 de setembro do ano 26 da Era Showa (1951)

[1º de agosto]

Interlocutor: caso
Meishu-Sama: instrução
"""
    parsed = parse_translation_header(text)
    assert parsed is not None
    assert parsed.header_type == "A3"
    assert parsed.work_name == "Mioshie-shū"
    assert parsed.session_date == "1º de agosto"


def test_parse_a2_supplement():
    text = """Gokōwa-roku (Suplemento)

Prefácio editorial.

**1º de janeiro do ano 23 da Era Showa (1948)**

(Poemas do Grão-Mestre para o Ano Novo)
"""
    parsed = parse_translation_header(text)
    assert parsed is not None
    assert parsed.header_type == "A2"
    assert parsed.work_name == "Gokōwa-roku (Suplemento)"
    assert parsed.session_date == "1º de janeiro do ano 23 da Era Showa (1948)"


def test_parse_a4_periodical():
    text = """**Uma Palavra ao Mestre Okada Michiaki: Sobre a Terapia Espiritual Sokohito**

Kyusei nº 61, publicado em 6 de janeiro do ano 25 da Era Showa (1950)

Corpo do artigo.
"""
    parsed = parse_translation_header(text)
    assert parsed is not None
    assert parsed.header_type == "A4"
    assert parsed.article_title.startswith("Uma Palavra")
    assert parsed.publication_source == "Kyusei"
    assert parsed.issue_number == "61"
    assert parsed.publication_date_iso == "1950-01-06"


def test_parse_a4_accepts_legacy_no():
    text = """Título do artigo

Kyusei n.o 61, publicado em 6 de janeiro do ano 25 da Era Showa (1950)
"""
    parsed = parse_translation_header(text)
    assert parsed is not None
    assert parsed.issue_number == "61"


def test_enrich_entry_updates_title_and_date():
    entry = {
        "body": """Gosuiji-roku nº 3, publicado em 25 de novembro do ano 26 da Era Showa (1951)

[1º de outubro]
Corpo.
""",
        "title": "19511125 - Gosuiji-roku nº 3",
        "source_date": "",
        "display_source_name": "19511125 - Gosuiji-roku nº 3",
        "display_source_name_pt": "19511125 - Gosuiji-roku nº 3",
    }
    enriched = enrich_entry_from_header(entry)
    assert enriched["title"] == "Gosuiji-roku nº 3"
    assert enriched["source_date"] == "1951-11-25"
    assert enriched["session_date"] == "1º de outubro"
    assert enriched["header_type"] == "A1"


def test_parse_pt_date_to_iso_year_only():
    assert parse_pt_date_to_iso("ano 26 da Era Showa (1951)") == "1951"


def test_normalize_session_date_adds_western_year():
    from translation_header_parser import (
        normalize_session_bracket_line,
        rebuild_translation_header,
    )

    line = "[5 de novembro do ano 27 da Era Showa]"
    fixed = normalize_session_bracket_line(line)
    assert fixed == "[5 de novembro do ano 27 da Era Showa (1952)]"


def test_rebuild_mioshie_header_session_date():
    from translation_header_parser import rebuild_translation_header

    jp = Path(__file__).resolve().parents[1] / "textos_japones/19521215-御教え集16号.txt"
    if not jp.exists():
        return
    jp_raw = jp.read_text(encoding="utf-8")
    pt = """Mioshie-shū nº 16, publicado em 15 de dezembro do ano 27 da Era Showa (1952)

[5 de novembro do ano 27 da Era Showa]

Corpo do texto."""
    out = rebuild_translation_header(jp_raw, pt, jp_path=str(jp))
    assert "[5 de novembro do ano 27 da Era Showa (1952)]" in out
    assert out.count("Mioshie-shū nº 16") == 1
