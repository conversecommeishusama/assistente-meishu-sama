"""Freio de mão automático por custo (2026-08-03) -- ver plano de escala em
GOSHINSHO.md. Única proteção contra gasto descontrolado de IA além do rate
limit por conta: um teto de gasto diário (Config.DAILY_COST_CAP_USD) com a
API DeepSeek. Ao ser atingido, novas perguntas são bloqueadas até o dia
seguinte (UTC) e um único e-mail de alerta é enviado ao responsável no
momento em que o teto é cruzado pela primeira vez naquele dia."""

from datetime import datetime, timezone
from pathlib import Path

from ..config import Config
from .deepseek_usage_service import today_cost_usd
from .email_service import is_email_configured, send_email

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALERT_MARKER_DIR = PROJECT_ROOT / "logs" / "cost_cap_alerts"


# 2026-08-03: níveis de aviso antecipado -- avisa bem antes do bloqueio
# acontecer, pra dar tempo do responsável reagir (ex. subir o teto na hora,
# se for crescimento real de campanha, não abuso) em vez de só saber quando
# já bloqueou todo mundo.
WARNING_THRESHOLDS = (0.5, 0.8)


def cost_cap_status():
    """Sem cache próprio -- reaproveita o cache curto de `today_cost_usd()`."""
    cap = Config.DAILY_COST_CAP_USD
    if not cap or cap <= 0:
        return {"enabled": False, "exceeded": False, "warning_level": None, "spent_usd": 0.0, "cap_usd": cap}
    spent = today_cost_usd()
    ratio = spent / cap
    warning_level = None
    for threshold in sorted(WARNING_THRESHOLDS, reverse=True):
        if ratio >= threshold:
            warning_level = threshold
            break
    return {
        "enabled": True,
        "exceeded": spent >= cap,
        "warning_level": warning_level,
        "spent_usd": spent,
        "cap_usd": cap,
    }


def _alert_marker_path(today):
    return ALERT_MARKER_DIR / f"{today.isoformat()}.sent"


def _warning_marker_path(today, threshold):
    return ALERT_MARKER_DIR / f"{today.isoformat()}_{int(threshold * 100)}.sent"


def maybe_send_warning_alert(status):
    """Alerta antecipado (1x por nível de aviso, por dia) -- chamado quando
    `status["warning_level"]` não é None mas o teto ainda não foi
    ultrapassado (`exceeded=False`); se já excedeu, `maybe_send_cap_alert`
    cuida do alerta, não este."""
    level = status.get("warning_level")
    if level is None or status.get("exceeded"):
        return
    today = datetime.now(timezone.utc).date()
    marker = _warning_marker_path(today, level)
    if marker.exists():
        return
    ALERT_MARKER_DIR.mkdir(parents=True, exist_ok=True)
    marker.touch()
    if not is_email_configured() or not Config.SES_CONTACT_TO_EMAIL:
        return
    try:
        send_email(
            Config.SES_CONTACT_TO_EMAIL,
            f"Goshinsho: {int(level * 100)}% do teto diário de IA já usado",
            (
                f"O gasto de hoje com a API DeepSeek chegou a US$ {status['spent_usd']:.2f} "
                f"({int(level * 100)}% do teto de US$ {status['cap_usd']:.2f}/dia).\n\n"
                "Isso ainda não bloqueou nada -- é só um aviso antecipado. Se o volume for "
                "crescimento real (ex. uma campanha de divulgação), considere subir "
                "DAILY_COST_CAP_USD no .env antes do teto ser atingido de fato."
            ),
        )
    except Exception:
        pass


def maybe_send_cap_alert(status):
    """Envia o alerta só uma vez por dia (marcador em disco) -- chamar toda
    vez que `status["exceeded"]` for True, é seguro chamar repetidamente."""
    if not status.get("exceeded"):
        return
    today = datetime.now(timezone.utc).date()
    marker = _alert_marker_path(today)
    if marker.exists():
        return
    ALERT_MARKER_DIR.mkdir(parents=True, exist_ok=True)
    marker.touch()
    if not is_email_configured() or not Config.SES_CONTACT_TO_EMAIL:
        return
    try:
        send_email(
            Config.SES_CONTACT_TO_EMAIL,
            "Goshinsho: teto de gasto diário com IA atingido",
            (
                f"O gasto de hoje com a API DeepSeek atingiu US$ {status['spent_usd']:.2f}, "
                f"acima do teto configurado (US$ {status['cap_usd']:.2f}/dia).\n\n"
                "Novas perguntas ao Goshinsho estão bloqueadas até a virada do dia (UTC). "
                "Confira o painel admin para mais detalhes, ou ajuste DAILY_COST_CAP_USD "
                "no .env se o teto precisar ser revisto."
            ),
        )
    except Exception:
        pass
