#!/usr/bin/env python3
"""Revisão linha a linha JP→PT — protocolo A→D (pareamento, busca exaustiva, tradução)."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from acervo_work_paths import ROOT, work_root  # noqa: E402
from apply_manual_livros_segmentacao import Boundary, split_by_anchors  # noqa: E402
from livros_segmentacao_pairing import find_pt_by_needles, jp_session_needles, split_pt_chunks  # noqa: E402
from qa_dialogue_annotation import parse_qa_turns, verify_qa_alignment  # noqa: E402
from revisao_paralela_livros import (  # noqa: E402
    ISSUE_ALIGN,
    ISSUE_CJK,
    ISSUE_INCOMPLETE,
    ISSUE_NO_PT,
    SNAPSHOT_ROOT,
    _needle_hits,
    review_trecho,
)

CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff]")
JP_TAIL_LINE_RE = re.compile(
    r"^[\u4e00-\u9fff\u3000-\u303f\u30a0-\u30ff][\u4e00-\u9fff\u3000-\u303f\u30a0-\u30ff\d（）\(\)月日曜・\s]{0,55}$"
)
MASS_CORPUS = (
    ROOT
    / "reports/translation_review/translation_mass/20260620T190000Z/corpus/textos_portugues"
)
PT_ORFAOS = ROOT / "reports/pt_orfaos_trabalho"
SPEC_DIR = ROOT / "reports/livros_trabalho/segmentacao_manual"

_SLICE_CACHE: dict[str, dict[str, Any]] = {}
_client: Any = None


@dataclass
class SearchResult:
    pt_text: str | None = None
    source: str = ""
    log: list[str] = field(default_factory=list)


@dataclass
class SegmentProtocolResult:
    jp_slice: str
    pt_slice: str
    phase_log: list[str] = field(default_factory=list)
    turns_fixed_corpus: int = 0
    turns_translated: int = 0
    search_log: list[str] = field(default_factory=list)
    blocking: bool = True
    slice_invalid: bool = False
    persist_blocked: bool = False
    review_issues: list[str] = field(default_factory=list)
    review_notes: list[str] = field(default_factory=list)


def needs_pt_work(text: str) -> bool:
    t = sanitize_turn_text(text or "")
    if not t:
        return True
    return has_blocking_cjk(t)


def has_blocking_cjk(text: str) -> bool:
    """CJK bloqueante: kana ou blocos kanji longos (não nomes 2–3 kanji)."""
    if re.search(r"[\u3040-\u309f\u30a0-\u30ff]", text):
        return True
    return bool(re.search(r"[\u4e00-\u9fff]{4,}", text))


def sanitize_turn_text(text: str) -> str:
    """Remove cabeçalhos JP colados no fim de parágrafos PT."""
    t = (text or "").strip()
    if not t:
        return t
    lines = t.splitlines()
    while lines and JP_TAIL_LINE_RE.match(lines[-1].strip()):
        lines.pop()
    t = "\n".join(lines).strip()
    m = re.search(r"\n([\u4e00-\u9fff][^\n]{0,50})$", t)
    if m and JP_TAIL_LINE_RE.match(m.group(1).strip()):
        t = t[: m.start()].strip()
    return t


def trim_pt_chunk_leakage(text: str) -> str:
    """Corta vazamento do trecho JP seguinte no fim do chunk PT."""
    t = (text or "").strip()
    if not t:
        return t
    lines = t.splitlines()
    while lines:
        last = lines[-1].strip()
        if last and JP_TAIL_LINE_RE.match(last):
            lines.pop()
        else:
            break
    return "\n\n".join(p.strip() for p in re.split(r"\n\s*\n", "\n".join(lines)) if p.strip()).strip()


def invalidate_slice_cache(filename: str | None = None) -> None:
    from line_by_line_slices import invalidate_slice_cache as _inv  # noqa: WPS433

    _inv(filename)
    if filename:
        _SLICE_CACHE.pop(filename, None)
    else:
        _SLICE_CACHE.clear()


def _body_hash(body: str) -> str:
    return str(hash(body))


def get_volume_slices(
    filename: str,
    jp_body: str,
    pt_body: str,
    spec: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Trechos JP/PT — separação sequencial (line_by_line_slices)."""
    from line_by_line_slices import get_volume_slices as _get  # noqa: WPS433

    jp_slices, pt_slices = _get(filename, jp_body, pt_body, spec)
    bounds = [Boundary.from_article(a) for a in spec.get("articles") or []]
    _SLICE_CACHE[filename] = {
        "pt_hash": _body_hash(pt_body),
        "jp_slices": jp_slices,
        "pt_slices": [trim_pt_chunk_leakage(c) for c in pt_slices],
        "bounds": bounds,
        "profile": spec.get("profile") or "gokowa_roku_qa",
    }
    return _SLICE_CACHE[filename]["jp_slices"], _SLICE_CACHE[filename]["pt_slices"]


def extract_segment_slices(
    filename: str,
    segment_index: int,
    jp_body: str,
    pt_body: str,
    spec: dict[str, Any],
) -> tuple[str, str, dict[str, int]]:
    from line_by_line_revision import extract_segment_slices as _ext  # noqa: WPS433

    return _ext(filename, segment_index, jp_body, pt_body, spec)


def _pt_sources(filename: str) -> list[tuple[str, Path]]:
    """Fontes PT — confiáveis primeiro; corpus de massa (pós-bug) por último."""
    wr = work_root("livros_acervo")
    out: list[tuple[str, Path]] = []
    seen: set[str] = set()

    def add(label: str, path: Path) -> None:
        key = str(path.resolve())
        if path.is_file() and key not in seen:
            seen.add(key)
            out.append((label, path))

    for snap in sorted(SNAPSHOT_ROOT.glob("*/livros_trabalho/pt/" + filename)):
        add(f"snapshot:{snap.parent.parent.name[:40]}", snap)

    add("pt_bak_p2", wr / "pt" / f"{filename}.bak_p2")

    pilot_root = ROOT / "reports/translation_review/translation_pilot"
    for p in sorted(pilot_root.glob("*/corpus/*" + filename.replace(".txt", "") + "*")):
        add(f"pilot:{p.parent.parent.name[:30]}", p)

    add("pt_trabalho", wr / "pt" / filename)
    add("periodicos_pt", work_root("periodicos") / "pt" / filename)

    for p in sorted(PT_ORFAOS.rglob("*.txt")):
        if filename in p.name or p.name == filename:
            add(f"pt_orfaos:{p.parent.name}", p)

    add("corpus_retraducao_massa", MASS_CORPUS / filename)

    return out


def _read_pt_file(path: Path) -> str:
    from fix_periodicos_work_headers import parse_article, split_file  # noqa: WPS433

    raw = path.read_text(encoding="utf-8")
    if "---" in raw:
        _, blocks = split_file(raw)
        if blocks:
            return parse_article(blocks[0]).content.strip()
    if "---" in raw:
        return raw.split("---", 1)[-1].strip()
    return raw.strip()


def _extract_pt_paragraph_at_needles(source_pt: str, jp_turn_text: str) -> str | None:
    """Parágrafo PT na posição das agulhas — funciona para prosa/narração e diálogo."""
    needles = [n for n in jp_session_needles(jp_turn_text) if len(n.strip()) >= 8][:8]
    if not needles:
        return None
    pos = find_pt_by_needles(source_pt, needles, 0)
    if pos < 0:
        return None
    start = source_pt.rfind("\n\n", 0, pos)
    start = 0 if start < 0 else start + 2
    end = source_pt.find("\n\n", pos)
    end = len(source_pt) if end < 0 else end
    chunk = source_pt[start:end].strip()
    if chunk and not needs_pt_work(chunk):
        hits, total = _needle_hits(chunk, needles)
        if total >= 1 and hits >= max(1, total // 2):
            return chunk
    return None


def _extract_turn_at_needles(
    source_pt: str,
    jp_turn_text: str,
    expected_kind: str,
    *,
    profile: str,
) -> str | None:
    needles = [n for n in jp_session_needles(jp_turn_text) if len(n.strip()) >= 8][:8]
    if not needles:
        return None
    pos = find_pt_by_needles(source_pt, needles, 0)
    if pos < 0:
        return None

    window = source_pt[max(0, pos - 300) : min(len(source_pt), pos + 6000)]
    pt_turns = parse_qa_turns(window, lang="pt", profile=profile)
    want = "interlocutor" if expected_kind == "interlocutor" else "meishu"
    best: tuple[int, str] | None = None
    for t in pt_turns:
        if t.kind != want:
            continue
        hits, total = _needle_hits(t.text, needles)
        if total >= 1 and hits >= max(1, total // 2):
            score = hits * 10 + len(t.text)
            if best is None or score > best[0]:
                best = (score, t.text.strip())
    if best:
        return best[1]
    return _extract_pt_paragraph_at_needles(source_pt, jp_turn_text)


def search_exhaustive_pt(
    filename: str,
    jp_turn_text: str,
    *,
    expected_kind: str,
    profile: str = "gokowa_roku_qa",
) -> SearchResult:
    """Busca exaustiva PT — parágrafo por agulhas (sem parse_qa_turns)."""
    del profile
    res = SearchResult()
    for label, path in _pt_sources(filename):
        res.log.append(f"  busca: {label} ({path.name})")
        try:
            body = _read_pt_file(path)
        except OSError as exc:
            res.log.append(f"    erro leitura: {exc}")
            continue
        if not body.strip():
            res.log.append("    vazio")
            continue
        pt = _extract_pt_paragraph_at_needles(body, jp_turn_text)
        if pt and not needs_pt_work(pt):
            res.pt_text = pt
            res.source = label
            res.log.append(f"    ENCONTRADO ({len(pt)} chars)")
            return res
        res.log.append("    não encontrado")
    res.log.append("  busca exaustiva concluída — sem correspondente")
    return res


def turn_needs_fix(jp_turn_text: str, pt_text: str, jp_kind: str) -> tuple[bool, list[str]]:
    pt_text = sanitize_turn_text(pt_text)
    if jp_kind in ("header", "narration"):
        if not pt_text:
            return True, ["PT vazio"]
        if jp_kind == "header" and len(jp_turn_text) > 15:
            short = jp_turn_text.strip()[:20]
            if short not in pt_text and jp_turn_text[:12] not in pt_text:
                needles = jp_session_needles(jp_turn_text)[:3]
                hits, total = _needle_hits(pt_text, needles)
                if total >= 1 and hits == 0:
                    return True, ["cabeçalho desalinhado"]
        return False, []

    if needs_pt_work(pt_text):
        return True, ["vazio ou CJK"]
    needles = jp_session_needles(jp_turn_text)[:6]
    hits, total = _needle_hits(pt_text, needles)
    if total >= 2 and hits == 0:
        return True, [f"0/{total} agulhas JP no turno"]
    if total >= 3 and hits < total // 2:
        return True, [f"só {hits}/{total} agulhas"]
    return False, []


def _get_deepseek_client() -> Any:
    global _client
    if _client is None:
        from run_deepseek_revision_pilot import load_env_api_key  # noqa: WPS433
        from run_translation_warn_pilot import DeepSeekClient  # noqa: WPS433

        _client = DeepSeekClient(api_key=load_env_api_key())
    return _client


def translate_turn_protocol(jp_text: str, *, label: str, title: str = "turno") -> str:
    """Retradução via protocolo_traducao + glossário (excepção após busca)."""
    from run_deepseek_revision_pilot import load_glossary  # noqa: WPS433
    from translation_protocol_core import PROTOCOL_PATH, translate_jp_text  # noqa: WPS433

    protocol = PROTOCOL_PATH.read_text(encoding="utf-8")
    glossary = load_glossary()
    client = _get_deepseek_client()
    prefixed = jp_text.strip()
    if label in ("Interlocutor", "Meishu-Sama") and not prefixed.startswith(("――", "（")):
        if label == "Interlocutor":
            prefixed = f"―― {prefixed}"
        else:
            prefixed = f"　{prefixed}"
    pt, _usage, _logs = translate_jp_text(
        client,
        prefixed,
        protocol,
        glossary,
        title=title,
        chunk_delay=0.2,
    )
    pt = pt.strip()
    if label == "Interlocutor" and not pt.startswith("Interlocutor:"):
        pt = re.sub(r"^[—―–\-]{1,2}\s*", "", pt)
        return pt
    if label == "Meishu-Sama" and pt.startswith("Meishu-Sama:"):
        return pt[len("Meishu-Sama:") :].strip()
    return pt


def segment_blocking_issues(
    jp_slice: str,
    pt_slice: str,
    *,
    filename: str,
    profile: str = "gokowa_roku_qa",
    bounds: Boundary | None = None,
) -> tuple[bool, list[str], list[str]]:
    """True se ainda há bloqueios — prioridade: turno a turno, depois verify_qa."""
    issues: list[str] = []
    notes: list[str] = []

    if not (pt_slice or "").strip():
        return True, [ISSUE_NO_PT], ["PT vazio"]

    jp_turns = parse_qa_turns(jp_slice, lang="jp", profile=profile)
    pt_turns = parse_qa_turns(pt_slice, lang="pt", profile=profile)
    pairs = build_turn_pairs(jp_turns, pt_slice, pt_turns, profile=profile)

    for jt, (label, pt_text) in zip(jp_turns, pairs, strict=False):
        if jt.kind not in ("interlocutor", "meishu", "header", "narration"):
            continue
        bad, why = turn_needs_fix(jt.text, pt_text, jt.kind)
        if bad:
            issues.append(ISSUE_ALIGN)
            notes.append(f"turno ({jt.kind}): {', '.join(why)}")
            return True, issues, notes

    has_a4b = "Interlocutor:" in pt_slice or "Meishu-Sama:" in pt_slice
    if has_a4b:
        qa = verify_qa_alignment(jp_slice, pt_slice, profile=profile)
        if qa:
            issues.extend([ISSUE_ALIGN] * len(qa))
            notes.extend(qa)
            return True, issues, notes

    if bounds is None:
        bounds = Boundary(kind="session", title_jp="", jp_anchor="")
    tr = review_trecho(0, bounds, jp_slice, pt_slice, filename=filename, profile=profile)
    if has_blocking_cjk(pt_slice):
        issues.append(ISSUE_CJK)
        notes.append("CJK bloqueante no trecho")
        return True, issues, notes
    hard = {ISSUE_NO_PT, ISSUE_INCOMPLETE}
    if any(i in hard for i in tr.issues):
        issues.extend(tr.issues)
        notes.extend(tr.notes)
        return True, issues, notes

    return False, tr.issues, tr.notes


def resolve_pt_text_for_jp_turn(
    jt: Any,
    pt_slice: str,
    pt_turns: list[Any],
    *,
    profile: str,
    dlg_i: int,
) -> str:
    """Texto PT para um turno JP — agulhas primeiro, depois fila posicional."""
    if jt.kind in ("interlocutor", "meishu"):
        ext = _extract_turn_at_needles(pt_slice, jt.text, jt.kind, profile=profile)
        if ext:
            return ext
        pt_dlg = [t for t in pt_turns if t.kind in ("interlocutor", "meishu")]
        if dlg_i < len(pt_dlg):
            return pt_dlg[dlg_i].text
        return ""
    if jt.kind == "narration":
        pt_nar = [t for t in pt_turns if t.kind == "narration"]
        if dlg_i < len(pt_nar):
            return pt_nar[dlg_i].text
    if jt.kind == "header":
        for t in pt_turns:
            if t.kind in ("header", "narration") and t.text.strip():
                return t.text
    return ""


def build_turn_pairs(
    jp_turns: list[Any],
    pt_slice: str,
    pt_turns: list[Any],
    *,
    profile: str,
) -> list[tuple[str, str]]:
    """Lista (label, texto) alinhada ao JP — agulhas + fila de diálogo."""
    out: list[tuple[str, str]] = []
    dlg_i = 0
    nar_i = 0
    for jt in jp_turns:
        if jt.kind == "interlocutor":
            text = resolve_pt_text_for_jp_turn(jt, pt_slice, pt_turns, profile=profile, dlg_i=dlg_i)
            out.append(("Interlocutor", text))
            dlg_i += 1
        elif jt.kind == "meishu":
            text = resolve_pt_text_for_jp_turn(jt, pt_slice, pt_turns, profile=profile, dlg_i=dlg_i)
            out.append(("Meishu-Sama", text))
            dlg_i += 1
        elif jt.kind == "header":
            pt_nar = [t for t in pt_turns if t.kind in ("header", "narration")]
            text = pt_nar[nar_i].text if nar_i < len(pt_nar) else jt.text
            out.append(("header", text))
            nar_i += 1
        elif jt.kind == "narration":
            pt_nar = [t for t in pt_turns if t.kind == "narration"]
            text = pt_nar[nar_i].text if nar_i < len(pt_nar) else ""
            out.append(("narration", text))
            nar_i += 1
    return out


def _format_turn(label: str, text: str) -> str:
    t = (text or "").strip()
    if label == "header":
        return t
    if label == "narration":
        return t
    if label == "Interlocutor":
        return f"Interlocutor: {t}" if t else "Interlocutor: "
    if label == "Meishu-Sama":
        return f"Meishu-Sama: {t}" if t else "Meishu-Sama: "
    return t


def _rebuild_pt_from_turns(turns: list[tuple[str, str]]) -> str:
    blocks: list[str] = []
    for kind, text in turns:
        blocks.append(_format_turn(kind, sanitize_turn_text(text)))
    return trim_pt_chunk_leakage("\n\n".join(b for b in blocks if b.strip()).strip()) + "\n"


def rebuild_pt_preserve_format(
    original: str,
    jp_turns: list[Any],
    pt_by_index: list[tuple[str, str]],
    *,
    has_a4b: bool,
) -> str:
    """Grava correções sem impor A4B quando o PT original não tinha rótulos."""
    if has_a4b:
        return _rebuild_pt_from_turns(pt_by_index)
    blocks: list[str] = []
    for jt, (_label, text) in zip(jp_turns, pt_by_index, strict=False):
        text = sanitize_turn_text(text)
        if text:
            blocks.append(text)
    if not blocks:
        return trim_pt_chunk_leakage(original)
    return trim_pt_chunk_leakage("\n\n".join(blocks).strip()) + "\n"


def process_segment_protocol(
    filename: str,
    segment_index: int,
    jp_body: str,
    pt_body: str,
    spec: dict[str, Any],
    *,
    translate: bool = True,
    max_translate: int = 40,
    log_fn: Callable[[str], None] | None = None,
) -> SegmentProtocolResult:
    """Delega ao motor linha a linha (map_jp_lines)."""
    from line_by_line_revision import process_segment_line_by_line  # noqa: WPS433

    return process_segment_line_by_line(
        filename,
        segment_index,
        jp_body,
        pt_body,
        spec,
        translate=translate,
        max_translate=max_translate,
        log_fn=log_fn,
    )
