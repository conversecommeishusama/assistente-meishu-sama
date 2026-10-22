#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera o áudio de uma LISTA de trechos (JSON), sem tocar no resto do acervo.

Contexto (2026-10-22): ao publicar uma versão nova do corpus é preciso refazer
o áudio dos trechos que MUDARAM — e só desses. `scripts/sincronizar_audios.py`
sincroniza a obra inteira, o que num livro ainda por gerar significa milhares
de trechos e dias de CPU. Este script consome a lista produzida por
`scripts/relatorio_trechos_alterados.py --json` e gera exactamente esses.

Formato da lista (uma entrada por trecho):
    [{"arquivo": "Tijotengoku.txt", "ocorrencias": 1, "trecho": "…"}, …]

O trecho é gerado pelo caminho normal do app (`tts_service.sintetizar`), pelo
que a voz e a chave de cache são as mesmas que o serviço vai procurar.

Uso:
    .venv/bin/python scripts/gerar_trechos_lista.py /tmp/trechos_novos.json
    .venv/bin/python scripts/gerar_trechos_lista.py lista.json --dry-run

    # Muito mais rápido: mantém o modelo XTTS carregado num daemon
    .venv/bin/python scripts/gerar_trechos_lista.py lista.json --daemon

Por que o `--daemon` existe (2026-10-22): a via por subprocesso carrega o
modelo (~2 GB) a cada trecho e leva ~5 min por trecho — 84 trechos dariam 7
horas. O daemon carrega o modelo uma vez e processa a fila. Recebe
explicitamente a amostra de `tts_service._xtts_amostra()`: o default do
`daemon_xtts.py` é a amostra ANTIGA (v1), o que gravaria outra voz sob a
chave v2.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
os.environ.setdefault("GOSHINSHO_TTS_CACHE", str(RAIZ / "data" / "tts_cache"))

from goshinsho.services import tts_service  # noqa: E402

SPOOL = RAIZ / "data" / "tts_spool_lista"


def _destino_canonico(trecho: str) -> str:
    """Caminho de cache que o SERVIÇO vai procurar para este trecho.

    Usa `tts_service.provedor_canonico`: um trecho de interlocutor vai para o
    edge (narrador), não para o XTTS. Em 22/10 enfileirei tudo como XTTS e as
    falas de interlocutor saíram com a voz do Meishu e invisíveis para o app.
    """
    prov, voz = tts_service.provedor_canonico(trecho)
    ch = tts_service._chave_cache(f"{prov}:{voz}", trecho, "+0%")
    return os.path.join(tts_service._cache_dir(), f"{ch}.mp3")


def gerar_com_daemon(itens: list[dict], limite_min: int = 240) -> int:
    """Enfileira os trechos e deixa um único daemon XTTS processá-los."""
    pendentes = [x["trecho"] for x in itens
                 if not tts_service.caminho_em_cache(x["trecho"])]
    if not pendentes:
        print("nada a gerar: todos os trechos já têm áudio")
        return 0

    # Falas de interlocutor e metadados vão para o edge (rápido, ~1 s): não
    # podem entrar na fila do XTTS, que levaria minutos cada uma.
    edge = [t for t in pendentes
            if tts_service.provedor_canonico(t)[0] == "edge"]
    if edge:
        print(f"{len(edge)} trecho(s) pelo narrador (edge)", flush=True)
        for i, tr in enumerate(edge, 1):
            try:
                tts_service.sintetizar(tr, voz="meishu")
            except Exception as exc:
                print(f"  [{i}/{len(edge)}] FALHOU: {exc}", file=sys.stderr,
                      flush=True)
    pendentes = [t for t in pendentes
                 if tts_service.provedor_canonico(t)[0] != "edge"]
    if not pendentes:
        print("nada mais a gerar no XTTS")
        return 0

    spool = SPOOL
    (spool / "done").mkdir(parents=True, exist_ok=True)
    (spool / "erro").mkdir(parents=True, exist_ok=True)
    for velho in list(spool.glob("tarefa_*.json")):
        velho.unlink()
    print(f"{len(pendentes)} trecho(s) a enfileirar em {spool}", flush=True)

    destinos: dict[str, str] = {}
    for i, tr in enumerate(pendentes):
        destino = _destino_canonico(tr)
        if os.path.exists(destino) and os.path.getsize(destino) > 0:
            continue
        destinos[f"tarefa_{i:04d}"] = destino
        (spool / f"tarefa_{i:04d}.json").write_text(
            json.dumps({"texto": tts_service._preparar_texto_xtts(tr),
                        "destino": destino}, ensure_ascii=False),
            encoding="utf-8")
    if not destinos:
        print("nada a gerar: todos já resolvidos no enfileiramento")
        return 0

    amostra = tts_service._xtts_amostra()
    python = tts_service._xtts_python()
    print(f"daemon: {python}\namostra: {amostra}", flush=True)
    log = open("/tmp/daemon_lista.log", "w", encoding="utf-8")
    proc = subprocess.Popen(
        [python, str(RAIZ / "scripts" / "daemon_xtts.py"),
         "--spool", str(spool), "--amostra", amostra],
        stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        env={**os.environ, "XTTS_THREADS": os.environ.get("XTTS_THREADS", "6")})
    print(f"daemon pid={proc.pid}, log em /tmp/daemon_lista.log", flush=True)

    t0, total = time.time(), len(destinos)
    while True:
        feitos = sum(1 for d in destinos.values()
                     if os.path.exists(d) and os.path.getsize(d) > 0)
        erros = len(list((spool / "erro").glob("*.json")))
        decorrido = (time.time() - t0) / 60
        print(f"  {feitos}/{total} prontos | {erros} erro(s) | "
              f"{decorrido:.1f} min", flush=True)
        if feitos + erros >= total:
            break
        if decorrido > limite_min:
            print("limite de tempo atingido — o daemon continua em segundo plano",
                  flush=True)
            return 1
        time.sleep(30)

    proc.terminate()
    print(f"\nconcluído em {(time.time()-t0)/60:.1f} min "
          f"({feitos} ficheiros, {erros} erros)")
    return 0 if erros == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lista", help="JSON com os trechos a gerar")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limite", type=int, default=0, help="gerar só os N primeiros")
    ap.add_argument("--daemon", action="store_true",
                    help="usar o daemon persistente (muito mais rápido)")
    args = ap.parse_args()

    itens = json.loads(Path(args.lista).read_text(encoding="utf-8"))
    if args.limite:
        itens = itens[:args.limite]
    if args.daemon and not args.dry_run:
        return gerar_com_daemon(itens)

    print(f"{len(itens)} trecho(s) na lista", flush=True)

    gerados = reaproveitados = falhas = 0
    t0 = time.time()
    for i, item in enumerate(itens, 1):
        tr = item["trecho"]
        rotulo = f'[{i}/{len(itens)}] {item.get("arquivo", "?")[:34]}'
        # Já existe nalguma chave (histórica inclusive)? Não vale regerar.
        if tts_service.caminho_em_cache(tr):
            reaproveitados += 1
            continue
        if args.dry_run:
            print(f"{rotulo}: geraria  {tr[:70]!r}", flush=True)
            continue
        try:
            tts_service.sintetizar(tr, voz="meishu", rate="+0%")
            gerados += 1
        except Exception as exc:
            falhas += 1
            print(f"{rotulo}: FALHOU ({exc})  {tr[:60]!r}", file=sys.stderr,
                  flush=True)
            continue
        if gerados % 5 == 0:
            ritmo = (time.time() - t0) / gerados
            falta = (len(itens) - i) * ritmo
            print(f"{rotulo}: {gerados} gerados | {ritmo:.1f}s/trecho | "
                  f"falta ~{falta/60:.0f} min", flush=True)

    print(f"\ngerados={gerados} reaproveitados={reaproveitados} "
          f"falhas={falhas} em {time.time()-t0:.0f}s")
    return 0 if falhas == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
