#!/usr/bin/env python3
"""Orquestra a retradução do Mioshie-shū 1-8 do ZERO com 8 workers paralelos.

Cada arquivo (1号..8号) é processado por UM processo `retraduzir_trechos.py`
(um "gunicorn"), em paralelo — decisão do usuário (docs/19: "8 gunicorns").

O script:
1. Confirma que os checkpoints atuais foram recolhidos (--zerar) ou faz backup.
2. Lança até N processos simultâneos (padrão 8).
3. Log por arquivo em /tmp/retrad_mioshie_8/<stem>.log.
4. Re-lança arquivo que falhar (retry até N tentativas).
5. Só termina quando TODOS os 8 arquivos estiverem 100% (todas as falas com
   pt_contextual) ou esgotarem as tentativas.

Uso:
  .venv/bin/python scripts/orquestrar_mioshie_8workers.py [--workers 8] [--retry 3]
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOG_DIR = Path("/tmp/retrad_mioshie_8")
LOG_DIR.mkdir(parents=True, exist_ok=True)
CKPT_DIR = RAIZ / "reports" / "retraducao_colecoes"
BACKUP_DIR = CKPT_DIR / "backup_pre_zerar_mioshie_20260819"

# Os 8 arquivos do Mioshie (escopo de retradução: 1-8; 9-33 = prosa, fora)
ARQUIVOS = [
    "textos_japones/19510920-御教え集1号.txt",
    "textos_japones/19511025-御教え集2号.txt",
    "textos_japones/19511125-御教え集3号.txt",
    "textos_japones/19511215-御教え集4号.txt",
    "textos_japones/19520115-御教え集5号.txt",
    "textos_japones/19510225-御教え集6号.txt",
    "textos_japones/19520320-御教え集7号.txt",
    "textos_japones/19520420-御教え集8号.txt",
]


def falas_completas(stem: str) -> int | None:
    """Retorna nº de falas com pt_contextual no checkpoint (None se não existe)."""
    ckpt = CKPT_DIR / f"{stem}.json"
    if not ckpt.exists():
        return None
    try:
        dados = json.loads(ckpt.read_text(encoding="utf-8"))
    except Exception:
        return None
    falas = dados.get("falas", {})
    if isinstance(falas, dict):
        falas = list(falas.values())
    return sum(1 for f in falas if isinstance(f, dict) and f.get("pt_contextual"))


def arquivo_pronto(stem: str) -> bool:
    """Pronto = checkpoint existe, tem falas e TODAS estão com pt_contextual.

    Mesmo critério de `arquivo_concluido` do retraduzir_trechos_massa.py:
    todas as falas do checkpoint preenchidas (n_falas > 0). Não basta ter 1.
    """
    ckpt = CKPT_DIR / f"{stem}.json"
    if not ckpt.exists():
        return False
    try:
        dados = json.loads(ckpt.read_text(encoding="utf-8"))
    except Exception:
        return False
    falas = dados.get("falas", {})
    if not falas:
        return False
    if isinstance(falas, dict):
        falas = list(falas.values())
    n_falas = len(falas)
    if n_falas <= 0:
        return False
    preenchidas = sum(1 for f in falas if isinstance(f, dict) and f.get("pt_contextual"))
    return preenchidas >= n_falas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--retry", type=int, default=3, help="tentativas por arquivo")
    args = ap.parse_args()
    workers = max(1, min(args.workers, 8))

    # Backup dos checkpoints atuais (corrompidos) ANTES de zerar
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    for arq in ARQUIVOS:
        stem = Path(arq).stem
        ckpt = CKPT_DIR / f"{stem}.json"
        if ckpt.exists():
            destino = BACKUP_DIR / ckpt.name
            if not destino.exists():
                shutil.copy2(ckpt, destino)
                print(f"[backup] {ckpt.name} -> {BACKUP_DIR.name}/", flush=True)

    # Apaga checkpoints atuais (retradução do ZERO — decisão do usuário)
    for arq in ARQUIVOS:
        stem = Path(arq).stem
        ckpt = CKPT_DIR / f"{stem}.json"
        if ckpt.exists():
            ckpt.unlink()
            print(f"[zerar] checkpoint {ckpt.name} apagado", flush=True)

    fila = list(ARQUIVOS)
    tentativas = {arq: 0 for arq in ARQUIVOS}
    ativos: dict[str, subprocess.Popen] = {}
    concluidos: dict[str, int] = {}

    print(f"\n[MIOSHIE 1-8] {len(fila)} arquivos | {workers} workers | retry={args.retry}", flush=True)

    while fila or ativos:
        # lança novos enquanto houver slot
        while fila and len(ativos) < workers:
            arq = fila.pop(0)
            stem = Path(arq).stem
            log_path = LOG_DIR / f"{stem}.log"
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(f"INICIO {time.strftime('%H:%M:%S')} | {arq}\n")
            proc = subprocess.Popen(
                [sys.executable, "scripts/retraduzir_trechos.py", "mioshie", arq],
                cwd=str(RAIZ),
                stdout=open(log_path, "a", encoding="utf-8"),
                stderr=subprocess.STDOUT,
            )
            ativos[arq] = proc
            tentativas[arq] += 1
            print(f"[{time.strftime('%H:%M:%S')}] lançado: {Path(arq).name} "
                  f"(tentativa {tentativas[arq]}, ativos={len(ativos)})", flush=True)

        # espera e checa
        time.sleep(15)
        for arq in list(ativos):
            if ativos[arq].poll() is not None:
                rc = ativos[arq].returncode
                del ativos[arq]
                stem = Path(arq).stem
                pronto = arquivo_pronto(stem)
                if rc == 0 and pronto:
                    concluidos[arq] = rc
                    print(f"[{time.strftime('%H:%M:%S')}] ✓ concluído: {Path(arq).name} "
                          f"(falas com PT: {falas_completas(stem)})", flush=True)
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] ✗ falhou rc={rc} pronto={pronto}: "
                          f"{Path(arq).name}", flush=True)
                    if tentativas[arq] < args.retry:
                        fila.append(arq)
                        print(f"    -> reenfileirando (tentativa {tentativas[arq]+1}/{args.retry})", flush=True)
                    else:
                        print(f"    -> esgotou {args.retry} tentativas; deixando para reavaliação", flush=True)

    print(f"\nOrquestração concluída: {len(concluidos)}/{len(ARQUIVOS)} arquivos")
    for arq in ARQUIVOS:
        stem = Path(arq).stem
        n = falas_completas(stem)
        print(f"  {stem}: {'OK (' + str(n) + ' falas PT)' if n else 'PENDENTE/FALHO'}")
    return 0 if len(concluidos) == len(ARQUIVOS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
