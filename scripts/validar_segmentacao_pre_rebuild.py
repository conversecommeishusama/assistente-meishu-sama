#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Validação READ-ONLY da segmentação antes de um rebuild dos índices.

Espelha **exactamente** o que `scripts/build_clean_large_indexes.py` faz em
`article_entries_from_spec()`. Esse comportamento tem duas armadilhas que
justificam este script:

1. **`approved` é ignorado no rebuild.** `apply_manual_livros_segmentacao.py`
   exige `approved=true`, mas `build_clean_large_indexes.py` usa qualquer spec.
   Validar só as aprovadas daria a falsa impressão de que está tudo bem
   (medido: apenas 2 specs têm `approved=true`, mas o rebuild usa as 137).
2. **Falha de âncora é silenciosa.** Se uma âncora não resolver, estiver vazia,
   ou o nº de chunks ≠ nº de artigos, `article_entries_from_spec` devolve `None`
   e quem chama **cai para o arquivo inteiro como 1 bloco** — sem erro. O artigo
   extra desaparece e o livro inteiro vira um chunk gigante (que trunca no
   embedding e5-large a 512 tokens ≈ 3200 chars).

Para cada spec, o script corta PT e JP com a MESMA `split_by_anchors` do rebuild e
classifica o resultado. Não escreve nada.

⚠️ **O corte é feito sobre `clean_body()`, não sobre o texto cru.** O rebuild
chama `clean_body(read_text(path))`; âncoras que parecem "erradas" no texto cru
podem estar certas no texto limpo (que remove `#T/#K/#W`/separadores e normaliza
as quebras de linha 4→3). Ver `GOSHINSHO.md` §"Integridade PT vs JP": "NUNCA
corrigir uma âncora sem rodar a validação contra o texto limpo primeiro".

Uso:
    .venv/bin/python scripts/validar_segmentacao_pre_rebuild.py
    .venv/bin/python scripts/validar_segmentacao_pre_rebuild.py --detalhe
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ / "scripts"))
sys.path.insert(0, str(RAIZ))

from apply_manual_livros_segmentacao import split_by_anchors  # noqa: E402
from build_clean_large_indexes import clean_body  # noqa: E402

SPECS = RAIZ / "reports" / "livros_trabalho" / "segmentacao_manual"
PT = RAIZ / "textos_portugues"
JP = RAIZ / "textos_japones"
MAPA = RAIZ / "reports" / "varredura_padronizacao" / "MAPEAMENTO_RENOMEACAO_TXT.json"
LIMITE_EMBEDDING = 3200


def _mapa() -> dict[str, str]:
    if not MAPA.exists():
        return {}
    try:
        return {i["novo"]: i["antigo"]
                for i in json.loads(MAPA.read_text(encoding="utf-8"))}
    except Exception:
        return {}


def _texto(caminho: Path) -> str:
    """Texto como o rebuild o vê: `clean_body(read_text())`."""
    return clean_body(caminho.read_text(encoding="utf-8", errors="replace"))


def _valida(caminho: Path, anchors: list[str]) -> str:
    """Devolve '' se segmenta; senão a razão (mesma regra do rebuild)."""
    if not caminho.exists():
        return "ficheiro ausente"
    if not all(a.strip() for a in anchors):
        vazias = sum(1 for a in anchors if not a.strip())
        return f"{vazias} âncora(s) vazia(s) -> rebuild cai para arquivo inteiro"
    try:
        chunks = split_by_anchors(_texto(caminho), anchors, label=caminho.name)
    except ValueError as exc:
        return f"âncora não resolve: {str(exc)[:150]}"
    if len(chunks) != len(anchors):
        return f"{len(chunks)} chunks != {len(anchors)} artigos"
    return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--detalhe", action="store_true")
    args = ap.parse_args()

    ren = _mapa()
    specs = sorted(SPECS.glob("*.txt.json"))
    print(f"specs: {len(specs)} (o rebuild usa TODAS -- 'approved' nao e filtro)\n")

    ok_pt = ok_jp = 0
    falhas: list[tuple[str, str, str]] = []
    mono: list[str] = []
    grandes: list[tuple[str, int, int]] = []

    for sp in specs:
        try:
            spec = json.loads(sp.read_text(encoding="utf-8"))
        except Exception as exc:
            falhas.append((sp.name, "spec", f"ilegivel: {exc}"))
            continue
        nome = spec.get("filename") or sp.name[: -len(".json")]
        arts = spec.get("articles") or []
        if len(arts) <= 1:
            mono.append(nome)
            continue

        for rot, pasta, campo in (("PT", PT, "pt_anchor"),
                                  ("JP", JP, "jp_anchor")):
            nome_arq = nome if rot == "PT" else ren.get(nome, nome)
            anchors = [a.get(campo) or "" for a in arts]
            erro = _valida(pasta / nome_arq, anchors)
            if erro:
                falhas.append((nome, rot, erro))
            elif rot == "PT":
                ok_pt += 1
                try:
                    chunks = split_by_anchors(_texto(PT / nome_arq), anchors,
                                              label="pt")
                    gordos = [len(c) for c in chunks
                              if len(c) > LIMITE_EMBEDDING]
                    if gordos:
                        grandes.append((nome, len(gordos), max(gordos)))
                except ValueError:
                    pass
            else:
                ok_jp += 1

    print(f"PT segmenta : {ok_pt}")
    print(f"JP segmenta : {ok_jp}")
    print(f"specs com <=1 artigo (monolito por desenho): {len(mono)}")
    print(f"falhas      : {len(falhas)}")

    if falhas:
        print(f"\n### falhas ({len(falhas)})")
        for i, (nome, rot, msg) in enumerate(falhas):
            if args.detalhe or i < 40:
                print(f"  [{rot}] {nome[:56]:56} {msg[:130]}")
        if not args.detalhe and len(falhas) > 40:
            print(f"  ... +{len(falhas) - 40} (use --detalhe)")

    if grandes:
        print(f"\n### artigos > {LIMITE_EMBEDDING} chars -- truncam no embedding "
              f"({len(grandes)} ficheiros)")
        for nome, n, maior in sorted(grandes, key=lambda x: -x[2])[:15]:
            print(f"  {nome[:58]:58} {n:3} artigos . maior {maior:,}")

    return 1 if falhas else 0


if __name__ == "__main__":
    raise SystemExit(main())
