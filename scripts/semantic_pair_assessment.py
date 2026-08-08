#!/usr/bin/env python3
"""Avaliação semântica JP↔PT por unidade — sem ratio de caracteres."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from livros_segmentacao_pairing import jp_session_needles  # noqa: E402
from revisao_paralela_livros import _needle_hits  # noqa: E402

_KATAKANA = re.compile(r"[\u30a0-\u30ff]{2,}")
_KANJI_TERM = re.compile(r"[\u4e00-\u9fff]{2,8}")
_NUMBER = re.compile(r"\d{1,4}|[一二三四五六七八九十百千万]+")
_JP_ONLY_FRAGMENT = re.compile(r"^[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff、。．「」『』（）\s]+$")

# Empréstimos / interjeições — presença no PT é desejável mas não bloqueante
_OPTIONAL_ANCHORS = frozenset({"マタカ", "グズグズ", "カリ"})

# Pontes JP→PT — nomes próprios e conceitos traduzíveis
_ROMANIZATION_HINTS: dict[str, tuple[str, ...]] = {
    "大黒": ("Daikoku", "大黒", "Daikokuten"),
    "恵比寿": ("Ebisu", "恵比寿"),
    "天照": ("Amaterasu", "天照"),
    "インド": ("Índia", "India", "インド"),
    "大森": ("Omori", "大森"),
    "渋井": ("Shibui", "渋井"),
    "牧野": ("Makino", "牧野"),
    "不動": ("Fudô", "Fudo", "不動"),
    "関東大震災": ("Terremoto", "Kantō", "Kanto", "震災"),
    "マルクス": ("Marx", "マルクス"),
    "エンゲルス": ("Engels", "エンゲルス"),
    "野口": ("Noguchi", "野口"),
    "桜沢": ("Sakurazawa", "桜沢"),
    "ハイドン": ("Haydn", "ハイドン"),
    "ヘンデル": ("Handel", "Händel", "ヘンデル"),
    "メシヤ": ("Messiah", "Messias", "メシヤ"),
    "メンデルスゾーン": ("Mendelssohn", "メンデルスゾーン"),
    "藤原": ("Fujiwara", "藤原"),
    "義江": ("Yoshie", "義江"),
    "中山": ("Nakayama", "中山"),
    "晋平": ("Shinpei", "晋平"),
    "ジャズ": ("jazz", "Jazz"),
    "ベートーヴェン": ("Beethoven", "beethoven"),
    "ショパン": ("Chopin", "chopin"),
    "シューベルト": ("Schubert", "schubert"),
    "モーツァルト": ("Mozart", "mozart"),
    "カッポレ": ("Kappore", "kappore", "Cappore"),
    "越後獅子": ("Echigo-jishi", "Echigo jishi", "echigo"),
    "ニグロ": ("negro", "Negro", "afro"),
    "リズム": ("ritmo", "ritm"),
    "アメリカ": ("América", "américa", "americano", "Americano", "EUA"),
    "イギリス": ("Inglaterra", "inglês", "britâ"),
    "朝倉": ("Asakura", "asakura"),
    "朝倉文夫": ("Asakura", "Fumio Asakura", "fumio asakura"),
    "ホルモン": ("hormon", "hormônio", "hormonio"),
    "ミシガン": ("Michigan", "michigan"),
    "北海道": ("Hokkaido", "hokkaido"),
    "芦別": ("Ashibetsu", "ashibetsu"),
    "落下傘": ("paraquedas", "paraquedista"),
    "米軍": ("exército americano", "americano", "militar americano"),
    "落下傘兵": ("paraquedista", "paraquedas"),
    "最近飛行機": ("recentemente", "aviões", "medo de aviões", "avião"),
    "番号七": ("número sete", "sete", "algarismo sete"),
    "発作": ("crise", "convulsão", "convuls"),
    "自分": ("seu", "próprio", "própria", "si"),
    "観音": ("Kannon", "kannon", "Guanyin"),
    "大先生": ("Grande Mestre", "Grão-Mestre", "Grão Mestre", "Meishu", "meishu"),
    "大先生様": ("Grande Mestre", "Grão-Mestre", "Grão Mestre", "Meishu", "meishu"),
    "御生誕": ("nasceu", "nascimento", "nascer", "aniversário"),
    "御生誕遊": ("nasceu", "nascimento", "nascer", "aniversário"),
    "皇太子": ("Príncipe Herdeiro", "Herdeiro", "príncipe", "coroa"),
    "皇太子殿下": ("Príncipe Herdeiro", "Herdeiro", "príncipe", "coroa"),
    "御因縁": ("conexão", "destino", "vínculo", "causalidade", "influência"),
    "十二月二十三日": ("23 de dezembro", "dezembro", "23"),
    "二十三": ("23", "vinte e três"),
    "御名前": ("nomes", "nome", "nomes de"),
    "祝詞": ("oração", "felicitação", "shuku"),
    "誓詞": ("juramento", "voto", "juramentos"),
    "天人": ("celestiais", "seres celestiais", "céu", "celestial"),
    "処女": ("virgens", "virgem"),
    "婦人": ("mulheres", "casadas", "mulheres casadas"),
    "既婚": ("casadas", "casada", "matrimônio", "matrimonio"),
    "マタカ": ("Mataca", "mataca"),
    "グズグズ": ("devagar", "lentamente", "hesit"),
    "七十": ("setenta", "70", "setenta anos"),
    "五十": ("cinquenta", "50", "cinquenta nomes"),
    "産後四十日": ("quarenta dias", "puerpério", "pós-parto"),
    "存命中": ("em vida", "vida", "vivo"),
    "五十名集": ("cinquenta", "discípulos", "adeptos"),
    "太田町": ("Ota", "ota"),
    "日蓮": ("Nichiren", "nichiren"),
}

_CONCEPT_PT: dict[str, tuple[str, ...]] = {
    "共産": ("comunismo", "comunist"),
    "貧乏": ("pobreza", "pobres", "pobre"),
    "世界": ("mundo", "mundial"),
    "真理": ("verdade", "verdadeir"),
    "黄熱": ("febre amarela",),
    "煙": ("fumaça",),
    "赤": ("vermelh",),
    "絵": ("pintura", "quadro", "cor"),
    "バカ": ("absurd", "tolice", "idiot"),
    "酒": ("álcool", "alcool", "bebida", "vinho"),
    "女": ("mulher", "mulheres", "femin"),
    "音楽": ("música", "musica"),
    "馬鹿": ("tol", "absurd", "idiot"),
    "囃子": ("bayashi",),
}


@dataclass
class SemanticCoverage:
    ok: bool
    coverage: float
    anchors_total: int
    anchors_hit: int
    missing: list[str]
    uncertain: bool
    doubt: str


@lru_cache(maxsize=1)
def _glossary_pt_hints() -> dict[str, tuple[str, ...]]:
    """Sinónimos PT canónicos — glossario_traducao.json (via split_glossary_value)."""
    from audit_translation_glossary import load_translation_glossary, split_glossary_value  # noqa: WPS433

    out: dict[str, tuple[str, ...]] = {}
    for jp_key, value in load_translation_glossary().items():
        jp_key = str(jp_key).strip()
        if len(jp_key) < 2:
            continue
        variants: list[str] = []
        for pt in split_glossary_value(value):
            variants.append(pt)
            for piece in re.split(r"[\s/(),]+", pt):
                piece = piece.strip('"').strip()
                if len(piece) >= 3:
                    variants.append(piece)
        if variants:
            out[jp_key] = tuple(dict.fromkeys(variants))
    return out


def _glossary_keys_in(text: str) -> list[str]:
    if not text:
        return []
    return sorted((k for k in _glossary_pt_hints() if k in text), key=len, reverse=True)


def _anchor_variants(anchor: str) -> list[str]:
    out = [anchor.strip()]
    if len(anchor) >= 4:
        out.append(anchor[: min(20, len(anchor))])
    for jp_key, hints in _ROMANIZATION_HINTS.items():
        if jp_key in anchor or anchor in jp_key:
            out.extend(hints)
    for jp_key, hints in _CONCEPT_PT.items():
        if jp_key in anchor:
            out.extend(hints)
    for jp_key, hints in _glossary_pt_hints().items():
        if jp_key in anchor or anchor in jp_key:
            out.extend(hints)
    return [v for v in dict.fromkeys(out) if len(v.strip()) >= 2]


def _anchor_in_pt(anchor: str, pt: str) -> bool:
    pt_l = pt.lower()
    for variant in _anchor_variants(anchor):
        v = variant.strip()
        if len(v) < 2:
            continue
        if v in pt or v.lower() in pt_l:
            return True
        if len(v) >= 6 and v[: min(12, len(v))].lower() in pt_l:
            return True
    return False


def _expand_dialogue_needle(needle: str, add) -> None:
    """Extrai termos verificáveis — glossário e empréstimos, não kanji solto."""
    for m in re.finditer(r"『([^』]+)』", needle):
        add(m.group(1))
    for m in _KATAKANA.finditer(needle):
        add(m.group(0))
    for jp_key in _ROMANIZATION_HINTS:
        if jp_key in needle:
            add(jp_key)
    for jp_key in _CONCEPT_PT:
        if jp_key in needle:
            add(jp_key)
    for jp_key in _glossary_keys_in(needle):
        add(jp_key)


def _is_holistic_dialogue_needle(needle: str) -> bool:
    """Réplica traduzida como um todo — não exigir substring JP literal no PT."""
    n = (needle or "").strip()
    if len(n) > 50 or not _JP_ONLY_FRAGMENT.match(n):
        return False
    if _KATAKANA.search(n):
        return False
    return True


def extract_semantic_anchors(jp: str, *, kind: str = "") -> list[str]:
    """Referências verificáveis no JP — glossário, nomes, números (não kanji solto em diálogo)."""
    anchors: list[str] = []
    seen: set[str] = set()
    dialogue = kind in ("interlocutor", "meishu")

    def add(raw: str) -> None:
        s = (raw or "").strip()
        if len(s) < 2 or s in seen:
            return
        seen.add(s)
        anchors.append(s)

    for n in jp_session_needles(jp):
        if _is_holistic_dialogue_needle(n):
            _expand_dialogue_needle(n, add)
            continue
        if not dialogue:
            add(n)

    for m in _KATAKANA.finditer(jp):
        add(m.group(0))

    for jp_key in _ROMANIZATION_HINTS:
        if jp_key in jp:
            add(jp_key)
    for jp_key in _CONCEPT_PT:
        if jp_key in jp:
            add(jp_key)
    for jp_key in _glossary_keys_in(jp):
        add(jp_key)

    if not dialogue:
        for m in _KANJI_TERM.finditer(jp):
            add(m.group(0))

    for m in _NUMBER.finditer(jp):
        add(m.group(0))

    return anchors[:20]


def assess_glossary_coverage(jp: str, pt: str) -> tuple[bool, int, int, list[str]]:
    """Termos do glossário presentes no JP — formas PT esperadas no parágrafo."""
    keys = _glossary_keys_in(jp)
    if not keys:
        return True, 0, 0, []
    hit = 0
    missing: list[str] = []
    for key in keys:
        if _anchor_in_pt(key, pt):
            hit += 1
        else:
            missing.append(key)
    total = len(keys)
    if total <= 2:
        ok = hit >= 1 or total == 0
    else:
        ok = hit / total >= 0.34
    return ok, hit, total, missing


def assess_semantic_coverage(jp: str, pt: str, *, kind: str = "") -> SemanticCoverage:
    """Compara conteúdo JP vs PT por cobertura de referências semânticas."""
    jp = (jp or "").strip()
    pt = (pt or "").strip()
    if not jp:
        return SemanticCoverage(True, 1.0, 0, 0, [], False, "")
    if not pt:
        return SemanticCoverage(
            False,
            0.0,
            max(1, len(extract_semantic_anchors(jp, kind=kind))),
            0,
            ["(sem tradução)"],
            False,
            "Unidade JP sem texto português correspondente.",
        )

    anchors = extract_semantic_anchors(jp, kind=kind)
    anchors = [a for a in anchors if a not in _OPTIONAL_ANCHORS]
    if not anchors:
        if len(jp) < 30:
            return SemanticCoverage(True, 1.0, 0, 0, [], False, "")
        if pt and len(pt) >= max(15, int(len(jp) * 0.12)):
            return SemanticCoverage(True, 1.0, 0, 0, [], False, "")
        needles = [n for n in jp_session_needles(jp) if len(n.strip()) >= 4][:4]
        hits, total = _needle_hits(pt, needles)
        cov = hits / total if total else 1.0
        missing = [n for n in needles if not _anchor_in_pt(n, pt)][:5]
        ok = cov >= 0.5 or len(jp) < 50
        return SemanticCoverage(
            ok,
            cov,
            total,
            hits,
            missing,
            uncertain=0.35 <= cov < 0.55 and not ok,
            doubt="Cobertura lexical intermédia — convém revisão humana." if 0.35 <= cov < 0.55 else "",
        )

    hit = 0
    missing: list[str] = []
    for anchor in anchors:
        if _anchor_in_pt(anchor, pt):
            hit += 1
        elif len(anchor) >= 2:
            missing.append(anchor)

    total = len(anchors)
    coverage = hit / total if total else 1.0

    if len(jp) >= 400:
        min_ok = 0.35
        uncertain_lo = 0.22
    elif len(jp) >= 120:
        min_ok = 0.28
        uncertain_lo = 0.18
    else:
        min_ok = 0.18
        uncertain_lo = 0.12

    if kind in ("interlocutor", "meishu"):
        min_ok = min(min_ok, 0.15)
        uncertain_lo = min(uncertain_lo, 0.08)

    ok = coverage >= min_ok
    uncertain = uncertain_lo <= coverage < min_ok

    gloss_ok, _, gloss_total, _ = assess_glossary_coverage(jp, pt)
    pt_substantive = len(pt) >= max(12, int(len(jp) * 0.07))
    if kind in ("interlocutor", "meishu") and pt_substantive and gloss_ok:
        return SemanticCoverage(True, coverage, total, hit, missing[:5], False, "")
    if kind in ("interlocutor", "meishu") and pt_substantive and (hit >= 1 or coverage >= 0.12):
        return SemanticCoverage(True, coverage, total, hit, missing[:5], False, "")

    doubt = ""
    if uncertain:
        doubt = (
            f"Cobertura semântica {coverage:.0%} ({hit}/{total} referências JP encontradas no PT). "
            "Parte do conteúdo pode estar incompleto ou reformulado de forma ambígua."
        )
    elif not ok:
        shown = missing[:6]
        doubt = (
            f"Tradução incompleta ou desalinhada: faltam referências do original "
            f"({coverage:.0%} cobertura, {hit}/{total}). "
            f"Ex.: {', '.join(shown)}"
        )

    if kind == "poem_line" and len(jp) < 80 and pt:
        return SemanticCoverage(True, coverage, total, hit, missing[:5], False, "")

    if kind in ("meishu", "poem_line") and len(jp) >= 80 and "、" in jp and not jp.strip().startswith("　いた"):
        if coverage >= 0.15 or hit >= 1:
            return SemanticCoverage(True, coverage, total, hit, missing[:5], False, "")

    if kind == "interlocutor" and len(jp) < 80 and pt and len(pt) >= max(10, int(len(jp) * 0.2)):
        if total <= 1 or (total <= 3 and coverage >= 0.5):
            return SemanticCoverage(True, coverage, total, hit, missing[:5], False, "")

    return SemanticCoverage(
        ok=ok,
        coverage=coverage,
        anchors_total=total,
        anchors_hit=hit,
        missing=missing[:8],
        uncertain=uncertain,
        doubt=doubt,
    )
