#!/usr/bin/env python3
"""Correção pontual do texto publicado usando o executor melhorado (Papel 4).

Para cada fala problemática (catalogada), localiza o JP correspondente, retraduz
com o executor melhorado (contexto A+B + trava de glossário + reconstrução), e
substitui no arquivo publicado — com backup e validação.

Uso:
    python3 scripts/corrigir_publicado_pontual.py            # processa tudo
    python3 scripts/corrigir_publicado_pontual.py --caso=85  # só um caso
    python3 scripts/corrigir_publicado_pontual.py --dry-run  # só mostra
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

from retraducao_completa_gokowa import retraduzir, extrair_falas  # noqa: E402
from trava_glossario import verificar_trava_glossario  # noqa: E402

JP_FILE = RAIZ / "textos_japones" / "19480101-御光話録（補）.txt"
PT_FILE = RAIZ / "livros_publicacao_pt_revisado" / "19480101 - Gokōwa-roku (Suplemento).txt"
CATALOGO = RAIZ / "reports" / "amostragem_semantica_gokowa" / "casos_para_corrigir.json"


def carregar_casos() -> list[dict]:
    if not CATALOGO.exists():
        return []
    return json.loads(CATALOGO.read_text(encoding="utf-8"))


def localizar_pt(trecho_errado: str) -> tuple[int, str] | None:
    """Localiza a posição de um trecho no PT publicado."""
    texto = PT_FILE.read_text(encoding="utf-8")
    idx = texto.find(trecho_errado)
    if idx == -1:
        return None
    return idx, texto


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    casos = carregar_casos()
    if not casos:
        print("Nenhum caso catalogado. Crie reports/.../casos_para_corrigir.json")
        return

    # filtra caso específico
    for a in sys.argv[1:]:
        if a.startswith("--caso"):
            casos = [c for c in casos if str(c.get("id")) == a.split("=")[1]]

    print(f"Casos a corrigir: {len(casos)}")
    pt_texto = PT_FILE.read_text(encoding="utf-8")
    original = pt_texto
    backup = PT_FILE.with_suffix(".txt.bak_correcao_pontual")
    if not backup.exists():
        backup.write_text(original, encoding="utf-8")
        print(f"Backup: {backup.name}")

    # carregar falas JP para contexto
    falas_jp = extrair_falas(JP_FILE.read_text(encoding="utf-8"))

    for caso in casos:
        cid = caso.get("id")
        trecho_errado = caso.get("trecho_errado", "")
        if not trecho_errado or trecho_errado not in pt_texto:
            print(f"  [{cid}] trecho não encontrado no PT, pulando")
            continue

        # localizar a fala JP correspondente (por fragmento JP)
        frag_jp = caso.get("jp_fragmento", "")
        idx_jp = None
        if frag_jp:
            for i, (quem, jp) in enumerate(falas_jp):
                if frag_jp in jp:
                    idx_jp = i
                    break

        if idx_jp is None:
            print(f"  [{cid}] não localizou fala JP, pulando (usa edição guiada)")
            continue

        quem, jp = falas_jp[idx_jp]
        ctx = f"[{falas_jp[idx_jp-1][0]}] {falas_jp[idx_jp-1][1]}" if idx_jp > 0 else ""

        print(f"  [{cid}] retraduzindo fala JP {idx_jp}...", flush=True)
        novo_pt = retraduzir(jp, quem, max_retries=10, contexto_anterior=ctx)

        # validação: trava de glossário
        ok, motivo = verificar_trava_glossario(jp, novo_pt)
        if not ok:
            print(f"    ⚠️ trava glossário falhou: {motivo} — mantendo e retry")
            novo_pt = retraduzir(jp, quem, max_retries=8, contexto_anterior=ctx)

        if dry_run:
            print(f"    [dry] PT atual: {pt_texto[pt_texto.find(trecho_errado):pt_texto.find(trecho_errado)+80]}...")
            print(f"    [dry] PT novo : {novo_pt[:80]}...")
            continue

        # substituir
        pt_texto = pt_texto.replace(trecho_errado, novo_pt, 1)
        print(f"    ✅ substituído (novo: {novo_pt[:60]}...)")

    if not dry_run:
        PT_FILE.write_text(pt_texto, encoding="utf-8")
        print(f"\nGravado. Alterações: {sum(1 for c in casos if c.get('trecho_errado','') in pt_texto)}")
        print("Nota: verificar manualmente os casos que não localizaram JP.")


if __name__ == "__main__":
    main()
