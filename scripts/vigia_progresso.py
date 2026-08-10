"""Vigia por PROGRESSO, não por sessão viva.

O usuário observou, com razão, que este tipo de laço falha com frequência
neste projeto. O histórico confirma: a Fase G travou por auto-referência 11
iterações seguidas; a revisão editorial teve o mesmo bug três vezes; o
executor do chunk turn-aware sumiu depois de fechar a fila; o
`agentic_orcamento_fix` morreu na iteração 3 e ficou 7h parado; e a auditoria
morreu em 2026-08-09 23:24 e ficou 2h.

Um vigia que só checa `tmux has-session` pega UM desses modos. Os outros dois
passam batido:

  · invocação que TRAVA sem morrer — a sessão continua viva, o contador não
    anda (o motor tem teto de 3h por invocação, o que é uma eternidade)
  · laço que ACHA que terminou — sai limpo com a fila ainda cheia

Aqui o critério é o único que importa: o número andou? Se um laço tem
trabalho pendente e não produz nada por `PARADO_MIN` minutos, ele é morto e
religado, independentemente de parecer saudável.

Manda e-mail quando religa — mas no máximo um por hora por laço, para o aviso
não virar ruído que ninguém lê.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

RAIZ = Path("/var/www/goshinsho")
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "scripts"))

LOG = RAIZ / "reports/varredura_padronizacao/VIGIA.log"
R = RAIZ / "reports/varredura_padronizacao"
PARADO_MIN = 25          # sem produzir nada por tanto tempo = travado
INTERVALO_S = 180
ALERTA_MIN = 60          # no máximo um e-mail por laço por hora
DESTINO_EMAIL = "goshinsho@gmail.com"

COMANDOS = {
    "fidelidade": "venv/bin/python3 -u scripts/leitura_fidelidade.py >>/tmp/fidelidade.log 2>&1",
    "verifica": ('while true; do venv/bin/python3 -u scripts/verifica_fidelidade.py '
                 '>/tmp/verifica.log 2>&1; tmux has-session -t fidelidade 2>/dev/null '
                 '|| break; sleep 240; done'),
    "auditoria": "bash scripts/run_auditoria_loop.sh",
    "auditor_ds": ('while true; do venv/bin/python3 -u scripts/auditor_deepseek.py '
                   '>/tmp/auditor_ds.log 2>&1; tmux has-session -t fidelidade 2>/dev/null '
                   '|| break; sleep 300; done'),
}


def anota(txt: str) -> None:
    with LOG.open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now():%F %H:%M:%S}  {txt}\n")


def contagens() -> dict[str, tuple[int, int]]:
    """(feito, pendente) por laço — pendente=0 significa que pode parar em paz."""
    import auditoria as A
    import auditor_deepseek as D
    def n(p):
        try:
            return len(json.loads((R / p).read_text(encoding="utf-8")))
        except Exception:
            return 0
    lidos = n("LEITURA_FIDELIDADE.json")
    verif = n("VERIFICACAO_FIDELIDADE.json")
    au, ad = len(A.carrega()), len(D.carrega())
    proc = len(A.procedentes())
    return {
        "fidelidade": (lidos, max(0, 8030 - lidos)),
        "verifica": (verif, max(0, int(len(A.procedentes())) - verif)),
        "auditoria": (au, max(0, proc - au)),
        "auditor_ds": (ad, max(0, proc - ad)),
    }


def viva(s: str) -> bool:
    return subprocess.run(["tmux", "has-session", "-t", s],
                          capture_output=True).returncode == 0


def religa(s: str, motivo: str) -> None:
    subprocess.run(["tmux", "kill-session", "-t", s], capture_output=True)
    time.sleep(2)
    subprocess.run(["tmux", "new-session", "-d", "-s", s, COMANDOS[s]],
                   cwd=str(RAIZ), capture_output=True)
    anota(f"RELIGADO {s} — {motivo}")


def avisa(assunto: str, corpo: str) -> None:
    try:
        from goshinsho.services.email_service import is_email_configured, send_email
        if is_email_configured():
            send_email(DESTINO_EMAIL, assunto, corpo)
    except Exception as exc:
        anota(f"(falha ao enviar e-mail: {exc!r})")


def main() -> None:
    ultimo: dict[str, tuple[int, datetime]] = {}
    alertado: dict[str, datetime] = {}
    anota(f"vigia por progresso no ar — considera travado após {PARADO_MIN} min sem produzir")
    while True:
        try:
            c = contagens()
        except Exception as exc:
            anota(f"(erro ao contar: {exc!r})")
            time.sleep(INTERVALO_S)
            continue
        agora = datetime.now()
        for s, (feito, pend) in c.items():
            if pend <= 0:
                ultimo[s] = (feito, agora)
                continue
            if not viva(s):
                religa(s, "sessão morta")
                ultimo[s] = (feito, agora)
                continue
            ant = ultimo.get(s)
            if ant is None or feito > ant[0]:
                ultimo[s] = (feito, agora)
                continue
            parado = (agora - ant[1]).total_seconds() / 60
            if parado >= PARADO_MIN:
                religa(s, f"travado — {feito} há {parado:.0f} min com {pend} pendentes")
                ultimo[s] = (feito, agora)
                if (s not in alertado
                        or agora - alertado[s] > timedelta(minutes=ALERTA_MIN)):
                    alertado[s] = agora
                    avisa(f"[Goshinsho] laço {s} travou e foi religado",
                          f"O laço {s} ficou {parado:.0f} min sem produzir, com "
                          f"{pend} itens pendentes. Foi morto e religado "
                          f"automaticamente às {agora:%H:%M}.\n\n"
                          f"Histórico: reports/varredura_padronizacao/VIGIA.log")
        time.sleep(INTERVALO_S)


if __name__ == "__main__":
    main()
