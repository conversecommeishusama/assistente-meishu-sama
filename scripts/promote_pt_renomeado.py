#!/usr/bin/env python3
"""Promove reports/livros_trabalho/pt (nomes novos PT) para textos_portugues,
gerenciando a renomeação (remove os nomes antigos que foram substituídos).

Cenário: o PT foi renomeado (128 arquivos com novos nomes portugueses) e o
staging tem o conteúdo final (Fase 2). O textos_portugues (fonte do rebuild)
ainda tem os nomes antigos. Este script:

1. Copia os 137 arquivos do staging (nomes novos) para textos_portugues.
2. Remove de textos_portugues os nomes ANTIGOS que foram renomeados
   (via mapeamento), mantendo:
   - os 9 periódicos que não mudaram (Eiko, Hikari, Kyusei, ...)
   - os 8 extras sem spec (Keiko, Relatos_de_Milagres, 未刊行, ...)
3. Backup timestampado dos arquivos removidos/substituídos.
4. Relatório.

O JP NÃO é renomeado — textos_japones mantém os nomes originais.

Uso:
    python3 scripts/promote_pt_renomeado.py             # dry-run
    python3 scripts/promote_pt_renomeado.py --apply
"""
from __future__ import annotations

import json
import shutil
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
STAGING = PROJECT_ROOT / "reports" / "livros_trabalho" / "pt"
TARGET = PROJECT_ROOT / "textos_portugues"
MAPA_PATH = PROJECT_ROOT / "reports" / "varredura_padronizacao" / "MAPEAMENTO_RENOMEACAO_TXT.json"
BACKUP_ROOT = PROJECT_ROOT / "backups" / "promote_pt_renomeado"


def main() -> None:
    aplicar = "--apply" in sys.argv
    mapa = json.loads(MAPA_PATH.read_text(encoding="utf-8"))
    # nome antigo -> nome novo
    antigo_para_novo = {m["antigo"]: m["novo"] for m in mapa}
    novos = {m["novo"] for m in mapa}

    staging_files = {f.name: f for f in STAGING.glob("*.txt")}
    target_files = {f.name: f for f in TARGET.glob("*.txt")}

    print(f"Staging PT: {len(staging_files)} | Target (textos_portugues): {len(target_files)}")

    # 1. Arquivos a copiar do staging (nomes novos)
    a_copiar = [n for n in staging_files if n in novos or n not in antigo_para_novo]
    # 2. Nomes antigos a remover do target (que foram renomeados)
    a_remover = [antigo for antigo, novo in antigo_para_novo.items()
                 if antigo != novo and antigo in target_files]
    # 3. Extras a manter (não no mapeamento)
    extras = [n for n in target_files if n not in antigo_para_novo and n not in novos]

    print(f"A copiar (staging->target): {len(a_copiar)}")
    print(f"A remover (nomes antigos renomeados): {len(a_remover)}")
    print(f"Extras mantidos: {len(extras)}")

    if not aplicar:
        print("\n=== DRY-RUN (use --apply) ===")
        for n in a_copiar[:8]:
            print(f"  copiar: {n}")
        for n in a_remover[:8]:
            print(f"  remover: {n}")
        return

    carimbo = time.strftime('%Y%m%dT%H%M%SZ')
    backup = BACKUP_ROOT / carimbo
    backup.mkdir(parents=True, exist_ok=True)

    # Copiar novos
    copiados = 0
    for nome in a_copiar:
        src = staging_files[nome]
        dst = TARGET / nome
        if dst.exists():
            shutil.copy2(dst, backup / f"substituido_{nome}")
        shutil.copy2(src, dst)
        copiados += 1

    # Remover antigos renomeados
    removidos = 0
    for nome in a_remover:
        f = TARGET / nome
        if f.exists():
            shutil.copy2(f, backup / f"removido_{nome}")
            f.unlink()
            removidos += 1

    print(f"\nCopiados: {copiados} | Removidos: {removidos}")
    print(f"Backup: {backup}")
    print(f"Target agora: {len(list(TARGET.glob('*.txt')))} arquivos")


if __name__ == "__main__":
    main()
