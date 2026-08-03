"""Freio de mão automático por custo (2026-08-03) -- ver plano de escala em
CLAUDE.md. Única proteção contra gasto descontrolado de IA além do rate
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


def cost_cap_status():
    """Sem cache próprio -- reaproveita o cache curto de `today_cost_usd()`."""
    cap = Config.DAILY_COST_CAP_USD
    if not cap or cap <= 0:
        return {"enabled": False, "exceeded": False, "spent_usd": 0.0, "cap_usd": cap}
    spent = today_cost_usd()
    return {"enabled": True, "exceeded": spent >= cap, "spent_usd": spent, "cap_usd": cap}


def _alert_marker_path(today):
    return ALERT_MARKER_DIR / f"{today.isoformat()}.sent"


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
