#!/usr/bin/env python3
"""Monitora os shards da retradução do Gokōwa-roku e avisa quando terminam.

Verifica periodicamente os checkpoints dos shards. Quando TODOS os shards
terminarem (intervalo completo processado):
  1. Consolida no checkpoint principal
  2. Gera o HTML final
  3. Registra aviso (log + arquivo de notificação)

Uso:
    python3 scripts/monitorar_shards_gokowa.py            # roda uma vez
    python3 scripts/monitorar_shards_gokowa.py --loop    # fica monitorando
    python3 scripts/monitorar_shards_gokowa.py --intervalo=60  # a cada 60s
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
OUT = RAIZ / "reports" / "amostragem_semantica_gokowa"
LOG = RAIZ / "logs" / "monitor_shards.log"
AVISO = OUT / "AVISO_SHARDS_CONCLUIDOS.txt"

# Total de falas (957 no Suplemento)
TOTAL_FALAS = 957


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def total_processado() -> int:
    total = 0
    arquivos = list(OUT.glob("laco_shard_*.json")) + list(OUT.glob("laco_intervalo_*.json"))
    for f in arquivos:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            total += len(d.get("falas", {}))
        except Exception:
            pass
    return total


def shards_ativos() -> int:
    """Conta shards com processo rodando (via ps)."""
    try:
        r = subprocess.run(
            ["pgrep", "-f", "laco_retraducao_shard"],
            capture_output=True, text=True,
        )
        return len([p for p in r.stdout.strip().split("\n") if p])
    except Exception:
        return 0


def main() -> None:
    loop = "--loop" in sys.argv
    intervalo = 60
    for a in sys.argv[1:]:
        if a.startswith("--intervalo"):
            intervalo = int(a.split("=")[1])

    while True:
        n_falas = total_processado()
        n_ativos = shards_ativos()

        if n_falas >= TOTAL_FALAS or (n_ativos == 0 and n_falas > 0):
            log(f"✅ SHARDS CONCLUÍDOS: {n_falas}/{TOTAL_FALAS} falas processadas | {n_ativos} processos ativos")
            log("Consolidando checkpoints...")
            r = subprocess.run(
                [sys.executable, str(RAIZ / "scripts" / "consolidar_shards_gokowa.py")],
                capture_output=True, text=True,
            )
            log(r.stdout.strip())

            log("Gerando JSON consolidado para auditoria externa...")
            # Gera um JSON consolidado limpo (JP | PT atual | PT contextual + status),
            # para ser auditado por ferramenta externa (ex: Claude) — sem HTML.
            dados_consolidados = json.loads(
                (OUT / "laco_retraducao_checkpoint.json").read_text(encoding="utf-8")
            )
            JSON_EXPORT = OUT / "retraducao_gokowa_para_auditoria.json"
            JSON_EXPORT.write_text(
                json.dumps(dados_consolidados, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log(f"JSON para auditoria salvo em {JSON_EXPORT}")

            # aviso
            AVISO.write_text(
                f"Shards concluídos em {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"Falas: {n_falas}/{TOTAL_FALAS}\n"
                f"JSON para auditoria: reports/amostragem_semantica_gokowa/retraducao_gokowa_para_auditoria.json\n",
                encoding="utf-8",
            )
            log(f"Aviso salvo em {AVISO}")
            if not loop:
                break

        else:
            log(f"⏳ Em andamento: {n_falas}/{TOTAL_FALAS} falas | {n_ativos} processos ativos")

        if not loop:
            break
        time.sleep(intervalo)


if __name__ == "__main__":
    main()
