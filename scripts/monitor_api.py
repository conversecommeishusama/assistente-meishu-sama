#!/usr/bin/env python3
"""Monitor de saúde da API DeepSeek + processos de retradução.

Roda em loop a cada INTERVALO (default 30s) por DURACAO (default 30 min),
coletando:
- Nº de processos python de retradução ativos (mioshie/gosuiji).
- Tempo de resposta de uma chamada de teste à API DeepSeek (mede latência).
- Contagem de retries (resposta vazia) nos logs recentes das massas.
- Erros de API (429/rate limit/timeout) nos logs recentes.

Loga cada leitura em logs/monitor_api.log (append) e imprime na saída.

Uso:
  .venv/bin/python scripts/monitor_api.py [--intervalo 30] [--duracao 1800]
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOG = RAIZ / "logs" / "monitor_api.log"

INTERVALO = 30
DURACAO = 1800  # 30 min


def log(msg: str) -> None:
    linha = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(linha, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def n_processos_retraducao() -> int:
    r = subprocess.run(
        ["pgrep", "-f", "retraduzir_trechos.py"],
        capture_output=True, text=True,
    )
    return len([p for p in r.stdout.split() if p])


def medir_latencia_api() -> float | None:
    """Chama a API DeepSeek com um prompt minúsculo e mede o tempo (segundos)."""
    try:
        from openai import OpenAI
        from dotenv import load_dotenv
        load_dotenv(RAIZ / ".env")
        client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")
        inicio = time.time()
        client.chat.completions.create(
            model="deepseek-v4-flash",
            max_tokens=5,
            messages=[{"role": "user", "content": "diga: ok"}],
            temperature=0,
        )
        return round(time.time() - inicio, 1)
    except Exception as e:
        log(f"  ERRO na chamada de teste: {type(e).__name__}: {str(e)[:120]}")
        return None


def retries_recentes() -> int:
    """Conta 'resposta vazia' nos logs das massas (últimos 5 min)."""
    cmd = (
        "grep -h 'resposta vazia' logs/massa_*trechos.log logs/massa_mioshie_*.log "
        "logs/massa_gosuiji_1.log 2>/dev/null | tail -100 | wc -l"
    )
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=str(RAIZ))
    try:
        return int(r.stdout.strip())
    except Exception:
        return -1


def erros_api_recentes() -> int:
    """Conta erros de API (429/rate/timeout) nos logs recentes."""
    cmd = (
        "grep -hE '429|rate.limit|too many|Timeout|timeout|Connection' "
        "logs/massa_*trechos.log logs/massa_mioshie_*.log 2>/dev/null | tail -50 | wc -l"
    )
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=str(RAIZ))
    try:
        return int(r.stdout.strip())
    except Exception:
        return -1


def main() -> None:
    global INTERVALO, DURACAO
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a == "--intervalo" and i + 1 < len(args):
            INTERVALO = int(args[i + 1])
        if a == "--duracao" and i + 1 < len(args):
            DURACAO = int(args[i + 1])

    log(f"Monitor iniciado: intervalo={INTERVALO}s, duracao={DURACAO}s")
    fim = time.time() + DURACAO
    rodada = 0
    while time.time() < fim:
        rodada += 1
        n_proc = n_processos_retraducao()
        latencia = medir_latencia_api()
        retries = retries_recentes()
        erros = erros_api_recentes()
        lat = f"{latencia}s" if latencia is not None else "FALHA"
        log(
            f"[{rodada}] processos_retradução={n_proc} | "
            f"latência_API={lat} | retries(acumulado)={retries} | erros_API={erros}"
        )
        time.sleep(INTERVALO)

    log("Monitor concluído (30 min).")


if __name__ == "__main__":
    main()
