"""Concede plano premium temporário a e-mails específicos, com expiração automática.

Uso:
    python3 scripts/grant_temporary_premium.py --days 6 email1 email2 ...

Grava um registo em data/temporary_premium_grants.json com o plano anterior
de cada conta e a data de expiração -- scripts/revert_temporary_premium.py
(rodado por cron) usa esse registo para devolver a conta ao plano anterior
quando expirar, sem depender de nenhuma sessão futura lembrar de o fazer.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from goshinsho.supabase_client import get_supabase  # noqa: E402

GRANTS_PATH = PROJECT_ROOT / "data" / "temporary_premium_grants.json"


def _load_grants() -> list[dict]:
    if not GRANTS_PATH.exists():
        return []
    return json.loads(GRANTS_PATH.read_text(encoding="utf-8"))


def _save_grants(grants: list[dict]) -> None:
    GRANTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = GRANTS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(grants, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(GRANTS_PATH)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, required=True)
    parser.add_argument("--note", default="")
    parser.add_argument("emails", nargs="+")
    args = parser.parse_args()

    sb = get_supabase()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=args.days)
    grants = _load_grants()

    for email in args.emails:
        normalized = email.strip().lower()
        resp = sb.table("usuarios").select("id,email,plano").eq("email", normalized).limit(1).execute()
        if not resp.data:
            print(f"NOT_FOUND: {email}")
            continue
        row = resp.data[0]
        if row.get("plano") == "premium":
            print(f"SKIP (já premium): {email}")
            continue

        sb.table("usuarios").update({"plano": "premium"}).eq("id", row["id"]).execute()
        grants.append(
            {
                "email": row["email"],
                "user_id": row["id"],
                "previous_plano": row.get("plano") or "gratis",
                "granted_at": now.isoformat(),
                "expires_at": expires_at.isoformat(),
                "status": "active",
                "reverted_at": None,
                "note": args.note,
            }
        )
        print(f"GRANTED: {email} (premium até {expires_at.date().isoformat()})")

    _save_grants(grants)


if __name__ == "__main__":
    main()
