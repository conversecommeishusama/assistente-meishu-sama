import os
from datetime import timedelta

from dotenv import load_dotenv


load_dotenv()


def _env(name):
    value = os.environ.get(name)
    return value.strip().strip('"').strip("'") if value else None


class Config:
    SECRET_KEY = _env("FLASK_SECRET_KEY") or "dev-change-me"
    PERMANENT_SESSION_LIFETIME = timedelta(days=int(_env("PERMANENT_SESSION_DAYS") or 30))
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = True
    SESSION_REFRESH_EACH_REQUEST = True
    SUPABASE_URL = _env("SUPABASE_URL")
    SUPABASE_KEY = _env("SUPABASE_KEY") or _env("SUPABASE_ANON_KEY")
    DEEPSEEK_API_KEY = _env("DEEPSEEK_API_KEY")
    STRIPE_SECRET_KEY = _env("STRIPE_SECRET_KEY")
    STRIPE_WEBHOOK_SECRET = _env("STRIPE_WEBHOOK_SECRET")
    SEARCH_ROUTING = (_env("GOSHINSHO_SEARCH_ROUTING") or "hybrid").lower()
    AWS_REGION = _env("AWS_REGION") or "us-east-1"
    AWS_ACCESS_KEY_ID = _env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = _env("AWS_SECRET_ACCESS_KEY")
    SES_FROM_EMAIL = _env("SES_FROM_EMAIL")
    SES_CONTACT_TO_EMAIL = _env("SES_CONTACT_TO_EMAIL") or SES_FROM_EMAIL
    PRICE_MENSAL = "price_1TgCMzF2Js1cKxv5mwWP0nym"
    PRICE_ANUAL = "price_1TgCOQF2Js1cKxv5h3NyQQCp"
