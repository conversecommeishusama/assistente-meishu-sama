#!/usr/bin/env python3
"""Geração em MASSA da voz do Meishu-Sama (Fish Audio) para os 83 textos ORAIS.

Lê os textos da MESMA fonte do app (GOSHINSHO_TEXTOS_PT / textos_leitura_colaborativa),
segmenta como o FRONT (quebrarEmFrases do leitura_tts.js), e para cada trecho chama
tts_service.sintetizar(voz="meishu") — que decide o provedor:
  - Meishu-Sama / texto corrido  → Fish (voz aprovada)
  - Interlocutor                 → edge (Antônio)
  - metadado (título/data)       → edge (narrador)

Cada áudio é gravado no data/tts_cache com a chave canônica (mesma que o app procura),
então os áudios ficam imediatamente utilizáveis na Leitura.

Paralelismo + checkpoint (retoma de onde parou se interrompido).

Uso:
    /var/www/goshinsho/.venv/bin/python scripts/gerar_lote_fish.py [--workers 4]
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import random
import re
import sys
import time

RAIZ = "/var/www/goshinsho"
sys.path.insert(0, RAIZ)
os.environ.setdefault("GOSHINSHO_TTS_CACHE", os.path.join(RAIZ, "data/tts_cache"))
# Modo ESTRITO: sem fallback silencioso. Se o Fish falhar, o trecho é retentado
# e auditado — nunca sai com voz errada (bug do fallback, 2026-09-10).
os.environ.setdefault("GOSHINSHO_TTS_STRICT", "1")

from goshinsho.services import leitura_service, tts_service  # noqa: E402

CHECKPOINT = os.path.join(RAIZ, "data", "tts_fish_geracao_estado.json")
TENTATIVAS = 4  # tentativas por trecho (retry + backoff contra rate-limit)


def quebrar_como_front(texto: str) -> list[str]:
    """Replica fielmente o quebrarEmFrases do leitura_tts.js (v7)."""
    trechos = []
    paragrafos = [re.sub(r"\s+", " ", p).strip()
                  for p in re.split(r"\n+", texto or "") if p.strip()]
    for par in paragrafos:
        partes = [x for x in re.split(r"(?<=[.!?…])\s+", par) if x]
        if len(partes) <= 1:
            trechos.append(par)
        else:
            bloco = ""
            for parte in partes:
                if len(bloco) + len(parte) + 1 > 700 and bloco:
                    trechos.append(bloco.strip())
                    bloco = parte
                else:
                    bloco = (bloco + " " + parte).strip() if bloco else parte
            if bloco:
                trechos.append(bloco.strip())
    return trechos


def carregar_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT):
        try:
            with open(CHECKPOINT, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"concluidos": []}  # lista de (arquivo, indice_trecho)


def salvar_checkpoint(estado: dict) -> None:
    os.makedirs(os.path.dirname(CHECKPOINT), exist_ok=True)
    tmp = CHECKPOINT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(estado, f)
    os.replace(tmp, CHECKPOINT)


def gerar_trecho(args) -> tuple:
    """Gera UM trecho, com retry + backoff. Retorna (ok, arquivo, indice, detalhe).

    Em modo estrito (GOSHINSHO_TTS_STRICT=1) o tts_service NÃO faz fallback: se
    o Fish falhar, a exceção sobe e o trecho entra na fila de retry — assim o
    Meishu nunca sai com voz errada nem desaparece silenciosamente.

    O timeout é aplicado nas camadas de rede (Fish SDK / edge-tts) — ver
    goshinsho/services/tts_service.py. Assim, uma chamada presa não trava o lote.
    """
    arquivo, indice, trecho = args
    ultimo_erro = ""
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            caminho = tts_service.sintetizar(trecho, voz="meishu", rate="+0%")
            return (True, arquivo, indice, os.path.basename(caminho)[:16])
        except Exception as exc:
            ultimo_erro = str(exc)[:100]
            if tentativa < TENTATIVAS:
                # Backoff exponencial com jitter (rate-limit do provedor).
                time.sleep(min(2 ** tentativa, 20) + random.uniform(0, 1.5))
    return (False, arquivo, indice, ultimo_erro)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--so-orais", action="store_true", default=True,
                    help="Gera só os 83 orais (default).")
    args = ap.parse_args()

    # Obras orais (fonte do app).
    obras = [o for o in leitura_service.listar_obras() if o["tipo"] == "oral"]
    obras.sort(key=lambda o: (o.get("data") or "", o.get("titulo") or ""))
    print(f"=== Geração em massa (Fish) — {len(obras)} textos orais ===")
    print(f"Fonte: {leitura_service.TEXTOS_DIR}")
    print(f"Workers: {args.workers} | Cache: {tts_service._cache_dir()}\n")

    estado = carregar_checkpoint()
    concluidos = set(tuple(x) for x in estado.get("concluidos", []))

    # Monta a fila de tarefas: (arquivo, indice, trecho) para cada trecho não concluído.
    tarefas = []
    totais_por_arquivo = {}
    for obra in obras:
        arquivo = obra["arquivo"]
        texto = leitura_service.obter_texto(arquivo)
        if not texto:
            continue
        trechos = quebrar_como_front(texto)
        totais_por_arquivo[arquivo] = len(trechos)
        for i, tr in enumerate(trechos):
            if (arquivo, i) not in concluidos:
                tarefas.append((arquivo, i, tr))

    total_pendente = len(tarefas)
    print(f"Total de trechos a gerar: {total_pendente}")
    if total_pendente == 0:
        print("Nada pendente — tudo já gerado.")
        return 0

    t0 = time.time()
    ok = 0
    erros = 0
    ultimo_log = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        # Itera em lotes para ir salvando checkpoint e logando progresso.
        futures = {ex.submit(gerar_trecho, t): t for t in tarefas}
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            res = fut.result()
            arquivo, indice = res[1], res[2]
            if res[0]:
                ok += 1
                concluidos.add((arquivo, indice))  # só SUCESSO entra no checkpoint
            else:
                erros += 1
                print(f"  ERRO [{arquivo} #{indice}]: {res[3]}", flush=True)
                # NÃO marca como concluído → será retentado numa próxima execução.

            # Loga progresso a cada ~30s ou a cada 100.
            agora = time.time()
            if i % 100 == 0 or agora - ultimo_log > 30:
                decorrido = agora - t0
                ritmo = i / decorrido * 60 if decorrido > 0 else 0
                restante_min = (total_pendente - i) / ritmo if ritmo > 0 else 0
                print(f"  [{i}/{total_pendente}] ok={ok} err={erros} "
                      f"({ritmo:.0f}/min, restante ~{restante_min/60:.1f}h)", flush=True)
                estado["concluidos"] = [list(c) for c in concluidos]
                salvar_checkpoint(estado)
                ultimo_log = agora

    # Checkpoint final.
    estado["concluidos"] = [list(c) for c in concluidos]
    estado["resumo"] = {"ok": ok, "erros": erros, "total": total_pendente}
    salvar_checkpoint(estado)

    decorrido = (time.time() - t0) / 60
    print(f"\n=== Concluído em {decorrido:.1f} min ===")
    print(f"OK: {ok} | Erros: {erros} | Total processado: {ok + erros}")
    print(f"Checkpoint: {CHECKPOINT}")
    if erros:
        print("AVISO: há erros — rode de novo p/ tentar os que falharam (checkpoint retoma).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
