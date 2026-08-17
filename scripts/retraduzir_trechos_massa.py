#!/usr/bin/env python3
"""Orquestra a retradução por TRECHOS de todas as coleções de diálogos orais.

Método aprovado (17/08): agrupamento por trechos de ~2000 chars + fluxo 2 etapas
(tradução contínua → rotulação) + relatório de glossário.

Escopo (diálogos truncados apenas):
  - gokowa: 御光話録 1-19 + Suplemento (補)
  - gosuiji: 御垂示録 1-30
  - mioshie: 御教え集 1-8  (9-33 = prosa contínua, FORA)

Antes de processar cada arquivo, faz backup do checkpoint existente (se houver)
em reports/retraducao_colecoes/backup_pre_trechos/ para permitir retradução do
zero sem perda.

Uso:
  .venv/bin/python scripts/retraduzir_trechos_massa.py <gokowa|gosuiji|mioshie>
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TEXTOS = RAIZ / "textos_japones"
OUT = RAIZ / "reports" / "retraducao_colecoes"
BACKUP = OUT / "backup_pre_trechos"

sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))
from retraduzir_colecao import EXTRATORES  # noqa: E402

# Escopo por coleção (diálogos truncados apenas)
PADROES = {
    "gokowa": "*御光話録*.txt",      # 1-19 + Suplemento (補)
    "gosuiji": "*御垂示録*.txt",      # 1-30
    "mioshie": "*御教え集*.txt",      # filtrar 1-8 abaixo
}
MIOSHIE_MAX = 8  # só 1-8 (9-33 = prosa contínua, fora)


def arquivo_no_escopo(colecao: str, nome: str) -> bool:
    if colecao == "gokowa":
        # inclui 1-19 (御光話録N号) E o Suplemento (御光話録（補）)
        return "御光話録" in nome
    if colecao != "mioshie":
        return True
    # mioshie: só números 1-8 (formato 御教え集N号)
    import re
    m = re.search(r"御教え集(\d+)号", nome)
    if not m:
        return False
    return int(m.group(1)) <= MIOSHIE_MAX


def arquivo_concluido(ckpt_path: Path, n_falas: int) -> bool:
    if not ckpt_path.exists():
        return False
    try:
        dados = json.loads(ckpt_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    falas = dados.get("falas", {})
    if isinstance(falas, list):
        return False
    preenchidas = sum(1 for f in falas.values() if f.get("pt_contextual"))
    return preenchidas >= n_falas and n_falas > 0


def main() -> None:
    if len(sys.argv) < 2:
        print("uso: .venv/bin/python scripts/retraduzir_trechos_massa.py <gokowa|gosuiji|mioshie> [--zerar]")
        print("  --zerar: apaga checkpoints (retraduzir do zero). SEM a flag, retoma do checkpoint.")
        sys.exit(1)
    colecao = sys.argv[1]
    zerar = "--zerar" in sys.argv
    if colecao not in PADROES:
        print(f"coleção inválida: {colecao}")
        sys.exit(1)

    arquivos = sorted(TEXTOS.glob(PADROES[colecao]))
    arquivos = [a for a in arquivos if arquivo_no_escopo(colecao, a.name)]
    print(f"[{colecao}] {len(arquivos)} arquivos de diálogo no escopo | zerar={zerar}")
    BACKUP.mkdir(parents=True, exist_ok=True)

    for i, arq in enumerate(arquivos, 1):
        ckpt = OUT / f"{arq.stem}.json"

        # nº real de falas do EXTRATOR (para saber se o arquivo já está completo)
        try:
            n_falas = len(EXTRATORES[colecao](arq.read_text(encoding="utf-8")))
        except Exception:
            n_falas = 0

        # FIX 17/08: SEM --zerar, NÃO apagar checkpoint de arquivo concluído
        # (retomada segura — o reinício anterior apagava checkpoints e perdia
        # progresso). Só apaga com --zerar (retradução do zero deliberada).
        if zerar:
            if ckpt.exists():
                destino = BACKUP / f"{ckpt.name}.bak_pre_trechos"
                if not destino.exists():
                    shutil.copy2(ckpt, destino)
                    print(f"  [{i}/{len(arquivos)}] {arq.name}: backup em {destino.name}")
                ckpt.unlink()
                print(f"  [{i}/{len(arquivos)}] {arq.name}: checkpoint apagado (--zerar)")
        elif arquivo_concluido(ckpt, n_falas):
            print(f"  [{i}/{len(arquivos)}] {arq.name}: JÁ CONCLUÍDO, pulando")
            continue

        print(f"  [{i}/{len(arquivos)}] {arq.name}: retraduzindo por trechos...", flush=True)
        r = subprocess.run(
            [sys.executable, "scripts/retraduzir_trechos.py", colecao, str(arq)],
            cwd=str(RAIZ),
        )
        if r.returncode != 0:
            print(f"  ERRO ao processar {arq.name} (code {r.returncode}) — seguindo", flush=True)

    print(f"\n[{colecao}] Orquestração por trechos concluída: {len(arquivos)} arquivos")


if __name__ == "__main__":
    main()
