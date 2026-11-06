#!/usr/bin/env python3
"""Fase 1 da renomeação: renomeia fisicamente os arquivos PT + atualiza specs.

Seguro e mecânico (NÃO toca o conteúdo dos arquivos):
1. Backup completo das pastas staging + revisado + specs.
2. Para cada obra do mapeamento aprovado:
   - renomeia o arquivo em reports/livros_trabalho/pt/ e livros_publicacao_pt_revisado/
   - atualiza o campo `filename` do spec (segmentacao_manual/<nome>.json)
   - valida que o conteudo não mudou (md5 antes/depois do conteúdo)
3. Relatório final.

JP NÃO é renomeado (mantém nomes originais).

Uso:
    python3 scripts/renomear_arquivos_fase1.py [--aplicar]
    (sem --aplicar = dry-run, só mostra o que faria)
"""
from __future__ import annotations

import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
PT = RAIZ / "reports/livros_trabalho/pt"
REV = RAIZ / "livros_publicacao_pt_revisado"
SPEC = RAIZ / "reports/livros_trabalho/segmentacao_manual"
MAPA_PATH = RAIZ / "reports/varredura_padronizacao" / "MAPEAMENTO_RENOMEACAO_TXT.json"


def md5(b: bytes) -> str:
    return hashlib.md5(b).hexdigest()


def main() -> None:
    aplicar = "--aplicar" in sys.argv
    mapa = json.loads(MAPA_PATH.read_text(encoding="utf-8"))
    a_renomear = [m for m in mapa if m["antigo"] != m["novo"]]
    print(f"Total: {len(mapa)} | a renomear: {len(a_renomear)} | sem mudança: {len(mapa)-len(a_renomear)}")

    if not aplicar:
        print("\n=== DRY-RUN (use --aplicar para executar) ===")
        for m in a_renomear[:10]:
            print(f"  {m['antigo']}  ->  {m['novo']}")
        print(f"  ... e mais {len(a_renomear)-10} arquivos")
        return

    carimbo = time.strftime('%Y%m%dT%H%M%SZ')
    backup = RAIZ / "backups" / f"pre_renomeacao_fase1_{carimbo}"
    for sub in ("pt_staging", "pt_revisado", "specs"):
        (backup / sub).mkdir(parents=True, exist_ok=True)

    relatorio = {"carimbo": carimbo, "renomeados": [], "erros": []}
    for m in a_renomear:
        antigo, novo = m["antigo"], m["novo"]
        try:
            # Backup
            for pasta, sub in ((PT, "pt_staging"), (REV, "pt_revisado")):
                f = pasta / antigo
                if f.exists():
                    shutil.copy(f, backup / sub / antigo)
            # Renomear staging + revisado
            for pasta in (PT, REV):
                f, fn = pasta / antigo, pasta / novo
                if not f.exists():
                    raise FileNotFoundError(f"fonte ausente: {pasta.name}/{antigo}")
                if fn.exists():
                    raise FileExistsError(f"destino já existe: {pasta.name}/{novo}")
                f.rename(fn)
            # Spec: atualizar filename
            spec_path = SPEC / f"{antigo}.json"
            if spec_path.exists():
                shutil.copy(spec_path, backup / "specs" / f"{antigo}.json")
                spec = json.loads(spec_path.read_text(encoding="utf-8"))
                spec["filename"] = novo
                spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=1), encoding="utf-8")
            relatorio["renomeados"].append({"antigo": antigo, "novo": novo})
            print(f"  OK {antigo} -> {novo}")
        except Exception as e:
            relatorio["erros"].append({"antigo": antigo, "novo": novo, "erro": str(e)[:120]})
            print(f"  ERRO {antigo}: {str(e)[:80]}")

    # Verificação final: conteúdo não mudou (md5 do arquivo renomeado vs backup)
    print("\n=== Verificação de conteúdo (md5 renomeado vs backup) ===")
    n_ok = 0
    for r in relatorio["renomeados"]:
        antigo, novo = r["antigo"], r["novo"]
        b = backup / "pt_staging" / antigo
        f = PT / novo
        if b.exists() and f.exists() and md5(b.read_bytes()) == md5(f.read_bytes()):
            n_ok += 1
        else:
            print(f"  CONTEÚDO DIFERENTE: {novo}")
    print(f"Conteúdo preservado: {n_ok}/{len(relatorio['renomeados'])}")

    out = RAIZ / "reports" / "varredura_padronizacao" / f"RELATORIO_RENOMEACAO_FASE1_{carimbo}.json"
    out.write_text(json.dumps(relatorio, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nRelatório: {out}")
    print(f"Backup: {backup}")
    print(f"Renomeados: {len(relatorio['renomeados'])} | Erros: {len(relatorio['erros'])}")


if __name__ == "__main__":
    main()
