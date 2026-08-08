#!/usr/bin/env python3
"""Separação de trechos JP→PT — cursor sequencial (como o protocolo linha a linha).

JP: ancora jp_anchor por trecho (spec manual).
PT: a partir do cursor, procurar o início equivalente ao JP (data, pt_anchor, agulhas);
    fim do trecho = início do trecho JP seguinte.
"""

from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from typing import Any

SCRIPTS = __import__("pathlib").Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

from apply_manual_livros_segmentacao import Boundary, split_by_anchors  # noqa: E402
from livros_segmentacao_pairing import (  # noqa: E402
    content_start,
    find_pt_by_needles,
    find_pt_date_marker,
    find_pt_gokowa_ho_session_start,
    jp_session_needles,
    jp_slice_date_jp_raw,
    jp_slice_date_pt,
    yamamizu_jp_date_to_pt,
)

GLOSSARIO_TRADUCAO_PATH = SCRIPTS.parent / "glossario_traducao.json"

_SLICE_CACHE: dict[str, dict[str, Any]] = {}


def invalidate_slice_cache(filename: str | None = None) -> None:
    if filename:
        _SLICE_CACHE.pop(filename, None)
    else:
        _SLICE_CACHE.clear()


def _body_hash(body: str) -> str:
    return str(hash(body))


@lru_cache(maxsize=1)
def _glossario_traducao() -> dict[str, str]:
    if not GLOSSARIO_TRADUCAO_PATH.is_file():
        return {}
    try:
        data = json.loads(GLOSSARIO_TRADUCAO_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)}


def _glossary_pt_needles(jp_chunk: str, *, limit: int = 12) -> list[str]:
    """Termos do glossário de tradução presentes no trecho JP → forma PT canónica.

    Âncoras de data e agulhas em japonês só funcionam quando o PT reproduz
    literalmente esse texto — o que falha sistematicamente em trechos sem
    cabeçalho de data escrito no PT (maioria deste perfil). A forma PT do
    glossário, por outro lado, é garantida pelo protocolo de tradução:
    funciona como agulha fiável de conteúdo, independente de haver data.
    """
    glossario = _glossario_traducao()
    if not glossario or not jp_chunk:
        return []
    found: list[tuple[int, str]] = []
    for jp_term, pt_term in glossario.items():
        pt_clean = (pt_term or "").strip()
        if len(jp_term) < 2 or len(pt_clean) < 6:
            continue
        if jp_term in jp_chunk:
            found.append((len(pt_clean), pt_clean))
    found.sort(reverse=True)
    seen: set[str] = set()
    out: list[str] = []
    for _, term in found:
        if term not in seen:
            seen.add(term)
            out.append(term)
        if len(out) >= limit:
            break
    return out


def _content_needle_candidates(jp_chunk: str) -> list[str]:
    """Agulhas de conteúdo utilizáveis directamente no PT (sem depender de data)."""
    needles = list(_glossary_pt_needles(jp_chunk))
    for n in jp_session_needles(jp_chunk):
        s = (n or "").strip()
        if not s:
            continue
        if re.match(r"^\d{1,3}\s+anos$", s) or (s[:1].isupper() and s.isascii() and len(s) >= 5):
            needles.append(s)
    return [n for n in dict.fromkeys(needles) if len(n.strip()) >= 6]


def _content_needle_start(pt_body: str, jp_chunk: str, cursor: int) -> int:
    """Fronteira por conteúdo — método principal quando não há cabeçalho de data
    literal no PT. Só aceita posição validada por `_session_boundary_valid`.

    Termos ubíquos (ex. "Johrei" num curso inteiro sobre Johrei) não
    distinguem trecho nenhum — aparecem por todo o documento e produzem
    candidatos essencialmente aleatórios. Só usa como agulha um termo que
    ocorre poucas vezes no PT inteiro (marcador realmente específico deste
    trecho), senão ignora-o e recorre ao método de data/âncora existente.
    """
    needles = _content_needle_candidates(jp_chunk)
    if not needles:
        return -1
    low = pt_body.lower()
    max_global_hits = 4
    candidates: set[int] = set()
    for n in needles:
        needle_low = n.lower()
        if low.count(needle_low) > max_global_hits:
            continue
        search = cursor
        hits = 0
        while hits < 6:
            pos = low.find(needle_low, search)
            if pos < 0:
                break
            candidates.add(pos)
            search = pos + max(len(n) // 2, 4)
            hits += 1
    if not candidates:
        return -1
    valid = sorted(p for p in candidates if _session_boundary_valid(pt_body, p, jp_chunk))
    if not valid:
        return -1

    def _header_noise(pos: int) -> int:
        chunk = (pt_body[pos:] or "")[:800]
        paras = [p.strip() for p in re.split(r"\n\s*\n", chunk.strip()) if p.strip()]
        n = 0
        for p in paras:
            if _looks_date_only_para(p):
                n += 1
            else:
                break
        return n

    return min(valid, key=_header_noise)


def _first_content_line(jp_chunk: str) -> str:
    for line in jp_chunk.splitlines():
        s = line.strip()
        if s:
            return s
    return ""


def trecho_pt_start_patterns(bound: Boundary, jp_chunk: str) -> list[str]:
    """Padrões para localizar o início do trecho PT (ordem de prioridade)."""
    pats: list[str] = []
    seen: set[str] = set()

    def add(s: str) -> None:
        s = (s or "").strip()
        if len(s) >= 4 and s not in seen:
            seen.add(s)
            pats.append(s)

    for key in (bound.pt_anchor, bound.pt_prefix, bound.title_pt):
        add(key)
    # variantes comuns Gokōwa/Gosuiji
    for key in list(pats):
        if "Gokōwa" in key or "Gokowa" in key:
            add(key.replace("Gokōwa", "Gosuiji").replace("Gokowa", "Gosuiji"))
        if "御光" in key:
            add(key.replace("御光", "御水"))
        stripped = key.strip("*").strip()
        if stripped != key:
            add(stripped)
        if "1º" in key or "1°" in key:
            add(key.replace("1º", "1").replace("1°", "1"))

    first = _first_content_line(jp_chunk)
    # Prefácio: só ancora explícita PT (evita datas soltas no metadata / corpo errado)
    if bound.kind == "preface":
        add("Gosuiji-roku (Suplemento)")
        add("Gokōwa-roku (Suplemento)")
        add("Gokowa-roku (Suplemento)")
    if bound.kind != "preface":
        add(jp_slice_date_pt(jp_chunk))
        add(jp_slice_date_pt(first))
        add(yamamizu_jp_date_to_pt(bound.title_jp))
        add(yamamizu_jp_date_to_pt(first))

        raw = jp_slice_date_jp_raw(jp_chunk) or jp_slice_date_jp_raw(first)
        if raw:
            add(raw)

        for n in jp_session_needles(jp_chunk)[:6]:
            if len(n.strip()) >= 6:
                add(n.strip())

        m = re.search(
            r"(\d{1,2}\s+de\s+(?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro))",
            f"{bound.title_pt} {bound.pt_anchor} {jp_slice_date_pt(jp_chunk)}",
            re.I,
        )
        if m:
            add(m.group(1))

    return pats


def _looks_date_only_para(para: str) -> bool:
    s = (para or "").strip()
    if not s:
        return False
    if re.match(r"^\d{1,2}\s+de\s+", s, re.I):
        return True
    if re.search(
        r"\b(janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro)\b",
        s,
        re.I,
    ) and len(s) < 120:
        return True
    return bool(re.match(r"^[\dº°\s\-–—de]+(?:\([^)]+\))?$", s, re.I))


def _first_substantive_para(paras: list[str]) -> str:
    for p in paras:
        if not _looks_date_only_para(p):
            return p.strip()
    return ""


def _session_boundary_valid(pt_body: str, pos: int, jp_chunk: str) -> bool:
    """Rejeita âncoras PT falsas (fragmento órfão, datas repetidas sem corpo)."""
    chunk = (pt_body[pos:] or "")[:1200]
    paras = [p.strip() for p in re.split(r"\n\s*\n", chunk.strip()) if p.strip()]
    if not paras:
        return False

    body = _first_substantive_para(paras)
    if not body:
        return len(paras) <= 2

    # Fragmento órfão: continuação a meio de palavra/frase
    if re.match(r"^[a-záéíóúâêôã]", body) and len(body.split()[0]) <= 3:
        return False

    first_jp = _first_content_line(jp_chunk)
    if first_jp:
        from acervo_agent_core import JP_DATE  # noqa: WPS433

        is_jp_date_header = bool(JP_DATE.match(first_jp.strip()) or first_jp.strip().startswith("［"))
        if not is_jp_date_header:
            needles = [n for n in jp_session_needles(first_jp) if len(n.strip()) >= 4][:6]
            if needles:
                from revisao_paralela_livros import _needle_hits  # noqa: WPS433

                hits, total = _needle_hits(body[:600], needles)
                if total >= 1 and hits == 0:
                    return False

    return True


def _collect_pt_start_candidates(
    pt_body: str, patterns: list[str], cursor: int
) -> list[int]:
    """Todas as posições candidatas (padrões longos primeiro)."""
    if not pt_body.strip():
        return []

    low = pt_body.lower()

    def all_matches(pat: str) -> list[int]:
        if not pat or len(pat.strip()) < 4:
            return []
        found: list[int] = []
        p = pat.strip()
        search = cursor
        max_hits = 32
        while search < len(pt_body) and len(found) < max_hits:
            pos = try_one_at(p, search)
            if pos < 0:
                break
            found.append(pos)
            search = pos + max(len(p) // 2, 4)
        return found

    def try_one_at(pat: str, from_cursor: int) -> int:
        if not pat:
            return -1
        for variant in (pat.strip(), pat.strip().strip("()[]")):
            p = variant
            if len(p) < 4:
                continue
            pos = low.find(p.lower(), from_cursor)
            if pos >= 0:
                return pos
            m = re.search(
                r"(\d{1,2})\s+de\s+((?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro))",
                p,
                re.I,
            )
            if m:
                day, month = m.group(1), m.group(2).lower()
                for form in (f"{day}º de {month}", f"{day}° de {month}", f"{day} de {month}"):
                    pos = low.find(form, from_cursor)
                    if pos >= 0:
                        return pos
                pos = find_pt_date_marker(pt_body, f"{day} de {month}", from_cursor)
                if pos >= 0:
                    return pos
                pos = find_pt_gokowa_ho_session_start(pt_body, f"{day} de {month}", from_cursor)
                if pos >= 0:
                    return pos
        return -1

    seen: set[int] = set()
    ordered: list[int] = []
    uniq_pats = sorted({p.strip() for p in patterns if (p or "").strip()}, key=len, reverse=True)
    for pat in uniq_pats:
        for pos in all_matches(pat):
            if pos not in seen:
                seen.add(pos)
                ordered.append(pos)

    needles = [p for p in patterns if len((p or "").strip()) >= 6][:8]
    if needles:
        pos = find_pt_by_needles(pt_body, needles, cursor)
        if pos >= 0 and pos not in seen:
            ordered.append(pos)

    return sorted(ordered)


_NEEDLE_FIRST_PROFILES = {"gokowa_roku_qa"}


def find_pt_start(
    pt_body: str,
    patterns: list[str],
    cursor: int,
    *,
    jp_chunk: str = "",
    profile: str = "",
) -> int:
    """Primeira ocorrência válida a partir de cursor — ignora âncoras falsas.

    Para o perfil ``gokowa_roku_qa`` (sessões de pergunta-e-resposta longas,
    tipicamente sem cabeçalho de data literal escrito no PT), tenta primeiro
    fronteira por conteúdo (glossário + agulhas compatíveis PT) — âncora de
    data falha sistematicamente aí porque o PT nunca reproduz a data como
    texto literal. Noutros perfis (ex. cursos por aula, coletâneas), onde o
    vocabulário se repete muito entre trechos curtos, a agulha por conteúdo
    deixa de ser discriminativa e o método de data/âncora existente permanece
    principal.
    """
    if not pt_body.strip():
        return -1

    if jp_chunk.strip() and profile in _NEEDLE_FIRST_PROFILES:
        needle_pos = _content_needle_start(pt_body, jp_chunk, cursor)
        if needle_pos >= 0:
            return needle_pos

    candidates = _collect_pt_start_candidates(pt_body, patterns, cursor)
    if jp_chunk.strip():
        valid = [pos for pos in candidates if _session_boundary_valid(pt_body, pos, jp_chunk)]
        if not valid:
            return -1

        def _header_noise(pos: int) -> int:
            chunk = (pt_body[pos:] or "")[:800]
            paras = [p.strip() for p in re.split(r"\n\s*\n", chunk.strip()) if p.strip()]
            n = 0
            for p in paras:
                if _looks_date_only_para(p):
                    n += 1
                else:
                    break
            return n

        return min(valid, key=_header_noise)
    if candidates:
        return candidates[0]

    low = pt_body.lower()

    def try_one(pat: str) -> int:
        if not pat:
            return -1
        for variant in (pat.strip(), pat.strip().strip("()[]")):
            p = variant
            if len(p) < 4:
                continue
            pos = low.find(p.lower(), cursor)
            if pos >= 0:
                return pos
            m = re.search(
                r"(\d{1,2})\s+de\s+((?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro))",
                p,
                re.I,
            )
            if m:
                day, month = m.group(1), m.group(2).lower()
                for form in (f"{day}º de {month}", f"{day}° de {month}", f"{day} de {month}"):
                    pos = low.find(form, cursor)
                    if pos >= 0:
                        return pos
                pos = find_pt_date_marker(pt_body, f"{day} de {month}", cursor)
                if pos >= 0:
                    return pos
                pos = find_pt_gokowa_ho_session_start(pt_body, f"{day} de {month}", cursor)
                if pos >= 0:
                    return pos
            m = re.search(
                r"(\d{1,2}[º°]?\s+de\s+(?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro))",
                p,
                re.I,
            )
            if m:
                pos = low.find(m.group(1).lower(), cursor)
                if pos >= 0:
                    return pos
            m = re.search(
                r"(\d{1,2}\s+de\s+(?:janeiro|fevereiro|março|abril|maio|junho|julho|agosto|setembro|outubro|novembro|dezembro))",
                p,
                re.I,
            )
            if m:
                pos = find_pt_date_marker(pt_body, m.group(1), cursor)
                if pos >= 0:
                    return pos
        return -1

    for pat in patterns:
        pos = try_one(pat)
        if pos >= 0:
            return pos

    needles = [p for p in patterns if len(p.strip()) >= 6][:8]
    if needles:
        pos = find_pt_by_needles(pt_body, needles, cursor)
        if pos >= 0:
            return pos

    for pat in patterns:
        date = jp_slice_date_pt(pat) or pat
        m = re.match(r"^(\d{1,2})\s+de\s+(\w+)", date, re.I)
        if m:
            pos = find_pt_gokowa_ho_session_start(pt_body, date, cursor)
            if pos >= 0:
                return pos
            pos = find_pt_date_marker(pt_body, date, cursor)
            if pos >= 0:
                return pos

    return -1


def pt_slice_char_bounds(
    pt_body: str,
    jp_body: str,
    spec: dict[str, Any],
    segment_index: int,
) -> tuple[int, int]:
    """Limites [start, end) do trecho PT no monólito — fonte de verdade para gravação."""
    bounds = [Boundary.from_article(a) for a in spec.get("articles") or []]
    jp_slices = split_by_anchors(jp_body, [b.jp_anchor for b in bounds], label="JP")
    profile = spec.get("profile") or ""
    positions = split_pt_by_jp_sequential(pt_body, jp_slices, bounds, profile=profile)
    if segment_index >= len(positions):
        raise IndexError(segment_index)
    start = positions[segment_index]
    end = positions[segment_index + 1] if segment_index + 1 < len(positions) else len(pt_body)
    return start, end


def splice_pt_slice(
    pt_body: str,
    jp_body: str,
    spec: dict[str, Any],
    segment_index: int,
    new_slice: str,
) -> str:
    """Substitui trecho PT por índice (sem find global de âncoras)."""
    start, end = pt_slice_char_bounds(pt_body, jp_body, spec, segment_index)
    new = new_slice.strip()
    tail = pt_body[end:].lstrip() if end < len(pt_body) else ""
    if new and tail:
        return pt_body[:start] + new + "\n\n" + tail
    if new:
        return pt_body[:start] + new + ("\n" if not pt_body[:start].endswith("\n") else "")
    return pt_body[:start] + tail


def split_pt_by_jp_sequential(
    pt_body: str,
    jp_slices: list[str],
    bounds: list[Boundary],
    *,
    profile: str = "",
) -> list[int]:
    """Posições de início de cada trecho PT (alinhamento sequencial ao JP)."""
    if not jp_slices:
        return [content_start(pt_body)]

    positions: list[int] = []
    cursor = content_start(pt_body)

    for i, (bound, jp_chunk) in enumerate(zip(bounds, jp_slices, strict=False)):
        base = content_start(pt_body) if i == 0 else cursor
        pats = trecho_pt_start_patterns(bound, jp_chunk)
        pos = find_pt_start(pt_body, pats, base, jp_chunk=jp_chunk, profile=profile)
        if pos < 0:
            if i == 0:
                pos = content_start(pt_body)
            else:
                # Sem âncora válida — procurar sem validação JP (último recurso)
                pos = find_pt_start(pt_body, pats, base, jp_chunk="", profile=profile)
                if pos < 0:
                    pos = cursor
        positions.append(min(pos, len(pt_body)))
        cursor = max(pos + 1, positions[-1] + 1)

    # Garantir ordem estritamente crescente
    for i in range(1, len(positions)):
        if positions[i] <= positions[i - 1]:
            positions[i] = min(positions[i - 1] + 1, len(pt_body))

    # Trechos PT desproporcionais ao JP (ficheiro corrompido / âncora falsa)
    max_ratio = 25
    for i in range(len(positions) - 1):
        jp_len = len(jp_slices[i])
        span = positions[i + 1] - positions[i]
        if jp_len < 80 or span <= jp_len * max_ratio:
            continue
        if i + 1 >= len(bounds):
            continue
        pats = trecho_pt_start_patterns(bounds[i + 1], jp_slices[i + 1])
        search_from = positions[i] + min(max(jp_len // 2, 80), 4000)
        pos = find_pt_start(pt_body, pats, search_from, jp_chunk=jp_slices[i + 1], profile=profile)
        if pos >= 0 and pos > positions[i]:
            new_span = pos - positions[i]
            if new_span <= jp_len * max_ratio:
                positions[i + 1] = pos
    for i in range(1, len(positions)):
        if positions[i] <= positions[i - 1]:
            positions[i] = min(positions[i - 1] + 1, len(pt_body))

    return positions


def split_volume_slices(
    jp_body: str,
    pt_body: str,
    spec: dict[str, Any],
) -> tuple[list[str], list[str], list[Boundary]]:
    """Divide monólito JP/PT em trechos — JP por anchor, PT por cursor sequencial."""
    bounds = [Boundary.from_article(a) for a in spec.get("articles") or []]
    jp_slices = split_by_anchors(jp_body, [b.jp_anchor for b in bounds], label="JP")
    profile = spec.get("profile") or ""
    positions = split_pt_by_jp_sequential(pt_body, jp_slices, bounds, profile=profile)
    pt_slices = [
        pt_body[positions[i] : (positions[i + 1] if i + 1 < len(positions) else len(pt_body))].strip()
        for i in range(len(jp_slices))
    ]
    return jp_slices, pt_slices, bounds


def get_volume_slices(
    filename: str,
    jp_body: str,
    pt_body: str,
    spec: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Cache de trechos — invalidar após alteração ao PT."""
    cached = _SLICE_CACHE.get(filename)
    h = _body_hash(pt_body)
    if cached and cached.get("pt_hash") == h:
        return cached["jp_slices"], cached["pt_slices"]

    jp_slices, pt_slices, bounds = split_volume_slices(jp_body, pt_body, spec)
    _SLICE_CACHE[filename] = {
        "pt_hash": h,
        "jp_slices": jp_slices,
        "pt_slices": pt_slices,
        "bounds": bounds,
        "profile": spec.get("profile") or "gokowa_roku_qa",
    }
    return jp_slices, pt_slices


def resplit_report(filename: str, jp_body: str, pt_body: str, spec: dict[str, Any]) -> dict[str, Any]:
    """Relatório de separação (para diagnóstico / reinício)."""
    invalidate_slice_cache(filename)
    jp_slices, pt_slices, bounds = split_volume_slices(jp_body, pt_body, spec)
    rows = []
    for i, (b, jp_s, pt_s) in enumerate(zip(bounds, jp_slices, pt_slices, strict=False)):
        rows.append(
            {
                "index": i,
                "title": b.title_pt or b.title_jp,
                "jp_chars": len(jp_s),
                "pt_chars": len(pt_s),
                "jp_anchor": b.jp_anchor[:60],
                "pt_start_preview": pt_s[:80].replace("\n", " "),
            }
        )
    return {"filename": filename, "trechos": len(rows), "segments": rows}


def validate_segment_slice(
    jp_slice: str,
    pt_slice: str,
    segment_index: int,
    *,
    title: str = "",
    kind: str = "",
) -> tuple[bool, list[str]]:
    """Validação obrigatória antes de A→D — slice PT proporcional ao JP.

    O tecto (`max_ratio` × `jp_len`, com piso mínimo) é a única defesa estável
    contra duplicação em cadeia: ao contrário de `original_pt_len` (que pode já
    estar corrompido/inflado por uma tentativa anterior), `jp_slice` nunca muda
    — por isso o limite tem de estar ancorado nele, com piso pequeno e
    proporcional ao trecho, nunca um piso plano gigante que na prática anula o
    tecto para trechos de tamanho normal (bug observado: piso de 80.000 chars
    deixava passar um trecho de ~2 mil chars duplicado 4× sem ser detectado).
    """
    issues: list[str] = []
    jp_len = len((jp_slice or "").strip())
    pt_len = len((pt_slice or "").strip())
    label = title or f"trecho {segment_index + 1}"
    is_preface = segment_index == 0 or kind == "preface" or label == "序文"
    max_ratio = 15 if is_preface else 4
    floor = 2000 if is_preface else 800

    if jp_len > 80 and pt_len < 40:
        issues.append(f"{label}: PT demasiado curto ({pt_len} chars) para JP={jp_len}")
    if jp_len > 50 and pt_len > max(jp_len * max_ratio, floor):
        issues.append(f"{label}: PT desproporcional ({pt_len} vs JP {jp_len})")
    if jp_len > 200 and pt_len > 0 and pt_len < jp_len * 0.08:
        issues.append(f"{label}: ratio PT/JP suspeito ({pt_len}/{jp_len})")

    return len(issues) == 0, issues


def validate_volume_slices(
    jp_slices: list[str],
    pt_slices: list[str],
    bounds: list[Boundary],
) -> tuple[bool, list[str]]:
    all_issues: list[str] = []
    for i, (jp_s, pt_s) in enumerate(zip(jp_slices, pt_slices, strict=False)):
        title = bounds[i].title_pt or bounds[i].title_jp if i < len(bounds) else ""
        ok, issues = validate_segment_slice(jp_s, pt_s, i, title=title, kind=bounds[i].kind if i < len(bounds) else "")
        if not ok:
            all_issues.extend(issues)
    return len(all_issues) == 0, all_issues


if __name__ == "__main__":
    import argparse
    import json
    from fix_periodicos_work_headers import parse_article, split_file  # noqa: E402

    ap = argparse.ArgumentParser(description="Reiniciar separação de trechos (linha a linha)")
    ap.add_argument("--file", required=True)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    wr = SCRIPTS.parent / "reports/livros_trabalho"
    spec_path = wr / "segmentacao_manual" / f"{args.file}.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    def body(path):
        raw = path.read_text(encoding="utf-8")
        _, blocks = split_file(raw)
        return parse_article(blocks[0]).content

    jp = body(wr / "jp" / args.file)
    pt = body(wr / "pt" / args.file) if (wr / "pt" / args.file).is_file() else ""
    report = resplit_report(args.file, jp, pt, spec)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"{args.file}: {report['trechos']} trechos")
        for s in report["segments"][:8]:
            print(f"  #{s['index']+1} JP={s['jp_chars']} PT={s['pt_chars']} | {s['title'][:40]}")
        if report["trechos"] > 8:
            print(f"  ... +{report['trechos']-8} trechos")
