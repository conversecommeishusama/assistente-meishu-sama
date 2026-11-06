#!/usr/bin/env python3
"""Monitor da saúde da API DeepSeek + progresso da retradução.

Roda em loop a cada 30s por 30 minutos, registrando:
- Latência média das chamadas à API (via timeout de uma chamada de teste)
- Nº de processos de retradução ativos
- Nº de retries ("resposta vazia"/"formato") nos logs das massas
- Nº de erros de API nos logs
- Progresso por volume (chars concluídos) das 3 coleções

Log em logs/monitor_api.log. Roda em tmux (independe do chat).

Uso:
  .venv/bin/python scripts/monitorar_saude_api.py
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
LOG_PATH = RAIZ / "logs" / "monitor_api.log"
DURACAO_MIN = 30          # 30 minutos
INTERVALO = 30            # a cada 30s
FIM = time.time() + DURACAO_MIN * 60

RETR = RAIZ / "reports" / "retraducao_colecoes"
LOGS = RAIZ / "logs"

sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))


def log(msg: str) -> None:
    linha = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(linha, flush=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def n_processos_retrad() -> int:
    r = subprocess.run(["pgrep", "-f", "retraduzir_trechos.py"], capture_output=True)
    return len(r.stdout.split()) if r.stdout else 0


def n_retries_logs() -> int:
    total = 0
    for pat in ["massa_*trechos.log", "massa_mioshie_*.log", "massa_gosuiji_1.log"]:
        for p in LOGS.glob(pat):
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
                total += len(re.findall(r"\[retry \d+\]|resposta vazia|formato não reconhecido", txt))
            except Exception:
                pass
    return total


def n_erros_api_logs() -> int:
    total = 0
    for pat in ["massa_*trechos.log", "massa_mioshie_*.log"]:
        for p in LOGS.glob(pat):
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
                total += len(re.findall(r"429|rate.limit|TimeoutError|APIError|insufficient", txt))
            except Exception:
                pass
    return total


def latencia_api() -> float | None:
    """Mede a latência da API com uma chamada mínima (timeout 10s)."""
    from openai import OpenAI
    from dotenv import load_dotenv
    load_dotenv(RAIZ / ".env")
    try:
        client = OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com/v1")
        inicio = time.time()
        client.chat.completions.create(
            model="deepseek-v4-flash",
            max_tokens=10,
            messages=[{"role": "user", "content": "diga ok"}],
            timeout=10,
        )
        return round(time.time() - inicio, 2)
    except Exception as e:
        return None


def progresso() -> str:
    """Progresso por volume das 3 coleções (chars concluídos)."""
    try:
        from retraduzir_colecao import EXTRATORES
        total_fc = total_tc = 0
        partes = []
        for col, pat, ext in [("gokowa", "*御光話録*.txt", "gokowa"),
                              ("gosuiji", "*御垂示録*.txt", "gosuiji"),
                              ("mioshie", "*御教え集*.txt", "mioshie")]:
            tc = fc = 0
            for arq in RAIZ.glob(f"textos_japones/{pat}"):
                nome = arq.name
                if col == "mioshie":
                    m = re.search(r"御教え集(\d+)号", nome)
                    if not m or int(m.group(1)) > 8:
                        continue
                try:
                    falas = EXTRATORES[ext](arq.read_text(encoding="utf-8"))
                except Exception:
                    continue
                chars = sum(len(f[1]) for f in falas)
                tc += chars
                ckpt = RETR / f"{arq.stem}.json"
                feitos = 0
                if ckpt.exists():
                    try:
                        d = json.loads(ckpt.read_text(encoding="utf-8"))
                        feitos = sum(1 for f in d.get("falas", {}).values() if f.get("pt_contextual"))
                    except Exception:
                        pass
                if feitos >= len(falas) and len(falas) > 0:
                    fc += chars
            partes.append(f"{col}={100*fc/max(tc,1):.0f}%")
            total_fc += fc
            total_tc += tc
        partes.append(f"TOTAL={100*total_fc/max(total_tc,1):.0f}%")
        return " | ".join(partes)
    except Exception as e:
        return f"progresso: erro {e}"


def main() -> None:
    log(f"=== Monitor de saúde da API iniciado (duração {DURACAO_MIN}min, intervalo {INTERVALO}s) ===")
    while time.time() < FIM:
        try:
            n_proc = n_processos_retrad()
            n_retries = n_retries_logs()
            n_erros = n_erros_api_logs()
            lat = latencia_api()
            prog = progresso()
            lat_txt = f"{lat}s" if lat is not None else "TIMEOUT/FALHA"
            log(f"proc={n_proc} | lat={lat_txt} | retries={n_retries} | erros_api={n_erros} | {prog}")
        except Exception as e:  # noqa: BLE001
            log(f"ERRO no monitor: {e}")
        time.sleep(INTERVALO)
    log("=== Monitor concluído (30min) ===")


if __name__ == "__main__":
    main()
