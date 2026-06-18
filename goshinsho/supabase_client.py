from urllib.parse import urlparse

from supabase import Client, create_client

from .config import Config


def _normalize_supabase_url(url):
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("SUPABASE_URL deve estar no formato https://seu-projeto.supabase.co.")

    hostname = parsed.hostname or ""
    if "seu-projeto" in hostname or not hostname.endswith(".supabase.co"):
        raise RuntimeError("SUPABASE_URL parece inválida. Copie a Project URL do Supabase em Project Settings > API.")

    if parsed.path and parsed.path != "/":
        raise RuntimeError("SUPABASE_URL não deve ter caminho extra. Use apenas https://xxxxx.supabase.co, sem /auth/v1 ou outras rotas.")

    return f"{parsed.scheme}://{parsed.netloc}"


def get_supabase() -> Client:
    if not Config.SUPABASE_URL or not Config.SUPABASE_KEY:
        raise RuntimeError("Configure SUPABASE_URL e SUPABASE_KEY ou SUPABASE_ANON_KEY no .env.")

    supabase_url = _normalize_supabase_url(Config.SUPABASE_URL)
    return create_client(supabase_url, Config.SUPABASE_KEY)
