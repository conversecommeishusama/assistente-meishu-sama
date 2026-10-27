#!/usr/bin/env python3
"""Tira do cache os mp3 do XTTS local (a voz que o usuário rejeitou).

2026-10-28. O usuário ouviu o Gokōwa-roku nº 14 e reconheceu a voz "afeminada"
que já tinha descartado. A causa eram duas (§10.8 do handoff de autoria): o
áudio APROVADO era tapado pelo local, e o lote gravava com a amostra errada.
Com a chave Fish instalada, a voz aprovada passou a ser servida — mas os mp3 do
XTTS continuam em disco e continuariam a tapar o áudio aprovado em qualquer
trecho onde ele falte.

Este script MOVE (não apaga) os ficheiros para um directório de quarentena.
É reversível: `--restaurar` devolve tudo.

Uso:
    .venv/bin/python scripts/quarentenar_xtts.py --dry-run
    .venv/bin/python scripts/quarentenar_xtts.py
    .venv/bin/python scripts/quarentenar_xtts.py --restaurar
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time

RAIZ = "/var/www/goshinsho"
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, "scripts"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(RAIZ, ".env"))

from goshinsho.services import leitura_service, tts_service  # noqa: E402
from gerar_texto_worker_v2 import quebrar_como_front  # noqa: E402

# Chaves do XTTS local: a canónica e a histórica (sem versão). Ambas são a
# mesma voz e ambas têm de sair.
CHAVES_XTTS = (("xtts", tts_service.VOZ_MEISHU_CACHE), ("xtts", "meishu"))


def _alvos() -> dict[str, str]:
    """{caminho: "provedor:voz"} para todos os mp3 do XTTS no âmbito."""
    cache = tts_service._cache_dir()
    alvos: dict[str, str] = {}
    for obra in leitura_service.listar_obras():
        texto = leitura_service.obter_texto(obra["arquivo"])
        if not texto:
            continue
        for trecho in quebrar_como_front(texto):
            for prov, voz in CHAVES_XTTS:
                chave = tts_service._chave_cache(f"{prov}:{voz}", trecho, "+0%")
                caminho = os.path.join(cache, f"{chave}.mp3")
                if os.path.exists(caminho) and os.path.getsize(caminho) > 0:
                    alvos[caminho] = f"{prov}:{voz}"
    return alvos


def _dir_quarentena() -> str:
    marca = os.path.join(tts_service._cache_dir(), ".quarentena_xtts")
    if os.path.exists(marca):
        with open(marca, encoding="utf-8") as f:
            return f.read().strip()
    return ""


def quarentenar(seco: bool) -> int:
    alvos = _alvos()
    if not alvos:
        print("Nada a quarentenar: nenhum mp3 do XTTS no âmbito.")
        return 0

    total = sum(os.path.getsize(p) for p in alvos)
    print(f"mp3 do XTTS no âmbito: {len(alvos)} | {total / 1e9:.2f} GB")

    if seco:
        for p in list(alvos)[:5]:
            print(f"  {alvos[p]:20s} {os.path.getsize(p)/1e6:7.1f} MB  {os.path.basename(p)[:16]}…")
        print("  …")
        print("\n--dry-run: nada foi movido.")
        return 0

    destino = os.path.join(
        os.path.dirname(tts_service._cache_dir()),
        f"tts_cache_quarentena_xtts_{time.strftime('%Y%m%dT%H%M%S')}")
    os.makedirs(destino, exist_ok=True)

    movidos = 0
    falhas = 0
    for caminho, chave in alvos.items():
        try:
            shutil.move(caminho, os.path.join(destino, os.path.basename(caminho)))
            movidos += 1
        except OSError as e:
            falhas += 1
            print(f"  FALHOU {os.path.basename(caminho)}: {e}", file=sys.stderr)

    # O manifesto permite reverter e auditar.
    with open(os.path.join(destino, "MANIFESTO.json"), "w", encoding="utf-8") as f:
        json.dump({"criado": time.strftime("%Y-%m-%dT%H:%M:%S"),
                   "origem": tts_service._cache_dir(),
                   "ficheiros": [os.path.basename(p) for p in alvos]}, f,
                  ensure_ascii=False, indent=1)
    with open(os.path.join(tts_service._cache_dir(), ".quarentena_xtts"), "w",
              encoding="utf-8") as f:
        f.write(destino)

    print(f"\nMovidos {movidos} ficheiros ({falhas} falhas) para:\n  {destino}")
    print("Reverter: .venv/bin/python scripts/quarentenar_xtts.py --restaurar")
    return 0 if falhas == 0 else 1


def restaurar() -> int:
    origem = _dir_quarentena()
    if not origem or not os.path.isdir(origem):
        print("Nenhuma quarentena registada.")
        return 1
    destino = tts_service._cache_dir()
    n = 0
    for nome in os.listdir(origem):
        if nome in ("MANIFESTO.json",):
            continue
        caminho = os.path.join(origem, nome)
        if os.path.isfile(caminho):
            shutil.move(caminho, os.path.join(destino, nome))
            n += 1
    marca = os.path.join(destino, ".quarentena_xtts")
    if os.path.exists(marca):
        os.remove(marca)
    print(f"Restaurados {n} ficheiros de {origem}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--restaurar", action="store_true")
    args = ap.parse_args()
    if args.restaurar:
        return restaurar()
    return quarentenar(args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
