#!/usr/bin/env python3
"""Watchdog automático: quando o gokowa concluir, lança 2ª instância do mioshie.

Motivação: a monitoração manual do chat NÃO é confiável (o gokowa pode concluir
e nada ser acionado). Este watchdog roda em tmux (independente do chat) e:

1. A cada intervalo, verifica se a massa do gokowa terminou (processo morto)
   E se o gokowa está 100% (todos os arquivos com checkpoint completo).
2. Quando isso acontecer, lança uma SEGUNDA instância do mioshie que processa
   APENAS os arquivos de mioshie ainda não concluídos (4,5,7,8 etc.), enquanto
   a instância original do mioshie continua nos arquivos atuais.
3. Garante que não há conflito: a 2ª instância só pega arquivos com checkpoint
   vazio/inexistente (nunca o arquivo que a 1ª está processando).

Uso:
  .venv/bin/python scripts/watchdog_mioshie2.py   (roda em loop, loga em logs/)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
TEXTOS = RAIZ / "textos_japones"
OUT = RAIZ / "reports" / "retraducao_colecoes"
LOG = RAIZ / "logs" / "watchdog_mioshie2.log"

sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))
from retraduzir_colecao import EXTRATORES  # noqa: E402

INTERVALO = 120  # segundos entre verificações
MIOSHIE2_SESSION = "massa_mioshie_t2"


def log(msg: str) -> None:
    linha = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(linha, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(linha + "\n")


def gokowa_concluido() -> bool:
    """True se TODOS os arquivos gokowa (1-19 + Suplemento) têm checkpoint completo."""
    for arq in sorted(TEXTOS.glob("*御光話録*.txt")):
        ckpt = OUT / f"{arq.stem}.json"
        try:
            falas = EXTRATORES["gokowa"](arq.read_text(encoding="utf-8"))
            if not falas:
                continue
            if not ckpt.exists():
                return False
            d = json.loads(ckpt.read_text(encoding="utf-8"))
            feitos = sum(1 for f in d.get("falas", {}).values() if f.get("pt_contextual"))
            if feitos < len(falas):
                return False
        except Exception as e:
            log(f"  AVISO ao checar gokowa {arq.name}: {e}")
            return False
    return True


def mioshie_restantes() -> list[Path]:
    """Arquivos de mioshie 1-8 AINDA NÃO INICIADOS (para a 2ª instância).

    Só pega arquivos com checkpoint inexistente ou com 0 falas feitas — para
    NÃO conflitar com a 1ª instância, que está processando os arquivos parciais
    (ex.: 3号 com 78%). A 2ª instância dedica-se aos que ainda não começaram.
    """
    import re
    restantes = []
    for arq in sorted(TEXTOS.glob("*御教え集*.txt")):
        m = re.search(r"御教え集(\d+)号", arq.name)
        if not m or int(m.group(1)) > 8:
            continue
        ckpt = OUT / f"{arq.stem}.json"
        # só pega arquivos que a 1ª instância AINDA NÃO começou (sem checkpoint) —
        # evita conflito com arquivos parciais em processamento
        if not ckpt.exists():
            restantes.append(arq)
    # ORDEM REVERSA (do último para o primeiro): a 1ª instância processa 1→8;
    # a 2ª processa 8→1. Elas se encontram no meio, NUNCA no mesmo arquivo.
    # Isso elimina o risco de corrida/edição simultânea (solução do usuário 17/08).
    restantes.reverse()
    return restantes


def sessao_tmux_existe(nome: str) -> bool:
    r = subprocess.run(["tmux", "has-session", "-t", nome], capture_output=True)
    return r.returncode == 0


def lancar_mioshie2(arquivos: list[Path]) -> None:
    """Lança a 2ª instância do mioshie processando só os arquivos restantes."""
    if not arquivos:
        log("Nenhum arquivo de mioshie restante — nada a fazer.")
        return
    if sessao_tmux_existe(MIOSHIE2_SESSION):
        log(f"Sessão {MIOSHIE2_SESSION} já existe — não relançando.")
        return

    # comando: processa cada arquivo restante com retraduzir_trechos.py
    cmds = []
    for arq in arquivos:
        cmds.append(f".venv/bin/python scripts/retraduzir_trechos.py mioshie {arq}")
    comando = " && ".join(cmds) + " && echo '[mioshie2 terminou]'"
    subprocess.run([
        "tmux", "new-session", "-d", "-s", MIOSHIE2_SESSION,
        f"cd {RAIZ} && {comando} > logs/massa_mioshie_t2.log 2>&1",
    ])
    log(f"Lançada 2ª instância do mioshie ({MIOSHIE2_SESSION}) com {len(arquivos)} arquivos restantes:")
    for a in arquivos:
        log(f"  - {a.name}")


def main() -> None:
    log("Watchdog mioshie2 iniciado. Aguardando o gokowa concluir...")
    lancado = False
    while True:
        try:
            if not lancado and gokowa_concluido():
                log("GOKOWA CONCLUÍDO (100%)! Verificando mioshie restantes...")
                restantes = mioshie_restantes()
                if restantes:
                    lancar_mioshie2(restantes)
                else:
                    log("Mioshie 1-8 também já está completo — nada a fazer.")
                lancado = True
            else:
                # log de status periódico (a cada ~30 min)
                if int(time.time()) % (30 * 60) < INTERVALO:
                    log("Aguardando gokowa (status: monitorando)...")
        except Exception as e:  # noqa: BLE001
            log(f"ERRO no watchdog: {e}")
        time.sleep(INTERVALO)


if __name__ == "__main__":
    main()
