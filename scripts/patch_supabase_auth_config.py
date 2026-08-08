#!/usr/bin/env python3
"""Aplica site_url e redirect URLs no Auth do projecto Supabase (Management API)."""

from __future__ import annotations

import os
import sys

import requests
from dotenv import load_dotenv

PROJECT_REF = "syykpsnalrfgtdanurwo"
SITE_URL = "https://goshinsho.com.br"
REDIRECT_URLS = [
    "https://goshinsho.com.br/app",
    "https://goshinsho.com.br/app?panel=login",
    "https://goshinsho.com.br/app?panel=login&confirmed=1",
]


def main() -> int:
    load_dotenv("/var/www/goshinsho/.env")
    token = os.environ.get("SUPABASE_ACCESS_TOKEN")
    if not token:
        print("Defina SUPABASE_ACCESS_TOKEN no .env (https://supabase.com/dashboard/account/tokens)", file=sys.stderr)
        return 1

    payload = {
        "site_url": SITE_URL,
        "uri_allow_list": ",".join(REDIRECT_URLS),
        "external_email_enabled": True,
    }
    response = requests.patch(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/config/auth",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )
    print("status:", response.status_code)
    print(response.text[:2000])
    return 0 if response.status_code < 400 else 1


if __name__ == "__main__":
    raise SystemExit(main())
