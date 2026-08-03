"""Verificação de disponibilidade do Goshinsho (2026-08-03, plano de escala
-- item "monitoramento externo"). Pensado para rodar via cron a cada 5
minutos: bate em /health, e se o site estiver fora do ar ou degradado,
envia um alerta por e-mail -- deduplicado (não manda de novo a cada 5min
enquanto o problema persistir, só a cada ALERT_REPEAT_MINUTES) e envia um
segundo e-mail quando o site volta ao normal.

Não depende de nenhum serviço de terceiros (UptimeRobot etc.) -- reaproveita
a infraestrutura de e-mail (SES/Resend) já configurada no projeto.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from goshinsho.config import Config  # noqa: E402
from goshinsho.services.email_service import is_email_configured, send_email  # noqa: E402

HEALTH_URL = f"{Config.PUBLIC_SITE_URL}/health"
STATE_PATH = PROJECT_ROOT / "logs" / "uptime_check_state.json"
REQUEST_TIMEOUT_SECONDS = 15
ALERT_REPEAT_MINUTES = 30


def _load_state():
    if not STATE_PATH.exists():
        return {"down_since": None, "last_alert_at": None}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"down_since": None, "last_alert_at": None}


def _save_state(state):
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state), encoding="utf-8")


def _check_health():
    try:
        resp = requests.get(HEALTH_URL, timeout=REQUEST_TIMEOUT_SECONDS)
        if resp.status_code != 200:
            return False, f"HTTP {resp.status_code}"
        payload = resp.json()
        if payload.get("status") != "ok":
            return False, f"status degradado: {payload.get('checks')}"
        return True, None
    except Exception as exc:
        return False, f"erro de conexão: {exc}"


def _send_alert(subject, body):
    if not is_email_configured() or not Config.SES_CONTACT_TO_EMAIL:
        return
    try:
        send_email(Config.SES_CONTACT_TO_EMAIL, subject, body)
    except Exception:
        pass


def main():
    now = datetime.now(timezone.utc)
    ok, reason = _check_health()
    state = _load_state()

    if ok:
        if state.get("down_since"):
            _send_alert(
                "Goshinsho: site voltou ao normal",
                f"O /health voltou a responder normalmente às {now.isoformat()}.",
            )
        _save_state({"down_since": None, "last_alert_at": None})
        return

    down_since = state.get("down_since") or now.isoformat()
    last_alert_at = state.get("last_alert_at")
    should_alert = last_alert_at is None
    if not should_alert:
        try:
            last = datetime.fromisoformat(last_alert_at)
            should_alert = (now - last).total_seconds() >= ALERT_REPEAT_MINUTES * 60
        except ValueError:
            should_alert = True

    if should_alert:
        _send_alert(
            "Goshinsho: site fora do ar ou degradado",
            (
                f"Falha detectada em {HEALTH_URL} às {now.isoformat()}.\n"
                f"Motivo: {reason}\n\n"
                f"No ar desde (última vez que respondeu ok): {down_since}\n"
                f"Este alerta se repete a cada {ALERT_REPEAT_MINUTES} minutos enquanto o problema persistir."
            ),
        )
        _save_state({"down_since": down_since, "last_alert_at": now.isoformat()})
    else:
        _save_state({"down_since": down_since, "last_alert_at": last_alert_at})


if __name__ == "__main__":
    main()
