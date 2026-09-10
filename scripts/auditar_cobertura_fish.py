#!/usr/bin/env python3
"""Audita a COBERTURA REAL dos áudios da Leitura (voz Fish + narrador edge).

Compara, para cada trecho dos textos ORAIS, a chave de cache ESPERADA (conforme
o roteamento ATUAL do tts_service) com os arquivos existentes em data/tts_cache.
É a fonte de verdade — o log do gerador pode mentir por causa do fallback.

Motivação (2026-09-10): o gerador em lote contava como "ok" trechos em que o
Fish falhou e o tts_service caiu para XTTS/edge (fallback silencioso). O log
dizia 48 erros, mas 427 trechos estavam sem o áudio correto.

Uso:
    /var/www/goshinsho/.venv/bin/python scripts/auditar_cobertura_fish.py
    # saída: relatório no stdout; --json grava/atualiza a lista de pendentes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

RAIZ = "/var/www/goshinsho"
sys.path.insert(0, RAIZ)
os.environ.setdefault("GOSHINSHO_TTS_CACHE", os.path.join(RAIZ, "data/tts_cache"))

from goshinsho.services import leitura_service, tts_service  # noqa: E402

import importlib.util  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "glf", os.path.join(RAIZ, "scripts/gerar_lote_fish.py"))
glf = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(glf)


def chave_esperada(trecho: str) -> tuple[str, str]:
    """Retorna (tipo, chave_cache) conforme o roteamento atual do tts_service."""
    falante = tts_service._identificar_falante(trecho)
    if falante == "outro":
        return "edge", tts_service._chave_cache("edge:pt-BR-AntonioNeural", trecho, "+0%")
    if falante == "" and tts_service._eh_metadado(trecho):
        return "edge", tts_service._chave_cache("edge:pt-BR-AntonioNeural", trecho, "+0%")
    return "fish", tts_service._chave_cache(
        f"fish:{tts_service.FISH_MEISHU_CACHE}", trecho, "+0%")


def auditar() -> dict:
    cache = tts_service._cache_dir()

    def existe(ch: str) -> bool:
        return os.path.exists(os.path.join(cache, ch + ".mp3"))

    obras = [o for o in leitura_service.listar_obras() if o["tipo"] == "oral"]
    resumo = {"fish_ok": 0, "fish_falta": 0, "edge_ok": 0, "edge_falta": 0}
    pendentes: list[list] = []
    detalhe_falta: list[tuple] = []
    nao_narraveis = 0

    for o in obras:
        arquivo = o["arquivo"]
        texto = leitura_service.obter_texto(arquivo)
        if not texto:
            continue
        for i, tr in enumerate(glf.quebrar_como_front(texto)):
            # Trechos só de pontuação/símbolos não têm o que narrar — o
            # edge-tts recusa (NoAudioReceived). Não são pendência de áudio.
            if tts_service._sem_conteudo_narravel(tr):
                nao_narraveis += 1
                continue
            tipo, ch = chave_esperada(tr)
            if existe(ch):
                resumo[f"{tipo}_ok"] += 1
            else:
                resumo[f"{tipo}_falta"] += 1
                pendentes.append([arquivo, i])
                detalhe_falta.append((arquivo, i, tipo, len(tr), tr[:70]))

    resumo["nao_narraveis"] = nao_narraveis
    resumo["total_falta"] = resumo["fish_falta"] + resumo["edge_falta"]
    resumo["total_trechos"] = (resumo["fish_ok"] + resumo["edge_ok"]
                               + resumo["total_falta"])
    narraveis = resumo["total_trechos"] - nao_narraveis
    resumo["narraveis"] = narraveis
    resumo["cobertura_pct"] = (round(100 * (narraveis - resumo["total_falta"])
                                     / narraveis, 3) if narraveis else 100.0)
    return {"resumo": resumo, "pendentes": pendentes, "detalhe": detalhe_falta}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", metavar="ARQ",
                    help="Grava a lista de pendentes (formato do checkpoint).")
    ap.add_argument("--detalhe", action="store_true", help="Mostra exemplos dos faltantes.")
    ap.add_argument("--limite-detalhe", type=int, default=15)
    args = ap.parse_args()

    r = auditar()
    s = r["resumo"]
    print("=== COBERTURA DOS ÁUDIOS (orais) ===")
    print(f"Trechos totais ....: {s['total_trechos']}")
    print(f"  não narráveis ...: {s['nao_narraveis']} (só pontuação — pulados)")
    print(f"  narráveis .......: {s['narraveis']}")
    print(f"  Fish (Meishu) ...: {s['fish_ok']} ok | {s['fish_falta']} FALTANDO")
    print(f"  Edge (narrador) .: {s['edge_ok']} ok | {s['edge_falta']} FALTANDO")
    print(f"Cobertura .........: {s['cobertura_pct']}%")

    if args.detalhe and r["detalhe"]:
        print(f"\n--- exemplos de faltantes (até {args.limite_detalhe}) ---")
        for arq, i, tipo, tam, tx in r["detalhe"][:args.limite_detalhe]:
            print(f"  [{tipo}] {arq} #{i} ({tam}c) {tx!r}")

    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump({"concluidos_pendentes": r["pendentes"]}, f)
        print(f"\nPendentes gravados em {args.json} ({len(r['pendentes'])}).")

    return 0 if s["total_falta"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
