#!/usr/bin/env python3
"""Pré-geração em lote (v2) da voz Meishu-Sama para os textos ORAIS.

Arquitetura otimizada (modelo XTTS persistente):
- Sobe N daemons XTTS (subprocessos do venv_xtts), cada um com spool dedicado
  (data/tts_spool/dN). Cada daemon carrega o modelo UMA vez e fica residente.
- Sobe M workers (subprocessos do venv prod), cada um ligado a um spool.
  Cada worker processa um texto por vez: trechos Interlocutor -> edge direto,
  trechos Meishu/corrido -> envia ao seu daemon (sem recarregar o modelo).
  M pode ser maior que N: o daemon tira as tarefas do spool uma a uma, por isso
  vários workers no mesmo spool não se estorvam — e assim uma obra que só
  precisa de narrador (edge) não deixa um daemon parado.
- Checkpoint em data/tts_geracao_estado.json (retoma de onde parou).
- O cache (data/tts_cache) evita regenerar o que já existe.

Uso:
    <venv_prod>/bin/python scripts/pre_gerar_lote_orais.py [--workers N]
        [--daemons N] [--todos]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

RAIZ = "/var/www/goshinsho"
ARQUIVOS_DIR = os.path.join(RAIZ, "textos_leitura_colaborativa")
ESTADO_PATH = os.path.join(RAIZ, "data", "tts_geracao_estado.json")
PYTHON_PROD = os.path.join(RAIZ, "venv", "bin", "python")
PYTHON_XTTS = os.path.join(RAIZ, "venv_xtts", "bin", "python")
DAEMON = os.path.join(RAIZ, "scripts", "daemon_xtts.py")
WORKER = os.path.join(RAIZ, "scripts", "gerar_texto_worker_v2.py")
SPOOL_BASE = os.path.join(RAIZ, "data", "tts_spool")

COLECOES_ORAIS = ["gokowa", "gosuiji", "mioshie"]


def _normalizar(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()


def listar_arquivos(todos: bool = False, lista: str | None = None) -> list[str]:
    if lista:
        # Lista explícita: um nome de obra por linha. Permite limitar o lote ao
        # âmbito aprovado (ex.: só escritos do Meishu, sem material
        # institucional) sem duplicar aqui a política de autoria.
        with open(lista, encoding="utf-8") as f:
            nomes = [l.strip() for l in f if l.strip()]
        return nomes
    nomes = [f for f in os.listdir(ARQUIVOS_DIR) if f.endswith(".txt") and ".bak" not in f]
    if not todos:
        nomes = [f for f in nomes if any(c in _normalizar(f) for c in COLECOES_ORAIS)]
    nomes.sort()
    return nomes


def carregar_estado() -> dict:
    if os.path.exists(ESTADO_PATH):
        try:
            return json.load(open(ESTADO_PATH))
        except Exception:
            pass
    return {"feitos": [], "inicio": time.time()}


def salvar_estado(estado: dict) -> None:
    os.makedirs(os.path.dirname(ESTADO_PATH), exist_ok=True)
    tmp = ESTADO_PATH + ".tmp"
    json.dump(estado, open(tmp, "w"), ensure_ascii=False, indent=1)
    os.replace(tmp, ESTADO_PATH)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=5,
                    help="Obras processadas em paralelo (uma por worker).")
    ap.add_argument("--daemons", type=int, default=None,
                    help="Daemons XTTS residentes. Por omissão igual a "
                         "--workers. Um daemon processa as tarefas do seu "
                         "spool UMA a uma, por isso ter mais workers do que "
                         "daemons é seguro e evita daemon ocioso enquanto uma "
                         "obra só precisa de narrador (edge).")
    ap.add_argument("--todos", action="store_true")
    ap.add_argument(
        "--lista",
        help="Ficheiro com a lista de obras (uma por linha). Ignora o "
             "checkpoint `feitos`: o cache por trecho é a fonte de verdade, "
             "por isso obras já tocadas mas com trechos novos são reprocessadas.",
    )
    args = ap.parse_args()
    n = args.workers
    n_daemons = args.daemons or n

    arquivos = listar_arquivos(todos=args.todos, lista=args.lista)
    estado = carregar_estado()
    feitos = set(estado.get("feitos", []))
    fila = arquivos if args.lista else [f for f in arquivos if f not in feitos]
    print(f"Total: {len(arquivos)} | feitos: {len(feitos)} | fila: {len(fila)}", flush=True)
    if not fila:
        print("Nada a fazer.", flush=True)
        return 0

    # Limpa spools antigos.
    os.makedirs(SPOOL_BASE, exist_ok=True)
    for f in os.listdir(SPOOL_BASE):
        p = os.path.join(SPOOL_BASE, f)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
        elif f.startswith("tarefa_"):
            try:
                os.remove(p)
            except OSError:
                pass

    # Sobe N daemons XTTS (modelo residente, spool dedicado cada).
    daemons = []  # (processo, spool_dir)
    for i in range(n_daemons):
        spool = os.path.join(SPOOL_BASE, f"d{i}")
        os.makedirs(spool, exist_ok=True)
        p = subprocess.Popen(
            [PYTHON_XTTS, DAEMON, "--spool", spool],
            env=dict(os.environ),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        daemons.append((p, spool))
        print(f"daemon XTTS [{i}] iniciado", flush=True)

    print("Aguardando daemons carregarem o modelo (~75s)...", flush=True)
    time.sleep(75)

    # Sobe N workers, cada um ligado a um spool de daemon (env).
    procs = {}  # processo -> (arquivo, daemon_idx)
    idx = 0
    ultimo_progresso = time.time()
    # Progresso honesto: o numerador é "obras já despachadas" e o denominador
    # é o total da lista. Antes o denominador era `len(fila)` mas o numerador
    # somava `feitos` (checkpoint antigo), o que produzia "[84/15]" num lote
    # de 15 obras.
    total_obras = len(arquivos)
    concluidas = total_obras - len(fila)

    def lancar(arquivo, daemon_idx):
        env = dict(os.environ)
        env["XTTS_SPOOL"] = daemons[daemon_idx][1]
        env["XTTS_DAEMON_IDX"] = str(daemon_idx)
        return subprocess.Popen(
            [PYTHON_PROD, WORKER, arquivo],
            env=env,
            # 2026-10-27: antes era DEVNULL e o worker perdia tudo o que tinha
            # para dizer — «timeout XTTS trecho N», «FIM: N edge + M xtts»,
            # excepções do edge. Herdar os descritores do pai leva isso para o
            # mesmo log do serviço (StandardOutput/StandardError da unidade).
            stdout=None, stderr=None,
        )

    try:
        while idx < len(fila) or procs:
            while len(procs) < n and idx < len(fila):
                arquivo = fila[idx]
                # Rodízio simples entre os spools dos daemons. Vários workers
                # podem partilhar o mesmo spool sem conflito: o daemon tira as
                # tarefas uma a uma e cada worker espera pelo SEU mp3 (a chave
                # é o sha256 do texto). Era `len(procs) % n`, que com slots
                # exclusivos colidia quando os workers terminavam fora de ordem
                # (dois no mesmo spool, um daemon ocioso) — 2026-10-27.
                daemon_idx = idx % n_daemons
                p = lancar(arquivo, daemon_idx)
                procs[p] = (arquivo, daemon_idx)
                idx += 1
                print(f"[{concluidas + idx}/{total_obras}] {arquivo} "
                      f"(daemon {daemon_idx})", flush=True)

            terminados = [pp for pp in procs if pp.poll() is not None]
            if not terminados:
                # Batimento: sem isto um worker pendurado (edge-tts sem
                # timeout, 27/10/2026) deixava o log mudo durante horas e
                # parecia que o lote estava bem.
                decorrido = time.time() - ultimo_progresso
                if decorrido >= 300:
                    ultimo_progresso = time.time()
                    print(
                        f"... {len(procs)} worker(s) activo(s) | "
                        f"{decorrido / 60:.0f} min sem concluir obra | "
                        f"{idx}/{len(fila)} despachadas | "
                        f"{concluidas}/{total_obras} concluídas",
                        flush=True,
                    )
                time.sleep(10)
                continue
            for p in terminados:
                arquivo, _daemon_idx = procs.pop(p)
                ultimo_progresso = time.time()
                feitos.add(arquivo)
                estado["feitos"] = sorted(feitos)
                salvar_estado(estado)
                concluidas += 1
                print(f"[{concluidas}/{total_obras}] concluído: {arquivo} "
                      f"(rc={p.returncode})", flush=True)
    except KeyboardInterrupt:
        print("\nInterrompido. Estado salvo — reexecute para retomar.", flush=True)
        for p in list(procs):
            try:
                p.terminate()
            except Exception:
                pass
    finally:
        for p, _spool in daemons:
            try:
                p.terminate()
            except Exception:
                pass
        print("Daemons encerrados.", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
