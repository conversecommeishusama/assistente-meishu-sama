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

# O worker grava aqui o relatório de falhas de cada obra; o orquestrador lê o
# mesmo directório no fim. A constante vem do worker para não haver duas
# definições do mesmo caminho. `sys.path[0]` é o directório do script, por isso
# o import funciona quando isto é executado como `python scripts/<nome>.py`.
from gerar_texto_worker_v2 import FALHAS_DIR, RESUMOS_DIR  # noqa: E402

COLECOES_ORAIS = ["gokowa", "gosuiji", "mioshie"]

# O `.env` é carregado aqui (e não só no worker) para que o aviso sobre a chave
# Fish reflicta a realidade e para que daemons e workers herdem o mesmo
# ambiente. Sem isto, o pai — lançado pelo systemd, sem `EnvironmentFile` — não
# via nenhuma variável do `.env`.
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(RAIZ, ".env"))
except Exception:  # dotenv ausente ou .env ilegível: seguir com o ambiente
    pass


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


def _amostra_do_servico() -> str:
    """A amostra de voz que o SERVIÇO usa (a do `.env`).

    Lida do `tts_service` para não haver duas noções de "qual é a voz". O
    daemon tem uma omissão própria, mais antiga, e é por isso que ele precisa
    de receber esta por argumento.
    """
    try:
        sys.path.insert(0, RAIZ)
        from goshinsho.services import tts_service
        return tts_service._xtts_amostra()
    except Exception as e:
        print(f"AVISO: não foi possível ler a amostra do serviço ({e})",
              flush=True)
        return ""


def _resumo_da_obra(arquivo: str) -> str:
    """« | 12 novos, 340 em cache» — para o "concluído" não enganar.

    Sem isto, o log escrevia exactamente o mesmo para uma obra que gerou 1.200
    trechos e para uma que só revisitou o cache (2026-10-27).
    """
    caminho = os.path.join(RESUMOS_DIR, f"{arquivo}.json")
    try:
        with open(caminho, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return " | sem contagens (o worker não terminou)"
    novos = d.get("novos", 0)
    em_cache = (d.get("edge_cache", 0) + d.get("xtts_cache", 0))
    extra = f", {d['falhas']} falhas" if d.get("falhas") else ""
    return f" | {novos} novos, {em_cache} em cache{extra}"


def _resumir_falhas(com_falhas: list[str]) -> None:
    """Diz, no fim do lote, o que ficou sem áudio.

    Sem isto, o lote terminava com a mesma cara quer tivesse gerado tudo quer
    tivesse deixado trechos em branco: as falhas eram engolidas no worker e o
    orquestrador só olhava para `rc` (que era sempre 0). 2026-10-27.
    """
    relatorios = {}
    if os.path.isdir(FALHAS_DIR):
        for nome in sorted(os.listdir(FALHAS_DIR)):
            if not nome.endswith(".json"):
                continue
            try:
                with open(os.path.join(FALHAS_DIR, nome), encoding="utf-8") as f:
                    relatorios[nome] = json.load(f)
            except (OSError, ValueError):
                continue

    if not relatorios and not com_falhas:
        print("Lote terminado: nenhuma falha registada.", flush=True)
        return

    total = sum(len(d.get("falhas", [])) for d in relatorios.values())
    print("=" * 70, flush=True)
    print(f"LOTE TERMINADO COM FALHAS: {total} trecho(s) sem áudio em "
          f"{len(relatorios)} obra(s)", flush=True)
    for nome, dados in relatorios.items():
        print(f"  {len(dados.get('falhas', [])):>5}  {dados.get('arquivo', nome)}",
              flush=True)
    for nome in com_falhas:
        if not any(d.get("arquivo") == nome for d in relatorios.values()):
            # O worker saiu com erro sem deixar relatório (ex.: morreu a meio).
            print(f"  {'?':>5}  {nome} (sem relatório — o worker não terminou)",
                  flush=True)
    print(f"Detalhe por trecho em: {FALHAS_DIR}", flush=True)
    print("Reexecutar: systemctl restart goshinsho-tts-pregen", flush=True)
    print("=" * 70, flush=True)


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
    # Quantos workers partilham cada daemon. Com --workers 4 --daemons 2 são 2:
    # a espera de um trecho tem de contar com o trecho do vizinho à frente.
    por_daemon = max(1, -(-n // n_daemons))

    arquivos = listar_arquivos(todos=args.todos, lista=args.lista)
    estado = carregar_estado()
    feitos = set(estado.get("feitos", []))
    fila = arquivos if args.lista else [f for f in arquivos if f not in feitos]
    print(f"Total: {len(arquivos)} | feitos: {len(feitos)} | fila: {len(fila)}", flush=True)
    if not fila:
        print("Nada a fazer.", flush=True)
        return 0

    # Os relatórios do lote anterior vão para o lado: o resumo final tem de
    # falar só deste. Nada é apagado.
    #
    # ⚠️ Arquivar é contabilidade e NÃO pode derrubar o lote. A 27/10 este
    # bloco usava `os.replace(pasta, pasta + "_anterior")` e rebentou com
    # ENOTEMPTY (diretório de destino ainda com ficheiros), matando o serviço
    # no arranque. Agora: nome único com data, e qualquer falha é só um aviso.
    for pasta in (FALHAS_DIR, RESUMOS_DIR):
        if os.path.isdir(pasta) and os.listdir(pasta):
            destino = f"{pasta}_anterior_{time.strftime('%Y%m%dT%H%M%S')}"
            try:
                shutil.move(pasta, destino)
                print(f"Relatórios do lote anterior arquivados em {destino}",
                      flush=True)
            except (OSError, shutil.Error) as e:
                print(f"AVISO: não foi possível arquivar {pasta} ({e}) — a "
                      f"continuar; o resumo final pode incluir o lote anterior.",
                      flush=True)
        try:
            os.makedirs(pasta, exist_ok=True)
        except OSError as e:
            print(f"AVISO: não foi possível criar {pasta} ({e})", flush=True)

    # A chave Fish não é usada pelo lote (o daemon só fala XTTS). Sem este
    # aviso, um lote gerado com a chave no `.env` dava a impressão de ter saido
    # na voz aprovada.
    if (os.environ.get("GOSHINSHO_FISH_AUDIO_API_KEY")
            or os.environ.get("FISH_API_KEY")):
        print("AVISO: chave Fish presente, mas o lote gera em XTTS local "
              "(o daemon não usa Fish).", flush=True)
    else:
        print("Chave Fish ausente: o lote gera em XTTS local.", flush=True)

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
    #
    # ⚠️ A AMOSTRA TEM DE SER PASSADA. O `daemon_xtts.py` tem por omissão a
    # amostra ANTIGA (`amostra_meishu_30s_limpa.wav`), que NÃO é a do `.env`
    # (`amostra_meishu_oficial.wav`). Enquanto este Popen não a passava, o lote
    # sintetizava com a voz errada e gravava sob a chave certa
    # (`xtts:meishu:v2`) — arquivos que o app serve, indistinguíveis dos bons.
    # Em 27/10 o usuário ouviu o resultado e reconheceu a voz que já tinha
    # descartado. Uma amostra explícita é a única forma de garantir qual voz
    # está a falar.
    amostra = _amostra_do_servico()
    if not amostra or not os.path.exists(amostra):
        print(f"ERRO: amostra do XTTS não encontrada ({amostra!r}). A geração "
              f"com outra voz produziria arquivos válidos na chave errada — "
              f"a abortar.", flush=True)
        return 1
    print(f"Amostra de voz: {amostra}", flush=True)

    daemons = []  # (processo, spool_dir)
    for i in range(n_daemons):
        spool = os.path.join(SPOOL_BASE, f"d{i}")
        os.makedirs(spool, exist_ok=True)
        p = subprocess.Popen(
            [PYTHON_XTTS, DAEMON, "--spool", spool, "--amostra", amostra],
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
    com_falhas: list[str] = []
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
        # Espera por trecho = 600 s (tempo de UM trecho, medido com o lote 1:1)
        # × quantos workers partilham este daemon. Sem isto, o segundo worker do
        # spool desistia enquanto o primeiro ainda sintetizava — e as obras de
        # artigos longos (Eiko, Kyōshu Yōkō) falhavam por timeout sem avaria
        # nenhuma (2026-10-27).
        env["GOSHINSHO_XTTS_ESPERA_S"] = str(600 * por_daemon)
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
                if p.returncode == 0:
                    feitos.add(arquivo)
                    estado["feitos"] = sorted(feitos)
                    salvar_estado(estado)
                else:
                    # 2026-10-27: uma obra com trechos sem áudio NÃO entra no
                    # checkpoint — senão o modo sem `--lista` nunca a voltava a
                    # tentar e a falha ficava escondida para sempre. O relatório
                    # do worker fica em `data/tts_falhas/`.
                    com_falhas.append(arquivo)
                concluidas += 1
                rotulo = "concluído" if p.returncode == 0 else "COM FALHAS"
                print(f"[{concluidas}/{total_obras}] {rotulo}: {arquivo} "
                      f"(rc={p.returncode}){_resumo_da_obra(arquivo)}",
                      flush=True)
    except KeyboardInterrupt:
        print("\nInterrompido. Estado salvo — reexecute para retomar.", flush=True)
        for p in list(procs):
            try:
                p.terminate()
            except Exception:
                pass
    finally:
        _resumir_falhas(com_falhas)
        for p, _spool in daemons:
            try:
                p.terminate()
            except Exception:
                pass
        print("Daemons encerrados.", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
