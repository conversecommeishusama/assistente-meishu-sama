#!/usr/bin/env python3
"""Orquestra a retradução dos Mioshie 9-33 (PROSA CONTÍNUA) em PARALELO.

Os Mioshie 9-33 (御教え集 9号-33号) são prosa contínua (não diálogo) e precisam
passar por TODO o pipeline: tradução → auditoria → ajuste → revisão semântica.

Este orquestrador:
  - Lista os arquivos 9-33 em textos_japones/.
  - Processa em PARALELO com N workers (default 10 = limite de gunicorns), cada
    um chamando `retraduzir_trechos.py mioshie_prosa <arquivo>`.
  - Faz backup do checkpoint existente antes de reprocessar (segurança).
  - É retomável: pula arquivos já concluídos (checkpoint com todos os trechos
    t{n} preenchidos).

Uso:
  .venv/bin/python scripts/retraduzir_mioshie_prosa_massa.py [--workers N] [--zerar] [--inicio N]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TEXTOS = RAIZ / "textos_japones"
OUT = RAIZ / "reports" / "retraducao_colecoes"
BACKUP = OUT / "backup_pre_trechos"

MIN_EDICAO = 9
MAX_EDICAO = 33
COLECAO = "mioshie_prosa"


def arquivos_prosa() -> list[Path]:
    """Lista os arquivos 9-33 (prosa contínua) em ordem."""
    import re
    arquivos = []
    for p in sorted(TEXTOS.glob("*御教え集*号.txt")):
        m = re.search(r"御教え集(\d+)号", p.name)
        if not m:
            continue
        n = int(m.group(1))
        if MIN_EDICAO <= n <= MAX_EDICAO:
            arquivos.append(p)
    return arquivos


def trechos_concluidos(ckpt: dict, n_trechos: int) -> bool:
    """True se todos os trechos t{n} do checkpoint têm pt_contextual."""
    falas = ckpt.get("falas", {})
    preench = sum(1 for f in falas.values() if f.get("pt_contextual"))
    return preench >= n_trechos and n_trechos > 0


def processar_um(arq: Path, zerar: bool) -> str:
    ckpt = OUT / f"{arq.stem}.json"
    nome = arq.name
    # backup pré-reprocessamento (segurança — regra do projeto)
    if zerar and ckpt.exists():
        BACKUP.mkdir(parents=True, exist_ok=True)
        destino = BACKUP / f"{ckpt.name}.bak_pre_trechos"
        if not destino.exists():
            shutil.copy2(ckpt, destino)
        ckpt.unlink()
    # se já concluído (sem --zerar), pula
    if not zerar and ckpt.exists():
        try:
            dados = json.loads(ckpt.read_text(encoding="utf-8"))
            # estima nº de trechos pelo nº de blocos do extrator
            sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(RAIZ / "scripts"))
            from retraduzir_colecao import EXTRATORES  # noqa
            n_blocos = len(EXTRATORES[COLECAO](arq.read_text(encoding="utf-8")))
            n_trechos = max(1, (n_blocos + 4) // 5)  # ~5 blocos/trecho (2000/400)
            if trechos_concluidos(dados, n_trechos):
                return f"[PULA] {nome} (já concluído)"
        except Exception:
            pass
    r = subprocess.run(
        [sys.executable, "scripts/retraduzir_trechos.py", COLECAO, str(arq)],
        cwd=str(RAIZ),
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return f"[ERRO] {nome}: {r.stderr[-300:] or r.stdout[-300:]}"
    # linha final do log = resumo
    ultima = [l for l in r.stdout.splitlines() if l.strip()][-1:] or [""]
    return f"[OK] {nome} | {ultima[0]}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=10, help="workers em paralelo (default 10)")
    ap.add_argument("--zerar", action="store_true", help="reprocessar do zero (com backup)")
    ap.add_argument("--inicio", type=int, default=MIN_EDICAO, help="edição inicial")
    args = ap.parse_args()

    arquivos = [a for a in arquivos_prosa() if int(a.name.split("御教え集")[1].split("号")[0]) >= args.inicio]
    if not arquivos:
        print("nenhum arquivo 9-33 encontrado")
        return 1

    print(f"[{COLECAO}] {len(arquivos)} arquivos (edição {args.inicio}-{MAX_EDICAO}) | workers={args.workers} | zerar={args.zerar}")

    resultados = []
    inicio_geral = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futuros = {ex.submit(processar_um, arq, args.zerar): arq.name for arq in arquivos}
        for i, fut in enumerate(as_completed(futuros), 1):
            nome = futuros[fut]
            try:
                res = fut.result()
            except Exception as e:  # noqa: BLE001
                res = f"[ERRO] {nome}: {e}"
            resultados.append(res)
            print(f"  ({i}/{len(arquivos)}) {res}", flush=True)

    # resumo final
    ok = sum(1 for r in resultados if r.startswith("[OK]"))
    pula = sum(1 for r in resultados if r.startswith("[PULA]"))
    erro = sum(1 for r in resultados if r.startswith("[ERRO]"))
    print(f"\n=== Resumo: {ok} OK | {pula} pulados | {erro} erros | tempo {(time.time()-inicio_geral)/60:.1f} min ===")
    for r in resultados:
        if r.startswith("[ERRO]"):
            print(f"  {r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
