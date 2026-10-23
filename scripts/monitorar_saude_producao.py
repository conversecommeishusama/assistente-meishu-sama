#!/usr/bin/env python3
"""Monitor de saúde de produção do Goshinsho.

Motivação (2026-10-21): o app ficou lento sem ninguém saber. Medido no access
log do Caddy: 41% dos /api/chat passavam de 60s, o pior caso aos 171s, e um
504 aos 165,8s. Em paralelo, o lote TTS estava travado há 13h a queimar 13,5
dos 14 cores (load average 45), roubando CPU do gunicorn. Nada disto gerou
aviso -- a primeira notícia foi o usuário a dizer "está lento e não responde".

Este script fecha esse buraco: verifica a cada execução um conjunto pequeno de
sinais que, juntos, explicam quase toda degradação observada, e manda e-mail
APENAS quando um sinal muda de estado (OK -> FALHA, e FALHA -> OK na
recuperação), com re-aviso espaçado enquanto a falha persistir. Sem spam.

Sinais verificados:

  1. serviços systemd ativos (goshinsho, goshinsho-portal, caddy)
  2. /health responde 200 dentro do limite
  3. load average (1 min) acima do teto -> pega TTS/processos a queimar CPU
  4. memória disponível abaixo do piso
  5. disco acima do teto
  6. p95 de /api/chat acima do teto -> pega o pipeline a degradar
  7. taxa de 5xx acima do teto -> pega 502/504 (workers mortos, fila)

Uso:
    venv/bin/python scripts/monitorar_saude_producao.py            # uma passagem
    venv/bin/python scripts/monitorar_saude_producao.py --verbose  # mostra tudo
    venv/bin/python scripts/monitorar_saude_producao.py --dry-run  # não envia e-mail

Sai com código 1 se algum sinal estiver em falha (útil para systemd/monitoria
externa), 0 se tudo normal.

Instalado por goshinsho-monitor.timer (a cada 5 min). Ver README no fim.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

# ---------------------------------------------------------------------------
# Limiares (todos sobrescrevíveis por variável de ambiente, para afinar sem
# editar código).
# ---------------------------------------------------------------------------
NPROC = os.cpu_count() or 4

# load average de 1 minuto. Teto 8, como pedido. Contexto medido nesta máquina
# (14 cores): repouso ~4, e o incidente de 21/10 chegou a 45 com o TTS travado.
# Acima de 8 há sempre algo errado -- não é o caso de "máquina a trabalhar".
MAX_LOAD = float(os.environ.get("MONITOR_MAX_LOAD", 8.0))

# p95 de /api/chat. Referência medida: perguntas normais levam 27-57s; as
# difíceis (fontes que se contradizem) 130-175s. O p95 real desta instalação
# anda em 100-131s mesmo com a máquina ociosa -- é o pipeline conhecido
# (~100s de busca + ~40s de síntese), não fila nem regressão. Um limite de 90s
# disparava sempre, o que treina quem lê o log a ignorar o alerta. 140s fica
# acima do p95 observado e abaixo do timeout de 300s: só alerta se o pipeline
# sair do envelope documentado. Baixar para 90-100s só faz sentido se o
# pipeline encolher.
MAX_P95_CHAT = float(os.environ.get("MONITOR_MAX_P95_CHAT", 140.0))

# Janela da análise do access log. 24h (e não minutos) porque o volume real de
# /api/chat é baixo: 111 pedidos em 7 dias = ~0,7/hora. Uma janela curta quase
# nunca teria amostra suficiente e o sinal ficaria permanentemente "ignorado".
# Os 6 MiB de cauda lidos cobrem bem mais que 24h no tráfego actual.
JANELA_CHAT_MIN = int(os.environ.get("MONITOR_JANELA_CHAT_MIN", 1440))
MIN_AMOSTRAS_CHAT = int(os.environ.get("MONITOR_MIN_AMOSTRAS_CHAT", 3))

# 5xx: só avaliamos com tráfego suficiente, e o limite é percentual.
JANELA_5XX_MIN = int(os.environ.get("MONITOR_JANELA_5XX_MIN", 15))
MIN_AMOSTRAS_5XX = int(os.environ.get("MONITOR_MIN_AMOSTRAS_5XX", 20))
MAX_5XX_PCT = float(os.environ.get("MONITOR_MAX_5XX_PCT", 5.0))
# Mínimo ABSOLUTO de erros, além da percentagem. Reiniciar o gunicorn gera
# 3-5 x 502 em poucos segundos durante o boot; com pouco tráfego nessa janela,
# isso passa facilmente dos 5% e geraria alarme por uma manutenção previsível.
MIN_ERROS_5XX = int(os.environ.get("MONITOR_MIN_ERROS_5XX", 10))

MAX_DISCO_PCT = float(os.environ.get("MONITOR_MAX_DISCO_PCT", 85.0))
MIN_MEM_DISPONIVEL_PCT = float(os.environ.get("MONITOR_MIN_MEM_PCT", 10.0))

# /health tem de responder rápido -- se demora, o gunicorn está saturado mesmo
# que responda. 5s já é muito para um endpoint que mede 0,01s em repouso.
MAX_HEALTH_SEG = float(os.environ.get("MONITOR_MAX_HEALTH_SEG", 5.0))

SERVICOS = ("goshinsho", "goshinsho-portal", "caddy")
URL_HEALTH = os.environ.get("MONITOR_HEALTH_URL", "http://127.0.0.1:8000/health")
ACCESS_LOG = Path(os.environ.get("MONITOR_ACCESS_LOG", "/var/log/caddy/access.log"))

# Quanto do fim do access log ler. 6 MiB cobre folgadamente 60 min de tráfego
# no volume actual (~28k pedidos/dia); evita varrer os 43 MiB do ficheiro.
ACCESS_TAIL_BYTES = int(os.environ.get("MONITOR_ACCESS_TAIL_BYTES", 6 * 1024 * 1024))

ESTADO_PATH = Path(
    os.environ.get("MONITOR_ESTADO", "/var/lib/goshinsho-monitor/estado.json")
)
LOG_PATH = Path(os.environ.get("MONITOR_LOG", str(RAIZ / "logs" / "monitor_saude.log")))

# Re-aviso: se a falha persiste, volta a avisar só depois disto (segundos).
REAVISO_SEG = int(os.environ.get("MONITOR_REAVISO_SEG", 6 * 3600))


# ---------------------------------------------------------------------------
# Verificações. Cada uma devolve (ok: bool, detalhe: str).
# ---------------------------------------------------------------------------
def verificar_servicos() -> tuple[bool, str]:
    inativos = []
    for nome in SERVICOS:
        try:
            res = subprocess.run(
                ["systemctl", "is-active", nome],
                capture_output=True, text=True, timeout=10,
            )
            estado = (res.stdout or "").strip()
        except Exception as exc:
            inativos.append(f"{nome}=erro({exc})")
            continue
        if estado != "active":
            inativos.append(f"{nome}={estado or 'desconhecido'}")
    if inativos:
        return False, "serviços fora do ar: " + ", ".join(inativos)
    return True, "todos ativos: " + ", ".join(SERVICOS)


def verificar_health() -> tuple[bool, str]:
    import urllib.error
    import urllib.request

    inicio = datetime.now(timezone.utc).timestamp()
    try:
        with urllib.request.urlopen(URL_HEALTH, timeout=MAX_HEALTH_SEG) as resp:
            corpo = resp.read(4096).decode("utf-8", "replace")
            codigo = resp.status
    except Exception as exc:
        return False, f"/health falhou: {type(exc).__name__}: {exc}"
    decorrido = datetime.now(timezone.utc).timestamp() - inicio

    if codigo != 200:
        return False, f"/health devolveu HTTP {codigo} em {decorrido:.2f}s"
    if decorrido > MAX_HEALTH_SEG:
        return False, f"/health lento: {decorrido:.2f}s (limite {MAX_HEALTH_SEG:.1f}s)"
    try:
        dados = json.loads(corpo)
    except Exception:
        return True, f"/health 200 em {decorrido:.2f}s (corpo não-JSON)"
    if dados.get("status") not in (None, "ok"):
        return False, f"/health status={dados.get('status')!r}"
    return True, f"/health 200 em {decorrido:.2f}s, status=ok"


def verificar_load() -> tuple[bool, str]:
    try:
        load1 = os.getloadavg()[0]
    except OSError as exc:
        return True, f"load indisponível ({exc})"
    ok = load1 <= MAX_LOAD
    return ok, f"load(1m) {load1:.2f} / limite {MAX_LOAD:.1f} ({NPROC} cores)"


def verificar_memoria() -> tuple[bool, str]:
    # /proc/meminfo: MemAvailable é a estimativa correta do que ainda pode ser
    # alocado (MemFree ignora cache reaproveitável e dá falsos alarmes).
    campos: dict[str, int] = {}
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for linha in f:
                partes = linha.split()
                if len(partes) >= 2:
                    campos[partes[0].rstrip(":")] = int(partes[1])
    except Exception as exc:
        return True, f"memória indisponível ({exc})"
    total = campos.get("MemTotal") or 0
    disponivel = campos.get("MemAvailable") or 0
    if not total:
        return True, "MemTotal ausente em /proc/meminfo"
    pct = disponivel / total * 100
    ok = pct >= MIN_MEM_DISPONIVEL_PCT
    return ok, (
        f"memória disponível {disponivel / 1024 / 1024:.1f} GiB "
        f"({pct:.1f}%) / piso {MIN_MEM_DISPONIVEL_PCT:.0f}%"
    )


def verificar_disco() -> tuple[bool, str]:
    try:
        st = os.statvfs("/")
    except OSError as exc:
        return True, f"disco indisponível ({exc})"
    total = st.f_blocks
    livre = st.f_bavail
    if not total:
        return True, "statvfs devolveu 0 blocos"
    usado_pct = (total - livre) / total * 100
    ok = usado_pct <= MAX_DISCO_PCT
    livre_gib = livre * st.f_frsize / 1024**3
    return ok, f"disco {usado_pct:.1f}% usado (livre {livre_gib:.0f} GiB) / teto {MAX_DISCO_PCT:.0f}%"


def _ler_fim_access_log() -> list[dict]:
    """Lê e decodifica as linhas JSON do fim do access log do Caddy.

    Lê só os últimos ACCESS_TAIL_BYTES (o ficheiro chega a 43 MiB+). A primeira
    linha é descartada quando o corte caiu a meio de um registo.
    """
    if not ACCESS_LOG.exists():
        raise FileNotFoundError(f"{ACCESS_LOG} não existe")
    tamanho = ACCESS_LOG.stat().st_size
    with ACCESS_LOG.open("rb") as f:
        if tamanho > ACCESS_TAIL_BYTES:
            f.seek(tamanho - ACCESS_TAIL_BYTES)
            f.readline()  # descarta a linha parcial do início
        bruto = f.read()

    registos = []
    for linha in bruto.split(b"\n"):
        linha = linha.strip()
        if not linha:
            continue
        try:
            registos.append(json.loads(linha))
        except Exception:
            # Linha truncada/rotada a meio: ignorar em silêncio.
            continue
    return registos


def _timestamp_registo(registo: dict) -> float | None:
    ts = registo.get("ts")
    return float(ts) if isinstance(ts, (int, float)) else None


def _amostra_access_log(janela_min: int) -> tuple[list[dict], float | None]:
    """Registos dentro da janela (e o instante do registo mais recente).

    Usa o `ts` do registo mais recente como referência em vez de "agora": o log
    pode ter minutos de atraso, e comparar com o relógio actual produziria
    janelas vazias ou mal calculadas.
    """
    registos = _ler_fim_access_log()
    if not registos:
        return [], None
    timestamps = [t for t in (_timestamp_registo(r) for r in registos) if t]
    if not timestamps:
        return [], None
    referencial = max(timestamps)
    corte = referencial - janela_min * 60
    na_janela = [
        r for r in registos
        if (_timestamp_registo(r) or 0) >= corte
    ]
    return na_janela, referencial


def verificar_p95_chat() -> tuple[bool, str]:
    import math

    try:
        amostra, _ = _amostra_access_log(JANELA_CHAT_MIN)
    except FileNotFoundError as exc:
        return True, f"ignorado ({exc})"
    except Exception as exc:
        return True, f"ignorado (leitura do access log: {type(exc).__name__}: {exc})"

    duracoes = [
        float(r["duration"])
        for r in amostra
        if r.get("request", {}).get("uri") == "/api/chat" and r.get("duration") is not None
    ]
    if len(duracoes) < MIN_AMOSTRAS_CHAT:
        return True, (
            f"ignorado: {len(duracoes)} amostra(s) de /api/chat em {JANELA_CHAT_MIN} min "
            f"(mínimo {MIN_AMOSTRAS_CHAT})"
        )

    duracoes.sort()
    # p95 por índice mais próximo (suficiente e sem dependências).
    indice = min(len(duracoes) - 1, max(0, math.ceil(0.95 * len(duracoes)) - 1))
    p95 = duracoes[indice]
    ok = p95 <= MAX_P95_CHAT
    return ok, (
        f"p95 /api/chat {p95:.1f}s / limite {MAX_P95_CHAT:.0f}s "
        f"(n={len(duracoes)} em {JANELA_CHAT_MIN} min, máx {duracoes[-1]:.1f}s)"
    )


def verificar_5xx() -> tuple[bool, str]:
    try:
        amostra, _ = _amostra_access_log(JANELA_5XX_MIN)
    except FileNotFoundError as exc:
        return True, f"ignorado ({exc})"
    except Exception as exc:
        return True, f"ignorado (leitura do access log: {type(exc).__name__}: {exc})"

    status = [
        int(r["status"])
        for r in amostra
        if isinstance(r.get("status"), int)
    ]
    if len(status) < MIN_AMOSTRAS_5XX:
        return True, (
            f"ignorado: {len(status)} pedido(s) em {JANELA_5XX_MIN} min "
            f"(mínimo {MIN_AMOSTRAS_5XX})"
        )
    erros = sum(1 for s in status if 500 <= s <= 599)
    pct = erros / len(status) * 100
    if erros < MIN_ERROS_5XX:
        return True, (
            f"ok: 5xx {pct:.1f}% mas só {erros} erro(s) em {JANELA_5XX_MIN} min "
            f"(mínimo para alarmar: {MIN_ERROS_5XX} -- cobre reinícios)"
        )
    ok = pct <= MAX_5XX_PCT
    return ok, (
        f"5xx {pct:.1f}% / teto {MAX_5XX_PCT:.0f}% "
        f"({erros}/{len(status)} em {JANELA_5XX_MIN} min)"
    )


VERIFICACOES = (
    ("servicos", "Serviços systemd", verificar_servicos),
    ("health", "Endpoint /health", verificar_health),
    ("load", "Carga de CPU", verificar_load),
    ("memoria", "Memória", verificar_memoria),
    ("disco", "Disco", verificar_disco),
    ("p95_chat", "Latência p95 de /api/chat", verificar_p95_chat),
    ("taxa_5xx", "Taxa de erros 5xx", verificar_5xx),
)


# ---------------------------------------------------------------------------
# Estado e notificação
# ---------------------------------------------------------------------------
def _carregar_estado() -> dict:
    try:
        with ESTADO_PATH.open(encoding="utf-8") as f:
            dados = json.load(f)
            return dados if isinstance(dados, dict) else {}
    except Exception:
        return {}


def _guardar_estado(estado: dict) -> None:
    try:
        ESTADO_PATH.parent.mkdir(parents=True, exist_ok=True)
        temporario = ESTADO_PATH.with_suffix(".tmp")
        with temporario.open("w", encoding="utf-8") as f:
            json.dump(estado, f, ensure_ascii=False, indent=2)
        temporario.replace(ESTADO_PATH)
    except Exception as exc:
        print(f"AVISO: não foi possível gravar o estado: {exc}", file=sys.stderr)


def _enviar_alerta(assunto: str, corpo: str) -> None:
    """Envia por e-mail reutilizando o serviço do app.

    Falha em silêncio (só para o log): o monitor nunca deve morrer por causa do
    canal de notificação -- mas também nunca deve esconder a falha que detectou,
    que continua registada no log e no código de saída.
    """
    try:
        from goshinsho.config import Config
        from goshinsho.services.email_service import is_email_configured, send_email

        destino = Config.SES_CONTACT_TO_EMAIL
        if not is_email_configured() or not destino:
            print("AVISO: e-mail não configurado; alerta só no log.", file=sys.stderr)
            return
        send_email(destino, assunto, corpo)
        print(f"alerta enviado para {destino}: {assunto}")
    except Exception as exc:
        print(f"AVISO: falha ao enviar alerta: {type(exc).__name__}: {exc}", file=sys.stderr)


def executar(dry_run: bool = False, verbose: bool = False) -> int:
    agora = datetime.now(timezone.utc)
    estado = _carregar_estado()
    resultados = []
    mudancas_alerta = []
    mudancas_recuperacao = []

    for chave, rotulo, funcao in VERIFICACOES:
        try:
            ok, detalhe = funcao()
        except Exception as exc:  # uma verificação quebrada não derruba as outras
            ok, detalhe = False, f"verificação falhou: {type(exc).__name__}: {exc}"
        resultados.append((chave, rotulo, ok, detalhe))

        anterior = estado.get(chave) or {}
        estava_ok = anterior.get("ok")
        ultimo_aviso = float(anterior.get("ultimo_aviso") or 0)
        instante = agora.timestamp()

        if not ok:
            deve_avisar = (
                estava_ok is not False  # primeiro registo ou transição OK->FALHA
                or (instante - ultimo_aviso) >= REAVISO_SEG
            )
            if deve_avisar:
                mudancas_alerta.append((rotulo, detalhe, estava_ok))
                ultimo_aviso = instante
        elif estava_ok is False:
            mudancas_recuperacao.append((rotulo, detalhe))

        estado[chave] = {
            "ok": ok,
            "detalhe": detalhe,
            "verificado_em": agora.isoformat(),
            "ultimo_aviso": ultimo_aviso,
        }

    # --- log por execução ---------------------------------------------------
    em_falha = [r for r in resultados if not r[2]]
    cabecalho = f"[{agora.isoformat(timespec='seconds')}] {'FALHA' if em_falha else 'ok'}"
    linhas_log = [cabecalho]
    for chave, rotulo, ok, detalhe in resultados:
        marca = "FALHA" if not ok else "  ok "
        if not ok or verbose:
            linhas_log.append(f"  [{marca}] {rotulo}: {detalhe}")
    for linha in linhas_log:
        print(linha)
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as f:
            for linha in linhas_log:
                f.write(linha + "\n")
    except Exception:
        pass

    # --- notificações -------------------------------------------------------
    if mudancas_alerta:
        assunto = f"Goshinsho: {len(mudancas_alerta)} problema(s) detectado(s) na saúde do app"
        corpo = [
            f"Monitor de saúde do Goshinsho -- {agora.isoformat(timespec='seconds')}",
            "",
            "Sinais em FALHA:",
        ]
        for rotulo, detalhe, estava_ok in mudancas_alerta:
            corpo.append(f"  - {rotulo}: {detalhe}")
            if estava_ok is None:
                corpo.append("    (primeira leitura deste sinal)")
        corpo += [
            "",
            "Verificação completa nesta execução:",
        ]
        for chave, rotulo, ok, detalhe in resultados:
            corpo.append(f"  {'FALHA' if not ok else 'OK   '} {rotulo}: {detalhe}")
        corpo += [
            "",
            "O que olhar primeiro:",
            "  1. systemctl status goshinsho goshinsho-portal goshinsho-tts-pregen",
            "  2. uptime  (load alto = processo a queimar CPU; o TTS é o suspeito habitual)",
            "  3. journalctl -u goshinsho --since '30 min ago' | grep -iE 'timeout|error'",
            "  4. tail -20 /var/log/caddy/access.log  (502/504 e durações)",
            "",
            f"Log do monitor: {LOG_PATH}",
        ]
        if dry_run:
            print("[dry-run] NÃO enviado:\n" + "\n".join(corpo))
        else:
            _enviar_alerta(assunto, "\n".join(corpo))

    if mudancas_recuperacao:
        assunto = "Goshinsho: saúde normalizada"
        corpo = [
            f"Monitor de saúde do Goshinsho -- {agora.isoformat(timespec='seconds')}",
            "",
            "Estes sinais voltaram ao normal:",
        ]
        for rotulo, detalhe in mudancas_recuperacao:
            corpo.append(f"  - {rotulo}: {detalhe}")
        if dry_run:
            print("[dry-run] NÃO enviado:\n" + "\n".join(corpo))
        else:
            _enviar_alerta(assunto, "\n".join(corpo))

    _guardar_estado(estado)
    return 1 if em_falha else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true", help="não envia e-mail")
    ap.add_argument("--verbose", action="store_true", help="mostra todos os sinais, mesmo OK")
    args = ap.parse_args()
    return executar(dry_run=args.dry_run, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
