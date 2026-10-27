#!/usr/bin/env python3
"""Worker de pré-geração (v2, usa daemon XTTS persistente).

O orquestrador (pre_gerar_lote_orais.py) sobe N daemons XTTS (modelo
residente) e N workers. Cada worker:
- Interlocutor (rótulo não-Meishu) -> edge-tts (Antônio), direto e rápido.
- Meishu-Sama / texto corrido -> envia tarefa ao daemon XTTS do seu spool
  (env XTTS_SPOOL) e aguarda o MP3 pronto (sem recarregar o modelo).

Uso (chamado pelo orquestrador):
  <venv_prod>/bin/python scripts/gerar_texto_worker_v2.py "<arquivo.txt>"
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import uuid

RAIZ = "/var/www/goshinsho"

# Relatório de falhas por obra. O orquestrador lê este directório no fim do
# lote; um ficheiro aqui é a lista de trechos que ficaram SEM áudio — antes
# essas falhas morriam num `except Exception: pass` (2026-10-27).
FALHAS_DIR = os.path.join(RAIZ, "data", "tts_falhas")

# Contagens por obra (quantos trechos eram realmente novos). Sem isto, o
# orquestrador escrevia "concluído" tanto para uma obra que gerou 1.200 trechos
# como para uma que só fez cache hit (2026-10-27).
RESUMOS_DIR = os.path.join(RAIZ, "data", "tts_resumos")

# Tempo máximo de espera pelo mp3 de um trecho XTTS.
#
# ⚠️ NÃO é «tempo de síntese de um trecho»: é o tempo de ESPERA NA FILA do
# spool. Quando dois workers partilham o mesmo daemon, um trecho pode ter de
# esperar pelo trecho do vizinho antes de começar. Em 2026-10-27 pus 300 s
# (assumindo ~30 s por trecho) e as obras longas — Eiko, Kyōshu Yōkō — passaram
# a falhar por timeout sem nada estar errado. O orquestrador define o valor
# conforme quantos workers partilham cada spool (`GOSHINSHO_XTTS_ESPERA_S`);
# 600 s é o tempo de UM trecho, medido com o lote 1:1.
LIMITE_XTTS_S = int(os.environ.get("GOSHINSHO_XTTS_ESPERA_S", "600"))
TENTATIVAS_XTTS = 2


def quebrar_como_front(texto: str) -> list[str]:
    trechos = []
    paragrafos = [re.sub(r"\s+", " ", p).strip()
                  for p in re.split(r"\n+", texto) if p.strip()]
    for par in paragrafos:
        partes = re.split(r"(?<=[.!?…])\s+", par)
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


def _esperar_mp3(destino: str, tarefa: str, spool: str,
                 limite: int = LIMITE_XTTS_S) -> tuple[str, str]:
    """Espera pelo mp3 do trecho. Devolve (estado, motivo).

    estados: "ok", "erro" (o daemon recusou), "timeout".

    Antes isto era um `while not os.path.exists(destino)` de 600 s: um daemon
    morto obrigava a esperar os 600 s completos, e uma falha do daemon ficava
    indistinguível de lentidão. Agora o desaparecimento da tarefa do spool diz
    logo o que aconteceu — o daemon move-a para `done/` no sucesso e para
    `erro/` na falha (2026-10-27).
    """
    inicio = time.time()
    fim = os.path.basename(tarefa)
    while time.time() - inicio < limite:
        if os.path.exists(destino) and os.path.getsize(destino) > 0:
            return "ok", ""
        if not os.path.exists(tarefa):
            if os.path.exists(os.path.join(spool, "erro", fim)):
                return "erro", "o daemon marcou a tarefa como erro"
            if os.path.exists(os.path.join(spool, "done", fim)):
                return "erro", "daemon concluiu a tarefa mas o mp3 não existe"
            return "erro", "tarefa desapareceu do spool"
        time.sleep(2)
    return "timeout", f"sem mp3 em {limite}s"


def _registrar_resumo(nome: str, contagens: dict,
                      dir_resumos: str = RESUMOS_DIR) -> None:
    """Grava as contagens da obra para o orquestrador poder dizer o que fez."""
    os.makedirs(dir_resumos, exist_ok=True)
    caminho = os.path.join(dir_resumos, f"{nome}.json")
    tmp = caminho + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"arquivo": nome, **contagens}, f, ensure_ascii=False,
                  indent=1)
    os.replace(tmp, caminho)


def _registrar_falhas(nome: str, falhas: list[dict],
                      dir_falhas: str = FALHAS_DIR) -> None:
    """Grava (ou limpa) o relatório de falhas desta obra."""
    os.makedirs(dir_falhas, exist_ok=True)
    caminho = os.path.join(dir_falhas, f"{nome}.json")
    if not falhas:
        if os.path.exists(caminho):
            try:
                os.remove(caminho)
            except OSError:
                pass
        return
    tmp = caminho + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"arquivo": nome, "falhas": falhas}, f, ensure_ascii=False,
                  indent=1)
    os.replace(tmp, caminho)


def main() -> int:
    if len(sys.argv) < 2:
        print("uso: gerar_texto_worker_v2.py '<arquivo.txt>'", file=sys.stderr)
        return 2
    nome = sys.argv[1]
    caminho = os.path.join(RAIZ, "textos_leitura_colaborativa", nome)
    if not os.path.exists(caminho):
        print(f"arquivo não encontrado: {caminho}", file=sys.stderr)
        return 1

    spool = os.environ.get("XTTS_SPOOL", os.path.join(RAIZ, "data", "tts_spool", "d0"))
    os.makedirs(spool, exist_ok=True)

    sys.path.insert(0, RAIZ)
    os.chdir(RAIZ)
    from dotenv import load_dotenv
    load_dotenv(os.path.join(RAIZ, ".env"))
    from goshinsho.services import tts_service

    return processar_obra(caminho, spool, tts_service)


def processar_obra(caminho: str, spool: str, tts_service, *,
                   dir_falhas: str = FALHAS_DIR,
                   dir_resumos: str = RESUMOS_DIR) -> int:
    """Gera o áudio de uma obra. Devolve 0 se tudo saiu, 1 se algo falhou.

    Separada de `main()` para poder ser testada sem tocar no corpus real nem
    no serviço de TTS (o teste passa um duplo no lugar de `tts_service`).
    """
    with open(caminho) as f:
        texto = f.read()
    trechos = quebrar_como_front(texto)
    arquivo = os.path.basename(caminho)

    t0 = time.time()
    n_edge_novo = n_edge_cache = 0
    n_xtts_novo = n_xtts_cache = 0
    n_pausa = n_vazio = 0
    falhas: list[dict] = []

    def falhou(i, trecho, provedor, motivo):
        limpo = re.sub(r"\s+", " ", trecho)
        falhas.append({
            "indice": i,
            "provedor": provedor,
            "motivo": motivo[:300],
            "excerto": limpo[:120],
        })
        print(f"[{arquivo}] FALHA {provedor} trecho {i}: {motivo} | "
              f"{limpo[:70]}", file=sys.stderr, flush=True)

    if tts_service._fish_disponivel():
        # A chave Fish não entra no lote: o daemon só fala XTTS. Dizer isto uma
        # vez evita a conclusão errada de que o áudio saiu na voz aprovada.
        print(f"[{arquivo}] AVISO: chave Fish presente; o lote gera em XTTS "
              f"local (o daemon não usa Fish).", file=sys.stderr, flush=True)

    for i, trecho in enumerate(trechos):
        # 2026-10-23: a autoria vem ANTES do falante. Um trecho de obra de
        # terceiros (testemunho de fiel, manual institucional) não pode sair na
        # voz do Meishu-Sama, mesmo sem rótulo de fala.
        provedor, _voz = tts_service.provedor_canonico(trecho, arquivo=arquivo)

        if provedor == "edge":
            # Narrador (Antônio). Passa `arquivo` também aqui: a autoria e o
            # rótulo de fala continuam a ser a única regra, e assim este ramo
            # não diverge do caminho do app.
            ja = tts_service.caminho_em_cache(trecho, arquivo=arquivo)
            try:
                tts_service.sintetizar(trecho, voz="meishu", arquivo=arquivo)
            except Exception as e:
                # 2026-10-27: aqui havia `except Exception: pass`. Um trecho
                # ficava sem áudio e o lote dizia "concluído" — a falha nunca
                # chegava a nenhum relatório.
                falhou(i, trecho, "edge", f"{type(e).__name__}: {e}")
                continue
            if tts_service._trecho_sem_fala(trecho):
                n_pausa += 1
            elif ja:
                n_edge_cache += 1
            else:
                n_edge_novo += 1
            continue

        # Voz do Meishu-Sama -> XTTS (via daemon).
        # A preparação é a do SERVIÇO, não uma cópia local: antes o worker
        # sanitizava por conta própria e não aplicava pronúncias nem removia
        # macrons, por isso o mesmo texto saía diferente do áudio gerado sob
        # demanda pelo app — com a MESMA chave de cache (2026-10-27).
        texto_tts = tts_service._preparar_texto_xtts(trecho)
        if not texto_tts:
            n_vazio += 1
            continue
        # 2026-10-22: a chave era "xtts:meishu" (sem versão) e o app procura
        # "xtts:meishu:v2" — o lote gravava ficheiros que o serviço nunca
        # encontrava e regerava o que já existia. Usar a constante do serviço.
        chave = tts_service._chave_cache(
            f"xtts:{tts_service.VOZ_MEISHU_CACHE}", trecho, "+0%")
        destino = os.path.join(tts_service._cache_dir(), f"{chave}.mp3")
        if os.path.exists(destino) and os.path.getsize(destino) > 0:
            n_xtts_cache += 1
            continue  # já gerado
        # QUALQUER áudio que o app sirva para este trecho já resolve: a voz
        # APROVADA (Fish), a chave antiga do XTTS… A 27/10 o worker só olhava
        # a chave canónica e as históricas por conta própria; com a regra da
        # voz aprovada a viver no serviço, isto passa a ser uma pergunta só.
        # E importa: gerar XTTS sobre um trecho que já tem o áudio pago em
        # disco é trabalho perdido que ainda por cima tapa o aprovado.
        if tts_service.caminho_em_cache(trecho, arquivo=arquivo):
            n_xtts_cache += 1
            continue

        # Envia tarefa ao daemon e aguarda o MP3.
        os.makedirs(os.path.dirname(destino) or ".", exist_ok=True)
        estado, motivo = "erro", "sem tentativas"
        for tentativa in range(1, TENTATIVAS_XTTS + 1):
            tid = f"{os.getpid()}_{i}_{uuid.uuid4().hex[:8]}"
            tarefa = os.path.join(spool, f"tarefa_{tid}.json")
            try:
                with open(tarefa, "w") as f:
                    json.dump({"texto": texto_tts, "destino": destino}, f)
            except OSError as e:
                estado, motivo = "erro", f"erro ao escrever no spool: {e}"
                time.sleep(2)
                continue
            estado, motivo = _esperar_mp3(destino, tarefa, spool)
            if estado == "ok":
                break
            # Uma tarefa que não chegou a ser consumida (timeout) não deve
            # ficar no spool para ser gerada mais tarde, sem ninguém à espera.
            if os.path.exists(tarefa):
                try:
                    os.remove(tarefa)
                except OSError:
                    pass
            # Não se repete um TIMEOUT: o daemon pode estar simplesmente a
            # acabar (ou a tarefa ainda na fila), e uma segunda tarefa igual
            # faria o mesmo trabalho outra vez. Só se repete uma recusa.
            if estado == "timeout":
                break
            if tentativa < TENTATIVAS_XTTS:
                print(f"[{arquivo}] trecho {i}: {motivo} — a repetir "
                      f"({tentativa}/{TENTATIVAS_XTTS - 1})", file=sys.stderr,
                      flush=True)
                time.sleep(3)

        if estado == "ok":
            n_xtts_novo += 1
        else:
            falhou(i, trecho, "xtts", motivo)
            continue

    total = (n_edge_novo + n_edge_cache + n_xtts_novo + n_xtts_cache
             + n_pausa + n_vazio + len(falhas))
    contagens = {
        "trechos": total,
        "novos": n_edge_novo + n_xtts_novo,
        "edge_novos": n_edge_novo,
        "edge_cache": n_edge_cache,
        "xtts_novos": n_xtts_novo,
        "xtts_cache": n_xtts_cache,
        "pausas": n_pausa,
        "vazios": n_vazio,
        "falhas": len(falhas),
        "segundos": round(time.time() - t0, 1),
    }
    # "novos" é o que distingue trabalho real de cache hit: sem isto, o
    # "concluído" do orquestrador era idêntico para uma obra gerada agora e
    # para uma que não fez nada (2026-10-27).
    print(
        f"[{arquivo}] FIM: {total} trechos | "
        f"edge {n_edge_novo + n_edge_cache} ({n_edge_novo} novos) | "
        f"xtts {n_xtts_novo + n_xtts_cache} ({n_xtts_novo} novos) | "
        f"pausa {n_pausa} | vazio {n_vazio} | falhas {len(falhas)} | "
        f"novos {contagens['novos']} | {contagens['segundos']:.0f}s",
        file=sys.stderr, flush=True,
    )

    _registrar_resumo(arquivo, contagens, dir_resumos)
    _registrar_falhas(arquivo, falhas, dir_falhas)
    return 1 if falhas else 0


if __name__ == "__main__":
    sys.exit(main())
