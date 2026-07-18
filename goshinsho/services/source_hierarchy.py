"""Hierarquia palavra escrita → palavra oral (Gosuiji/Gokōwa-roku, Mioshie-shū)."""

from __future__ import annotations

import re

_ORAL_SOURCE_RE = re.compile(
    r"(?is)"
    r"gosuiji[-\s]?roku|"
    r"gok[oō]wa[-\s]?roku|"
    r"mioshie[-\s]?sh|"
    r"coletanea de ensinamentos|"
    r"御光話|"
    r"御教え"
)

_WRITTEN_MIN_SCORE = 2.5
_WRITTEN_SUFFICIENT_COUNT = 3
_ORAL_SUPPLEMENT_MAX = 3
_ORAL_SUPPLEMENT_RATIO = 0.72


def source_blob(meta: dict) -> str:
    return f"{meta.get('fonte', '')} {meta.get('arquivo', '')}"


def is_oral_source(meta: dict) -> bool:
    return bool(_ORAL_SOURCE_RE.search(source_blob(meta)))


def is_written_source(meta: dict) -> bool:
    return bool(source_blob(meta).strip()) and not is_oral_source(meta)


def _tag_medium(chunks: list[str], metas: list[dict]) -> tuple[list[str], list[dict]]:
    tagged: list[dict] = []
    for chunk, meta in zip(chunks, metas):
        enriched = dict(meta)
        enriched["source_medium"] = "oral" if is_oral_source(meta) else "written"
        tagged.append(enriched)
    return chunks, tagged


def prefer_written_sources(
    scored: list[tuple[float, str, dict]],
    *,
    max_output: int,
    weighted_terms: list[tuple[str, float]] | None = None,
) -> tuple[list[str], list[dict]]:
    """
    Prioriza trechos de palavra escrita; oral só se insuficiente ou para complementar.

    scored: lista (score, chunk, meta) já ordenada por score descendente.
    """
    if not scored or max_output <= 0:
        return [], []

    written = [item for item in scored if is_written_source(item[2])]
    oral = [item for item in scored if is_oral_source(item[2])]

    good_written = [item for item in written if item[0] >= _WRITTEN_MIN_SCORE]
    written_sufficient = len(good_written) >= min(_WRITTEN_SUFFICIENT_COUNT, max_output // 2 + 1)

    selected: list[tuple[float, str, dict]] = []
    seen: set[tuple] = set()

    def _key(chunk: str, meta: dict) -> tuple:
        return (meta.get("entry_id") or meta.get("arquivo"), meta.get("chunk_index"), chunk[:120])

    def _take(pool: list[tuple[float, str, dict]], limit: int) -> None:
        for item in pool:
            if len(selected) >= limit:
                break
            key = _key(item[1], item[2])
            if key in seen:
                continue
            seen.add(key)
            selected.append(item)

    if written_sufficient:
        _take(written, max_output)
        if written and oral:
            best_written = written[0][0]
            threshold = best_written * _ORAL_SUPPLEMENT_RATIO
            supplements = [item for item in oral if item[0] >= threshold][:_ORAL_SUPPLEMENT_MAX]
            if supplements and len(selected) >= max_output:
                # Troca os piores escritos por oral complementar de alto score
                replaceable = sorted(selected, key=lambda item: item[0])[: len(supplements)]
                replace_keys = {_key(c, m) for _, c, m in replaceable}
                selected = [item for item in selected if _key(item[1], item[2]) not in replace_keys]
                for item in supplements:
                    key = _key(item[1], item[2])
                    if key in seen:
                        continue
                    if len(selected) >= max_output:
                        break
                    seen.add(key)
                    selected.append(item)
                selected.sort(key=lambda item: -item[0])
            elif len(selected) < max_output:
                _take(supplements, max_output)
    else:
        _take(written, max_output)
        if len(selected) < max_output:
            _take(oral, max_output)

    selected = selected[:max_output]
    chunks = [chunk for _, chunk, _ in selected]
    metas = [meta for _, _, meta in selected]
    return _tag_medium(chunks, metas)
