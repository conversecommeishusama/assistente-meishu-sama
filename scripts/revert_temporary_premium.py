"""Reverte concessões temporárias de premium expiradas (ver grant_temporary_premium.py).

Pensado para rodar via cron diário: idempotente, só age sobre registos
"active" cujo expires_at já passou, e só reverte se a conta ainda estiver
em "premium" (não pisa em upgrade real feito manualmente nesse meio-tempo).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from goshinsho.supabase_client import get_supabase  # noqa: E402

GRANTS_PATH = PROJECT_ROOT / "data" / "temporary_premium_grants.json"


def main() -> None:
    if not GRANTS_PATH.exists():
        return
    grants = json.loads(GRANTS_PATH.read_text(encoding="utf-8"))
    now = datetime.now(timezone.utc)
    sb = get_supabase()
    changed = False

    for grant in grants:
        if grant.get("status") != "active":
            continue
        expires_at = datetime.fromisoformat(grant["expires_at"])
        if now < expires_at:
            continue

        resp = sb.table("usuarios").select("plano").eq("id", grant["user_id"]).limit(1).execute()
        current_plano = resp.data[0].get("plano") if resp.data else None
        if current_plano == "premium":
            sb.table("usuarios").update({"plano": grant["previous_plano"]}).eq("id", grant["user_id"]).execute()
            print(f"REVERTED: {grant['email']} -> {grant['previous_plano']}")
        else:
            print(f"SKIP (plano mudou manualmente): {grant['email']} está '{current_plano}'")

        grant["status"] = "reverted"
        grant["reverted_at"] = now.isoformat()
        changed = True

    if changed:
        tmp = GRANTS_PATH.with_suffix(".tmp")
        tmp.write_text(json.dumps(grants, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(GRANTS_PATH)


if __name__ == "__main__":
    main()
