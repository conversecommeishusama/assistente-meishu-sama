#!/usr/bin/env python3
"""Fase 1 da renomeação: renomeia FISICAMENTE os arquivos PT (fonte + staging)
e atualiza o campo `filename` dos specs de segmentação.

NÃO toca no conteúdo dos arquivos (apenas o nome). A tradução do nome vem do
mapeamento aprovado (reports/varredura_padronizacao/MAPEAMENTO_RENOMEACAO.json),
que foi gerado pela função de produção (translate_filename_to_pt) e aprovado
pelo usuário (137 nomes).

Uso:
    python3 scripts/renomeia_arquivos_fase1.py --dry-run   # só mostra o plano
    python3 scripts/renomeia_arquivos_fase1.py --aplicar   # renomeia de verdade
"""
from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
REV = RAIZ / "livros_publicacao_pt_revisado"
ST = RAIZ / "reports" / "livros_trabalho" / "pt"
SPEC = RAIZ / "reports" / "livros_trabalho" / "segmentacao_manual"
MAPA = RAIZ / "reports" / "varredura_padronizacao" / "MAPEAMENTO_RENOMEACAO.json"
BACKUP = RAIZ / "backups" / "renomeacao_fase1"


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    mapa = json.loads(MAPA.read_text(encoding="utf-8"))
    print(f"Total no mapeamento: {len(mapa)}")

    # validações de segurança
    novos = [m["novo"] for m in mapa]
    antigos = [m["antigo"] for m in mapa]
    assert len(set(novos)) == len(novos), "Nomes novos duplicados!"
    assert len(set(antigos)) == len(antigos), "Nomes antigos duplicados!"
    assert not (set(novos) & set(antigos)), "Colisão novo↔antigo!"

    # checagem: todos os arquivos existem nas duas pastas
    faltando = []
    for m in mapa:
        if not (REV / m["antigo"]).exists():
            faltando.append(("fonte", m["antigo"]))
        if not (ST / m["antigo"]).exists():
            faltando.append(("staging", m["antigo"]))
        if not (SPEC / f"{m['antigo']}.json").exists():
            faltando.append(("spec", m["antigo"]))
    if faltando:
        print(f"\nAVISO: {len(faltando)} arquivos/specs ausentes:")
        for tipo, nome in faltando[:20]:
            print(f"  [{tipo}] {nome}")
        print("(esses serão pulados)")

    if not aplicar:
        print("\n=== PLANO (dry-run) ===")
        for m in mapa:
            print(f"  {m['antigo']} -> {m['novo']}")
        print(f"\n{len(mapa)} renomeações planejadas.")
        print("Rode com --aplicar para executar.")
        return

    # aplicar
    carimbo = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bkp = BACKUP / carimbo
    bkp.mkdir(parents=True, exist_ok=True)

    ok = 0
    pulados = []
    for m in mapa:
        antigo, novo = m["antigo"], m["novo"]
        # backup dos originais
        for d in (REV, ST):
            src = d / antigo
            if src.exists() and not (bkp / src.name).exists():
                shutil.copy(src, bkp / src.name)
        sp = SPEC / f"{antigo}.json"
        if sp.exists() and not (bkp / sp.name).exists():
            shutil.copy(sp, bkp / sp.name)

        # renomear fonte e staging
        for d in (REV, ST):
            src = d / antigo
            if src.exists():
                src.rename(d / novo)
        # atualizar filename no spec + renomear o próprio spec
        if sp.exists():
            try:
                spec = json.loads(sp.read_text(encoding="utf-8"))
                if isinstance(spec, dict) and "filename" in spec:
                    spec["filename"] = novo
                    sp.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
                sp.rename(SPEC / f"{novo}.json")
            except Exception as e:
                print(f"  ERRO spec {antigo}: {e}")
        ok += 1

    print(f"\nRenomeados: {ok}")
    print(f"Backup: {bkp}")
    print(f"Pulados: {len(pulados)}")
    for p in pulados:
        print(f"  {p}")


if __name__ == "__main__":
    main()
