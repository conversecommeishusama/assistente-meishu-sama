"""Pós-processamento de respostas da pipeline v2."""

from __future__ import annotations

import re

_FORBIDDEN_OPENINGS = (
    r"^\s*com base nos trechos fornecidos[,\s]*",
    r"^\s*com base no[s]? trecho[s]? (?:fornecido[s]?|disponívei[s]?|disponibilizados)[,\s]*",
    r"^\s*nos trechos fornecidos[,\s]*",
    r"^\s*baseado nos trechos fornecidos[,\s]*",
)


def strip_academic_opening(text: str) -> str:
    """Remove aberturas acadêmicas que o modelo ignora no prompt."""
    result = (text or "").strip()
    if not result:
        return result
    changed = True
    while changed:
        changed = False
        for pattern in _FORBIDDEN_OPENINGS:
            new = re.sub(pattern, "", result, count=1, flags=re.IGNORECASE)
            if new != result:
                result = new.lstrip()
                changed = True
    if result and result[0].islower():
        result = result[0].upper() + result[1:]
    result = re.sub(r"\n{3,}", "\n\n", result).strip()
    return result
