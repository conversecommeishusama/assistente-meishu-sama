#!/usr/bin/env python3
"""Fase Inicial — reconfirmação da segmentação pelo critério autoral.

Diagnóstico apenas (não altera nenhum spec). Aplica à totalidade dos
livros_trabalho, EXCETO Gokōwa (que será tratado à parte, no fim, por ser
mais complexo).

Sinais avaliados por livro:
  1. Excesso: densidade (trechos / 1000 chars JP) fora da faixa de referência
     calibrada nos livros já reconfirmados (Jikan, Koza, autor-estruturado).
  2. Metadado infiltrado: título de trecho bate com classificador de
     metadado editorial (mesmo usado no Jikan Sosho).
  3. Método antigo: split_method não pertence ao conjunto já reconfirmado
     nesta leva (ou não é um método dedicado a este único livro).
  4. Sub-segmentação: livro grande com poucos trechos (monólito disfarçado).

Saída: reports/livros_trabalho/segmentacao_manual/FASE_INICIAL_RECONFIRMACAO.json
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jp_line_split import _is_editorial_metadata_line, _is_jikan_metadata_line  # noqa: E402

ROOT = "/var/www/goshinsho"
SPECS_DIR = os.path.join(ROOT, "reports/livros_trabalho/segmentacao_manual")
JP_DIR = os.path.join(ROOT, "reports/livros_trabalho/jp")

GOKOWA_MARK = "御光話録"

# Métodos já reconfirmados nesta leva (critério autoral aplicado e validado
# manualmente contra o texto-fonte, um a um, na Fase Inicial).
RECONFIRMED_METHODS = {
    "line_jikan_structural",
    "line_jikan_csv_poems",
    "line_johrei_koza_structural",
    "line_kannon_koza",
    "line_author_structure",
    "line_yamamizu_date_session",  # 山と水: diário por data, sessão pode ser longa
    "line_ochishiji_date",  # 御垂示録: sessão por data, sem sub-divisão do autor
    "line_csv_hymn",  # 御讃歌集: 1 hino = 1 unidade do autor (densidade alta é normal)
    "line_miracle",  # 世界救世教奇蹟集: byline (igreja+nome+idade) é o título legítimo
    "line_bracket_testimony",  # relatos com capítulo 〔...〕 + testemunho individual
    "line_shinko_generic",  # 天国の福音書: já revisto, resíduo de falso positivo é marginal
}

# Documentos muito curtos: um único segmento é normal, não é sinal de problema.
TRIVIAL_DOC_CHARS = 5000

# Faixa de referência calibrada empiricamente nos livros já reconfirmados
# (trechos por 1000 caracteres JP, sem espaços/quebras de linha).
DENSITY_LOW = 0.10
DENSITY_HIGH = 4.00

# Sub-segmentação: livro grande com poucos trechos.
SUBSEG_MIN_CHARS = 30000
SUBSEG_MAX_ARTICLES = 5


@dataclass
class Diagnóstico:
    filename: str
    split_method: str
    n_articles: int
    jp_chars: int
    density: float
    sinais: list[str] = field(default_factory=list)
    categoria: str = "segmentacao_ok"


def jp_char_count(fname: str) -> int:
    path = os.path.join(JP_DIR, fname)
    if not os.path.exists(path):
        return -1
    with open(path, encoding="utf-8") as fh:
        txt = fh.read()
    return len(txt.replace("\n", "").replace(" ", "").replace("\u3000", ""))


def check_titles_metadata(articles: list[dict]) -> int:
    hits = 0
    for art in articles:
        title = (art.get("title_jp") or "").strip()
        if not title or len(title) < 4:
            continue
        if _is_jikan_metadata_line(title) or _is_editorial_metadata_line(title):
            hits += 1
    return hits


def diagnose(spec_path: str) -> Diagnóstico | None:
    with open(spec_path, encoding="utf-8") as fh:
        d = json.load(fh)

    if not isinstance(d, dict) or "articles" not in d or not isinstance(d.get("articles"), list):
        return None  # não é um spec de livro (manifesto/relatório/fila de controlo)

    fname = d.get("filename") or os.path.basename(spec_path)[:-5]
    if GOKOWA_MARK in fname:
        return None

    articles = d.get("articles", [])
    n = len(articles)
    method = d.get("split_method") or d.get("method") or "?"
    chars = jp_char_count(fname)
    density = (n / (chars / 1000)) if chars > 0 else 0.0

    diag = Diagnóstico(filename=fname, split_method=method, n_articles=n, jp_chars=chars, density=round(density, 3))

    if method in RECONFIRMED_METHODS:
        if chars > TRIVIAL_DOC_CHARS and n <= 1:
            diag.sinais.append(f"metodo_reconfirmado_mas_monolito(1 trecho em {chars} chars)")
            diag.categoria = "duvidoso_amostrar"
            return diag
        diag.categoria = "segmentacao_ok"
        diag.sinais.append("metodo_ja_reconfirmado")
        return diag

    if 0 < chars < TRIVIAL_DOC_CHARS and n <= 2:
        diag.categoria = "segmentacao_ok"
        diag.sinais.append("documento_trivial_curto")
        return diag

    if chars < 0:
        diag.sinais.append("jp_source_nao_encontrado")
        diag.categoria = "duvidoso_amostrar"
        return diag

    meta_hits = check_titles_metadata(articles)
    meta_ratio = (meta_hits / n) if n else 0.0

    excesso = density > DENSITY_HIGH
    subseg = chars >= SUBSEG_MIN_CHARS and n <= SUBSEG_MAX_ARTICLES
    monolito_nao_trivial = chars > TRIVIAL_DOC_CHARS and n <= 2
    metadado_infiltrado = meta_hits >= 2 or meta_ratio >= 0.15

    if excesso:
        diag.sinais.append(f"excesso_densidade({diag.density}/1k > {DENSITY_HIGH})")
    if subseg:
        diag.sinais.append(f"sub_segmentacao({n} trechos em {chars} chars)")
    if monolito_nao_trivial:
        diag.sinais.append(f"monolito_nao_trivial({n} trechos em {chars} chars > {TRIVIAL_DOC_CHARS})")
    if metadado_infiltrado:
        diag.sinais.append(f"metadado_infiltrado({meta_hits}/{n} titulos)")
    if density < DENSITY_LOW and chars >= SUBSEG_MIN_CHARS:
        diag.sinais.append(f"densidade_muito_baixa({diag.density}/1k)")

    if excesso or subseg or monolito_nao_trivial or metadado_infiltrado:
        diag.categoria = "precisa_ressegmentar"
    elif density < DENSITY_LOW and chars >= SUBSEG_MIN_CHARS:
        diag.categoria = "duvidoso_amostrar"
    else:
        diag.categoria = "segmentacao_ok"

    return diag


def main() -> None:
    specs = sorted(
        f for f in os.listdir(SPECS_DIR)
        if f.endswith(".json") and "TRIAGEM" not in f and "FASE_INICIAL" not in f
    )

    results: list[Diagnóstico] = []
    for sp in specs:
        d = diagnose(os.path.join(SPECS_DIR, sp))
        if d is not None:
            results.append(d)

    by_cat: dict[str, list[str]] = {"segmentacao_ok": [], "precisa_ressegmentar": [], "duvidoso_amostrar": []}
    for r in results:
        by_cat[r.categoria].append(r.filename)

    out = {
        "total_avaliados": len(results),
        "excluidos_gokowa": True,
        "resumo": {k: len(v) for k, v in by_cat.items()},
        "categorias": by_cat,
        "detalhe": [
            {
                "filename": r.filename,
                "split_method": r.split_method,
                "n_articles": r.n_articles,
                "jp_chars": r.jp_chars,
                "density": r.density,
                "sinais": r.sinais,
                "categoria": r.categoria,
            }
            for r in results
        ],
    }

    out_path = os.path.join(SPECS_DIR, "FASE_INICIAL_RECONFIRMACAO.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=2)

    print(f"Total avaliado (excl. Gokōwa): {len(results)}")
    for k, v in by_cat.items():
        print(f"  {k}: {len(v)}")
    print(f"\nSaída: {out_path}")


if __name__ == "__main__":
    main()
