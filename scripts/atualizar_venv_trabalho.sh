#!/usr/bin/env bash
# =============================================================================
# atualizar_venv_trabalho.sh — Atualiza as libs com CVE do .venv (scripts de
# trabalho em lote), na MESMA receita validada no venv de produção (2026-10-13).
#
# RODE APENAS QUANDO NENHUM JOB ESTIVER USANDO O .venv.
# Faz snapshot antes (reversível) e roda a auditoria no final.
# =============================================================================
set -euo pipefail
VENV=/var/www/goshinsho/.venv
PIP="$VENV/bin/pip"

echo "=== Verificando se há job usando o .venv ==="
if pgrep -f "$VENV/bin" >/dev/null 2>&1; then
  echo "ABORTADO: ha um processo usando o .venv. Finalize-o primeiro:"
  pgrep -af "$VENV/bin"
  exit 1
fi
echo "  ocioso. Prosseguindo."

echo "=== Snapshot (reversao) ==="
"$PIP" freeze > "/root/requirements.dotvenv.$(date +%Y%m%d_%H%M%S).txt"
ls -t /root/requirements.dotvenv.*.txt | head -1

echo "=== Atualizando (mesma receita da producao: 31->0 CVEs) ==="
"$PIP" install --quiet --upgrade \
  pyjwt werkzeug urllib3 h2 hpack anyio edge-tts \
  "multidict==6.9.1" \
  "torch==2.13.0" "sentence-transformers==5.6.0" \
  "cryptography==50.0.0" "fsspec==2026.6.0" "setuptools>=83"

echo "=== pip check ==="
"$PIP" check || true

echo "=== Auditoria final ==="
python3 -m venv /tmp/audit_dv >/dev/null 2>&1 || true
/tmp/audit_dv/bin/pip install -q --upgrade pip pip-audit >/dev/null 2>&1 || true
"$PIP" freeze > /tmp/dv.txt
/tmp/audit_dv/bin/pip-audit -r /tmp/dv.txt --progress-spinner off 2>&1 | tail -3

echo
echo "=== Reversao, se necessario ==="
echo "  $PIP install -r \$(ls -t /root/requirements.dotvenv.*.txt | head -1)"
