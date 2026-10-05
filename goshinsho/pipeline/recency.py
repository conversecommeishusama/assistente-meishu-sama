"""Precedência temporal — texto mais recente tem prioridade sobre o mais antigo.

Regra do projeto (2026-10-05): o acervo cobre 1930-1955 e, por decisão explícita
do fundador, quando dois trechos tratam do MESMO assunto, o mais recente é a
formulação mais amadurecida e definitiva do ensinamento. Isso vale sobretudo
porque, antes do fim da perseguição religiosa (1945), Meishu-Sama registrou que
não podia falar abertamente (『明日の医術』 foi escrito "por verso", com
"裏表") — o texto posterior do mesmo tema é a versão esclarecida. Ver
`docs/LEVANTAMENTO_PRE_GUERRA_E_PERSEGUICAO_20261005.md`.

O bônus é DELIBERADAMENTE pequeno (mesma ordem do `content_score`, ±0.3): serve
para DESEMPATAR trechos de relevância comparável, nunca para fazer um trecho
antigo e central perder para um recente e periférico. Um trecho sem data
recebe 0.0 (neutro) — não se prefere o que não se conhece.
"""

from __future__ import annotations

import re

_YEAR_RE = re.compile(r"(\d{4})")

# Faixa do acervo (publicações de Meishu-Sama em vida).
_OLDEST_YEAR = 1930
_NEWEST_YEAR = 1955

# Bônus máximo (aplicado a 1955); linearmente 0.0 em 1930.
#
# CALIBRAÇÃO (2026-10-05): 0.10 é DELIBERADAMENTE menor que os sinais de
# conteúdo de `content_score` -- fala direta de Meishu-Sama (+0.18) e artigo
# doutrinário escrito (+0.24). Assim a recência DESEMPATA trechos de conteúdo
# comparável (mesmo assunto) sem nunca promover um trecho de data recente e
# conteúdo irrelevante por cima de um trecho antigo e central. Um primeiro
# valor de 0.30 foi reprovado por teste: ele invertia um trecho sem relação
# com a pergunta por cima de uma fala direta de Meishu-Sama a respeito dela.
_MAX_BONUS = 0.10


def meta_year(meta: dict | None) -> int | None:
    """Ano (int) de publicação do trecho, ou None se ausente/não reconhecido.

    Lê o campo `data` dos metadados (formatos observados: "1951" e
    "1951-12-25"). Retorna None fora da faixa plausível do acervo.
    """
    if not meta:
        return None
    raw = meta.get("data") or meta.get("data_sessao") or ""
    match = _YEAR_RE.search(str(raw))
    if not match:
        return None
    try:
        year = int(match.group(1))
    except (TypeError, ValueError):
        return None
    if not (_OLDEST_YEAR <= year <= _NEWEST_YEAR + 5):
        return None
    return year


def recency_bonus(meta: dict | None) -> float:
    """Bônus 0.0.._MAX_BONUS conforme a data — mais recente, maior.

    Sem data: 0.0 (neutro). A rampa é linear sobre a faixa do acervo, de modo
    que anos vizinhos quase não se diferenciam, mas eras distantes (1935 vs
    1955) sim.
    """
    year = meta_year(meta)
    if year is None:
        return 0.0
    span = _NEWEST_YEAR - _OLDEST_YEAR
    if span <= 0:
        return 0.0
    frac = (year - _OLDEST_YEAR) / span
    frac = min(max(frac, 0.0), 1.0)
    return round(_MAX_BONUS * frac, 4)
