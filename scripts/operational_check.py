#!/usr/bin/env python3
import argparse
import json
import os
import pickle
import ssl
import sys
import tarfile
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = PROJECT_ROOT / "experiments" / "uploaded_indexes"
BACKUP_LATEST = Path("/var/backups/goshinsho/latest.tar.gz")
load_dotenv(PROJECT_ROOT / ".env")


def result(name, ok, detail=""):
    return {"name": name, "ok": bool(ok), "detail": detail}


def http_head(url, expected_statuses=(200,), timeout=20):
    request = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl.create_default_context()) as response:
            status = response.status
            return status in expected_statuses, f"HTTP {status}"
    except urllib.error.HTTPError as exc:
        return exc.code in expected_statuses, f"HTTP {exc.code}"
    except Exception as exc:
        return False, str(exc)


def check_env():
    required = ["FLASK_SECRET_KEY", "SUPABASE_URL", "DEEPSEEK_API_KEY", "STRIPE_SECRET_KEY"]
    checks = []
    for name in required:
        value = os.environ.get(name)
        if name == "SUPABASE_URL":
            ok = bool(value and value.startswith("https://") and ".supabase.co" in value)
        elif name == "FLASK_SECRET_KEY":
            ok = bool(value and value != "dev-change-me" and len(value) >= 16)
        else:
            ok = bool(value)
        checks.append(result(f"env:{name}", ok, "configured" if ok else "missing_or_invalid"))
    supabase_key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_ANON_KEY")
    checks.append(result("env:SUPABASE_KEY", bool(supabase_key), "configured" if supabase_key else "missing"))
    return checks


def check_indexes():
    required = {
        "pt": ("chunks_pt.pkl", "metadados_pt.pkl", "indice_pt.faiss"),
        "jp": ("chunks_jp.pkl", "metadados_jp.pkl", "indice_jp.faiss"),
    }
    checks = []
    report_path = INDEX_DIR / "build_report.json"
    checks.append(result("indexes:build_report", report_path.exists(), str(report_path)))
    report = {}
    if report_path.exists():
        try:
            report = json.loads(report_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            checks.append(result("indexes:build_report_json", False, str(exc)))
    for lang, files in required.items():
        missing = [name for name in files if not (INDEX_DIR / name).exists()]
        checks.append(result(f"indexes:{lang}:files", not missing, "missing=" + ",".join(missing) if missing else "present"))
        chunks_path = INDEX_DIR / files[0]
        metas_path = INDEX_DIR / files[1]
        if chunks_path.exists() and metas_path.exists():
            try:
                chunks = pickle.loads(chunks_path.read_bytes())
                metas = pickle.loads(metas_path.read_bytes())
                checks.append(result(f"indexes:{lang}:pickle_counts", len(chunks) == len(metas), f"chunks={len(chunks)} metas={len(metas)}"))
            except Exception as exc:
                checks.append(result(f"indexes:{lang}:pickle_counts", False, str(exc)))
    if report.get("indexes"):
        detail = ", ".join(f"{item.get('lang')}={item.get('chunks')}" for item in report["indexes"])
        checks.append(result("indexes:reported_chunks", True, detail))
    return checks


def check_backup():
    checks = [result("backup:latest_exists", BACKUP_LATEST.exists(), str(BACKUP_LATEST))]
    if not BACKUP_LATEST.exists():
        return checks
    forbidden_prefixes = (
        "goshinsho/venv/",
        "goshinsho/data/clean_corpus/",
        "goshinsho/exports/",
        "goshinsho/android-app/",
        "goshinsho/admin-android-app/",
    )
    try:
        with tarfile.open(BACKUP_LATEST, "r:gz") as archive:
            names = archive.getnames()
        checks.append(result("backup:readable", True, f"files={len(names)}"))
        checks.append(result("backup:manifest", "MANIFEST.txt" in names, "MANIFEST.txt"))
        forbidden = [name for name in names if name.startswith(forbidden_prefixes)]
        checks.append(result("backup:exclusions", not forbidden, "forbidden=" + ",".join(forbidden[:5]) if forbidden else "ok"))
        required = [
            "goshinsho/app.py",
            "goshinsho/goshinsho/routes.py",
            "goshinsho/data/publication_sources/summary.json",
            "goshinsho/experiments/uploaded_indexes/build_report.json",
        ]
        missing = [name for name in required if name not in names]
        checks.append(result("backup:required_files", not missing, "missing=" + ",".join(missing) if missing else "present"))
    except Exception as exc:
        checks.append(result("backup:readable", False, str(exc)))
    return checks


def check_http(base_url):
    base = base_url.rstrip("/")
    checks = []
    for path, statuses in (
        ("/app", (200,)),
        ("/app-pt", (200,)),
        ("/health", (200,)),
        ("/logo.png", (200,)),
        ("/downloads/goshinsho.apk", (200,)),
        ("/downloads/goshinsho-admin.apk", (200, 302)),
    ):
        ok, detail = http_head(base + path, statuses)
        checks.append(result(f"http:{path}", ok, detail))
    return checks


def main():
    parser = argparse.ArgumentParser(description="Run safe operational checks for Goshinsho.")
    parser.add_argument("--base-url", default="https://goshinsho.com.br", help="Public base URL to check.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    args = parser.parse_args()

    checks = []
    checks.extend(check_env())
    checks.extend(check_indexes())
    checks.extend(check_backup())
    checks.extend(check_http(args.base_url))

    ok = all(check["ok"] for check in checks)
    payload = {"status": "ok" if ok else "failed", "checks": checks}
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for check in checks:
            marker = "OK" if check["ok"] else "FAIL"
            print(f"[{marker}] {check['name']} - {check['detail']}")
        print(f"status={payload['status']}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
