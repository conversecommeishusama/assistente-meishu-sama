#!/usr/bin/env python3
"""Sincroniza a biblioteca de áudios com os textos ATUAIS da Leitura.

Por que existe (2026-09-10):
    O gerador em lote usava um checkpoint por (arquivo, ÍNDICE do trecho).
    Quando alguém edita o texto, os índices deslizam: o gerador acha que já
    fez e PULA trechos, deixando-os mudos para sempre. Já causou 25 trechos
    órfãos nos orais. Além disso, o log dizia "ok" enquanto o áudio não
    existia (fallback silencioso).

    Este script resolve os dois: compara o CONTEÚDO (chave de cache, que é o
    sha256 do texto cru) com o cache real. É IDEMPOTENTE e à prova de edição:
    - trecho novo/alterado  → gera
    - trecho inalterado     → pula (nada a fazer)
    - trecho removido       → (opcional) reporta áudio órfão

Uso:
    # Ver o que está desatualizado (NÃO gera nada):
    .venv/bin/python scripts/sincronizar_audios.py --dry-run

    # Sincronizar (gera só o que falta/mudou):
    .venv/bin/python scripts/sincronizar_audios.py

    # Só os orais / só os escritos do Meishu:
    .venv/bin/python scripts/sincronizar_audios.py --tipo oral
    .venv/bin/python scripts/sincronizar_audios.py --tipo escrita

    # Um texto específico (ex.: após revisar um livro):
    .venv/bin/python scripts/sincronizar_audios.py --arquivo "19480905 - Conversas sobre a Fé.txt"

    # Modo automático (para cron/systemd timer): só age se houver mudanças.
    .venv/bin/python scripts/sincronizar_audios.py --auto

Saída: relatório legível + código de saída 0 (ok) ou 1 (ficou pendência).
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import random
import sys
import time

RAIZ = "/var/www/goshinsho"
sys.path.insert(0, RAIZ)
os.environ.setdefault("GOSHINSHO_TTS_CACHE", os.path.join(RAIZ, "data/tts_cache"))
# Sem fallback silencioso: se o Fish falhar, a exceção sobe e o trecho é
# retentado/auditado (senão o áudio sai com voz errada e o log diz "ok").
os.environ.setdefault("GOSHINSHO_TTS_STRICT", "1")

from goshinsho.services import leitura_service, tts_service  # noqa: E402

ESTADO = os.path.join(RAIZ, "data", "tts_sincronizacao_estado.json")
TENTATIVAS = 4
VOZ = "meishu"

# Coleções/obras que NÃO são escritos do Meishu-Sama (decisão do usuário):
# material institucional e revistas. Excluídas de --tipo escrita por padrão.
NAO_MEISHU = (
    "Manual da Igreja", "Guia Rápido", "Relatos de Milagres",
    "Doutrina da Igreja", "HAKONE ART MUSEUM", "A Story of Ukiyo-e",
    "Jornais", "Revista_Asahi",
    # revistas institucionais
    "Eiko", "Hikari", "Tijotengoku", "Kyusei", "Ensinamentos_diversos",
    "Esboco_da_Medicina",
)


def _spec_glf():
    """Importa o quebrar_como_front do gerador (segmentação idêntica ao front)."""
    import importlib.util
    p = os.path.join(RAIZ, "scripts/gerar_lote_fish.py")
    s = importlib.util.spec_from_file_location("glf", p)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


glf = _spec_glf()


def filtrar_obras(tipo: str, arquivo: str | None, incluir_institucional: bool):
    """Seleciona as obras conforme o filtro pedido."""
    obras = leitura_service.listar_obras()
    if arquivo:
        return [o for o in obras if o["arquivo"] == arquivo]
    if tipo == "oral":
        return [o for o in obras if o["tipo"] == "oral"]
    if tipo == "escrita":
        sel = [o for o in obras if o["tipo"] != "oral"]
        if not incluir_institucional:
            sel = [o for o in sel
                   if not any(n.lower() in (o["titulo"] or "").lower()
                              for n in NAO_MEISHU)]
        return sel
    return obras  # tudo


def diagnostico(obras) -> dict:
    """Compara texto atual × cache. NÃO gera nada."""
    cache = tts_service._cache_dir()

    def existe(ch: str) -> bool:
        return os.path.exists(os.path.join(cache, ch + ".mp3"))

    pendentes: list[tuple] = []
    por_arquivo: dict[str, dict] = {}
    total = ok = 0
    nao_narraveis = 0

    for o in obras:
        arq = o["arquivo"]
        texto = leitura_service.obter_texto(arq)
        if not texto:
            continue
        trechos = glf.quebrar_como_front(texto)
        info = {"titulo": o.get("titulo") or arq, "tipo": o["tipo"],
                "trechos": len(trechos), "faltando": 0, "nao_narraveis": 0}
        for i, tr in enumerate(trechos):
            total += 1
            # Trechos só de pontuação/símbolos (separadores "───", "| | |") não
            # têm o que narrar: o edge-tts recusa (NoAudioReceived) e falhariam
            # para sempre. Contam como "não narráveis", não como pendência.
            if tts_service._sem_conteudo_narravel(tr):
                nao_narraveis += 1
                info["nao_narraveis"] += 1
                continue
            fl = tts_service._identificar_falante(tr)
            if fl == "outro" or (fl == "" and tts_service._eh_metadado(tr)):
                ch = tts_service._chave_cache("edge:pt-BR-AntonioNeural", tr, "+0%")
            else:
                ch = tts_service._chave_cache(
                    f"fish:{tts_service.FISH_MEISHU_CACHE}", tr, "+0%")
            if existe(ch):
                ok += 1
            else:
                info["faltando"] += 1
                pendentes.append((arq, i, tr))
        por_arquivo[arq] = info

    # A cobertura considera só o que É narrável (senão nunca chega a 100%).
    narraveis = total - nao_narraveis
    return {
        "total": total,
        "narraveis": narraveis,
        "nao_narraveis": nao_narraveis,
        "ok": ok,
        "pendentes": pendentes,
        "por_arquivo": por_arquivo,
        "cobertura": round(100 * ok / narraveis, 3) if narraveis else 100.0,
    }


def gerar_trecho(args) -> tuple:
    """Gera UM trecho com retry + backoff. Retorna (ok, arquivo, indice, detalhe)."""
    arquivo, indice, trecho = args
    ultimo = ""
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            caminho = tts_service.sintetizar(trecho, voz=VOZ, rate="+0%")
            return (True, arquivo, indice, os.path.basename(caminho)[:16])
        except Exception as exc:
            ultimo = f"{type(exc).__name__}: {str(exc)[:100]}"
            if tentativa < TENTATIVAS:
                time.sleep(min(2 ** tentativa, 20) + random.uniform(0, 1.5))
    return (False, arquivo, indice, ultimo)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Sincroniza a biblioteca de áudios com os textos atuais.")
    ap.add_argument("--tipo", choices=["oral", "escrita", "todos"], default="todos")
    ap.add_argument("--arquivo", help="Sincroniza apenas este arquivo.")
    ap.add_argument("--incluir-institucional", action="store_true",
                    help="Inclui Manual/Guia/revistas (não são escritos do Meishu).")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--dry-run", action="store_true",
                    help="Só mostra o que está desatualizado (não gera).")
    ap.add_argument("--auto", action="store_true",
                    help="Modo silencioso p/ cron: só age se houver pendência.")
    ap.add_argument("--limite", type=int, default=0,
                    help="Gera no máximo N trechos (0 = sem limite).")
    args = ap.parse_args()

    obras = filtrar_obras(args.tipo, args.arquivo, args.incluir_institucional)
    if not obras:
        print("Nenhuma obra corresponde ao filtro.")
        return 1

    print(f"=== Sincronização de áudios — {len(obras)} obra(s) ===")
    print(f"Filtro: tipo={args.tipo}"
          + (f" | arquivo={args.arquivo}" if args.arquivo else "")
          + (" | + institucional" if args.incluir_institucional else ""))
    print(f"Cache: {tts_service._cache_dir()}\n")

    d = diagnostico(obras)
    print(f"Trechos no texto ......: {d['total']:,}")
    print(f"  não narráveis .......: {d['nao_narraveis']:,} "
          f"(só pontuação/símbolos — pulados)")
    print(f"  narráveis ...........: {d['narraveis']:,}")
    print(f"Já com áudio correto ..: {d['ok']:,}")
    print(f"Desatualizados ........: {len(d['pendentes']):,}")
    print(f"Cobertura .............: {d['cobertura']}%")

    # Detalhe por obra (só as que têm pendência).
    com_pend = [(a, i) for a, i in d["por_arquivo"].items() if i["faltando"]]
    if com_pend:
        print(f"\n--- Obras com pendência ({len(com_pend)}) ---")
        for arq, info in sorted(com_pend, key=lambda x: -x[1]["faltando"])[:25]:
            print(f"  {info['faltando']:6,}/{info['trechos']:6,}  "
                  f"{info['titulo'][:56]}")

    if not d["pendentes"]:
        print("\nTudo sincronizado — nada a fazer.")
        if not args.auto:
            print("(Use --dry-run para auditar sem gerar.)")
        return 0

    if args.dry_run:
        print(f"\n[dry-run] {len(d['pendentes']):,} trechos seriam gerados. "
              f"Nada foi alterado.")
        return 1

    tarefas = d["pendentes"]
    if args.limite:
        tarefas = tarefas[:args.limite]

    print(f"\nGerando {len(tarefas):,} trechos (workers={args.workers})...")
    t0 = time.time()
    ok = erros = 0
    falhas: list[tuple] = []
    ultimo_log = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        futuros = {ex.submit(gerar_trecho, t): t for t in tarefas}
        for i, fut in enumerate(concurrent.futures.as_completed(futuros), 1):
            res = fut.result()
            if res[0]:
                ok += 1
            else:
                erros += 1
                falhas.append((res[1], res[2], res[3]))
                print(f"  ERRO [{res[1]} #{res[2]}]: {res[3]}", flush=True)
            agora = time.time()
            if i % 100 == 0 or agora - ultimo_log > 30:
                dt = agora - t0
                ritmo = i / dt * 60 if dt > 0 else 0
                resta = (len(tarefas) - i) / ritmo if ritmo > 0 else 0
                print(f"  [{i}/{len(tarefas)}] ok={ok} err={erros} "
                      f"({ritmo:.0f}/min, restam ~{resta:.0f} min)", flush=True)
                ultimo_log = agora

    dt = (time.time() - t0) / 60
    print(f"\n=== Sincronização concluída em {dt:.1f} min ===")
    print(f"Gerados: {ok:,} | Erros: {erros:,}")

    if falhas:
        print("\n--- Falhas (serão retentadas na próxima execução) ---")
        for a, i, msg in falhas[:20]:
            print(f"  {a} #{i}: {msg}")

    # Reaudita para confirmar (o log pode mentir; o cache não).
    d2 = diagnostico(obras)
    print(f"\nCobertura final: {d2['cobertura']}% "
          f"({len(d2['pendentes']):,} ainda pendentes)")

    os.makedirs(os.path.dirname(ESTADO), exist_ok=True)
    with open(ESTADO, "w", encoding="utf-8") as f:
        json.dump({"ultima_sincronizacao": time.strftime("%Y-%m-%d %H:%M:%S"),
                   "obras": len(obras), "gerados": ok, "erros": erros,
                   "pendentes": len(d2["pendentes"])}, f, ensure_ascii=False)

    return 0 if not d2["pendentes"] else 1


if __name__ == "__main__":
    sys.exit(main())
