#!/usr/bin/env python3
"""Monitora a saúde da API DeepSeek durante a retradução.

Coleta a cada INTERVALO (30s) por DURACAO (30min):
- Erros recentes nos logs das massas (429/rate limit/retry "resposta vazia")
- Avanço dos trechos nos logs (para detectar estagnação/lentidão)
- Tempo dos últimos trechos concluídos (médio)

Loga em logs/api_health_monitor.log (formato linha, fácil de grep).

Uso:
  .venv/bin/python scripts/monitor_api_health.py
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOG = RAIZ / "logs" / "api_health_monitor.log"
INTERVALO = 30  # segundos
DURACAO = 30 * 60  # 30 minutos
INICIO = time.time()

LOGS_MASSAS = [
    "logs/massa_mioshie_5.log",
    "logs/massa_mioshie_7.log",
    "logs/massa_mioshie_6.log",
    "logs/massa_mioshie_trechos.log",
    "logs/massa_mioshie_t2.log",
    "logs/massa_gosuiji_trechos.log",
    "logs/massa_gosuiji_1.log",
    "logs/massa_gokowa_trechos.log",
    "logs/aud_colecoes.log",
]


def log(msg: str) -> None:
    linha = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(linha, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def coletar() -> dict:
    """Coleta métricas da saúde da API e das massas."""
    res = {
        "erros_recentes": 0,
        "retry_vazia": 0,
        "trechos_ultimos_5min": 0,
        "tempos_ultimos": [],
        "processos": 0,
    }
    agora = time.time()
    for lp in LOGS_MASSAS:
        p = RAIZ / lp
        if not p.exists():
            continue
        # últimos ~5 min do log (últimas 200 linhas são suficientes)
        linhas = p.read_text(encoding="utf-8", errors="ignore").splitlines()[-200:]
        for linha in linhas:
            # erros de API
            if re.search(r"429|rate.?limit|too many|insufficient|balance", linha, re.I):
                res["erros_recentes"] += 1
            # retry por resposta vazia / formato
            if re.search(r"retry.*vazia|resposta vazia|formato não reconhecido", linha, re.I):
                res["retry_vazia"] += 1
            # trecho concluído (-> Xs | N falas)
            m = re.search(r"->\s*([\d.]+)s\s*\|", linha)
            if m:
                res["trechos_ultimos_5min"] += 1
                res["tempos_ultimos"].append(float(m.group(1)))
    # processos de retradução ativos
    try:
        r = subprocess.run(["pgrep", "-f", "retraduzir_trechos.py"], capture_output=True, text=True)
        res["processos"] = len(r.stdout.strip().splitlines()) if r.stdout.strip() else 0
    except Exception:
        pass
    # média dos tempos
    if res["tempos_ultimos"]:
        res["tempo_medio_s"] = round(sum(res["tempos_ultimos"]) / len(res["tempos_ultimos"]), 1)
    else:
        res["tempo_medio_s"] = None
    return res


def main() -> None:
    log(f"Monitor de saúde da API iniciado | intervalo={INTERVALO}s | duração={DURACAO}s")
    amostras = 0
    while time.time() - INICIO < DURACAO:
        try:
            c = coletar()
            amostras += 1
            alerta = ""
            if c["erros_recentes"] > 0:
                alerta += " ⚠️ ERROS API"
            if c["retry_vazia"] > 8:
                alerta += " ⚠️ MUITOS RETRIES"
            if c["tempo_medio_s"] and c["tempo_medio_s"] > 400:
                alerta += " ⚠️ TREINOS LENTOS (>400s)"
            log(
                f"amostra={amostras} procs={c['processos']} "
                f"erros_api={c['erros_recentes']} retry_vazia={c['retry_vazia']} "
                f"trechos_5min={c['trechos_ultimos_5min']} "
                f"tempo_medio={c['tempo_medio_s']}s{alerta}"
            )
        except Exception as e:  # noqa: BLE001
            log(f"ERRO no monitor: {e}")
        time.sleep(INTERVALO)

    log("Monitor de 30 min concluído.")


if __name__ == "__main__":
    main()
