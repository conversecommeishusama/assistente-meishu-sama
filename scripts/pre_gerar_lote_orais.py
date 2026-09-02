#!/usr/bin/env python3
"""Pré-geração em lote da voz Meishu-Sama para os textos ORAIS da Leitura.

Processa Gokōwa, Gosuiji e Mioshie (e opcionalmente todos) com N workers em
paralelo, cada um gerando um texto por vez (subprocess do worker). Tem
checkpoint em disco (data/tts_geracao_estado.json) e pula o que já está no
cache — pode ser interrompido e retomado.

Uso:
    <venv_prod>/bin/python scripts/pre_gerar_lote_orais.py [--todos] [--workers N]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

RAIZ = "/var/www/goshinsho"
ARQUIVOS_DIR = os.path.join(RAIZ, "textos_leitura_colaborativa")
ESTADO_PATH = os.path.join(RAIZ, "data", "tts_geracao_estado.json")
PYTHON_PROD = os.path.join(RAIZ, "venv", "bin", "python")
WORKER = os.path.join(RAIZ, "scripts", "gerar_texto_meishu.py")

COLECOES_ORAIS = ["gokowa", "gosuiji", "mioshie"]


def _normalizar(s: str) -> str:
    """Remove acentos e lowercases (Gokōwa → gokowa)."""
    import unicodedata
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode().lower()


def listar_arquivos(todos: bool = False) -> list[str]:
    """Lista os textos ORAIS (mesmo critério do leitura_service: nome contém
    gokowa/gosuiji/mioshie, ignorando acentos). Se --todos, lista todos."""
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
    ap.add_argument("--todos", action="store_true", help="processar TODOS os textos (não só orais)")
    ap.add_argument("--workers", type=int, default=5, help="workers paralelos")
    args = ap.parse_args()

    arquivos = listar_arquivos(todos=args.todos)
    estado = carregar_estado()
    feitos = set(estado.get("feitos", []))
    fila = [f for f in arquivos if f not in feitos]
    print(f"Total: {len(arquivos)} | já feitos: {len(feitos)} | fila: {len(fila)}", flush=True)

    if not fila:
        print("Nada a fazer — todos já processados.", flush=True)
        return 0

    # Workers: cada um pega o próximo da fila (lock via arquivo de estado).
    workers = args.workers
    processos = {}
    idx = 0

    def lancar(arquivo):
        env = dict(os.environ)
        return subprocess.Popen(
            [PYTHON_PROD, WORKER, arquivo],
            env=env, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    try:
        while idx < len(fila) or processos:
            # Preenche slots livres
            while len(processos) < workers and idx < len(fila):
                arquivo = fila[idx]
                idx += 1
                p = lancar(arquivo)
                processos[p] = arquivo
                print(f"[{len(feitos)+idx}/{len(fila)}] iniciando: {arquivo}", flush=True)

            # Espera um terminar
            if processos:
                done, _ = subprocess.select if False else (None, None)
                # Poll
                terminados = []
                for p, arquivo in list(processos.items()):
                    rc = p.poll()
                    if rc is not None:
                        terminados.append((p, arquivo))
                if not terminados:
                    time.sleep(5)
                    continue
                for p, arquivo in terminados:
                    del processos[p]
                    feitos.add(arquivo)
                    estado["feitos"] = sorted(feitos)
                    salvar_estado(estado)
                    print(f"[{len(feitos)}/{len(fila)}] concluído: {arquivo} (rc={p.returncode})", flush=True)
    except KeyboardInterrupt:
        print("\nInterrompido — estado salvo. Reexecute para retomar.", flush=True)
        for p in processos:
            try:
                p.terminate()
            except Exception:
                pass
        return 130

    dec = time.time() - estado.get("inicio", time.time())
    print(f"\nLote concluído: {len(feitos)} textos em {dec/3600:.1f}h", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
