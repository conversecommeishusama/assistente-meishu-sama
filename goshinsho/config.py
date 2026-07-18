import os
from datetime import timedelta

from dotenv import load_dotenv


load_dotenv()


def _env(name):
    value = os.environ.get(name)
    return value.strip().strip('"').strip("'") if value else None


def _env_bool(name: str, *, default: bool = True) -> bool:
    raw = _env(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


class Config:
    SECRET_KEY = _env("FLASK_SECRET_KEY") or "dev-change-me"
    PUBLIC_SITE_URL = (_env("PUBLIC_SITE_URL") or "https://goshinsho.com.br").rstrip("/")
    SUPABASE_SERVICE_ROLE_KEY = _env("SUPABASE_SERVICE_ROLE_KEY")
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
    PIPELINE = (_env("GOSHINSHO_PIPELINE") or "v2").lower()
    # Modo orientação / sacerdócio (pastoral). false = pausado até retomar.
    ORIENTATION_MODE_ENABLED = _env_bool("GOSHINSHO_ORIENTATION_MODE", default=True)
    # Tutela Johrei Ho Koza (inject + prompt). Desactivada por defeito — testar busca genérica + glossário.
    JOHREI_HO_KOZA_PRIORITY = _env_bool("GOSHINSHO_JOHREI_HO_KOZA", default=False)
    # Termo isolado do glossário → intenção definicional + enriquecimento de busca.
    DEFINITIONAL_GLOSSARY_TERM = _env_bool("GOSHINSHO_DEFINITIONAL_GLOSSARY", default=True)
    # Perguntas definicionais: priorizar palavra escrita sobre oral (Gosuiji/Mioshie-shū).
    # Desactivado por defeito — testes mostraram perda de qualidade nas respostas finais.
    SOURCE_HIERARCHY_WRITTEN_FIRST = _env_bool("GOSHINSHO_SOURCE_HIERARCHY", default=False)
    # Se o v2 não cobre a pergunta, segunda busca com motor legacy sem tutelas.
    LEGACY_MOTOR_FALLBACK = _env_bool("GOSHINSHO_LEGACY_MOTOR_FALLBACK", default=True)
    # Modo Pesquisa Profunda (Tier 2 opt-in): multi-busca + síntese.
    RESEARCH_MODE = _env_bool("GOSHINSHO_RESEARCH_MODE", default=True)
    RESEARCH_MAX_SUB_QUERIES = int(_env("GOSHINSHO_RESEARCH_MAX_SUB_QUERIES") or 4)
    RESEARCH_CHUNKS_PER_QUERY = int(_env("GOSHINSHO_RESEARCH_CHUNKS_PER_QUERY") or 8)
    RESEARCH_MAX_MERGED_CHUNKS = int(_env("GOSHINSHO_RESEARCH_MAX_MERGED_CHUNKS") or 20)
    AWS_REGION = _env("AWS_REGION") or "us-east-1"
    AWS_ACCESS_KEY_ID = _env("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = _env("AWS_SECRET_ACCESS_KEY")
    SES_FROM_EMAIL = _env("SES_FROM_EMAIL")
    SES_CONTACT_TO_EMAIL = _env("SES_CONTACT_TO_EMAIL") or SES_FROM_EMAIL
    RESEND_API_KEY = _env("RESEND_API_KEY")
    RESEND_FROM_EMAIL = _env("RESEND_FROM_EMAIL") or "Goshinsho <noreply@goshinsho.com.br>"
    PRICE_MENSAL = "price_1TgCMzF2Js1cKxv5mwWP0nym"
    PRICE_ANUAL = "price_1TgCOQF2Js1cKxv5h3NyQQCp"
