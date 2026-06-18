#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="/var/www/goshinsho"
PROJECT_PARENT="/var/www"
PROJECT_NAME="goshinsho"
BACKUP_ROOT="/var/backups/goshinsho"
BACKUP_DIR="${BACKUP_ROOT}/daily"
RETENTION_DAYS="${GOSHINSHO_BACKUP_RETENTION_DAYS:-14}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
ARCHIVE="${BACKUP_DIR}/goshinsho_${STAMP}.tar.gz"
MANIFEST_DIR="$(mktemp -d)"
MANIFEST="${MANIFEST_DIR}/MANIFEST.txt"
LOG_FILE="${BACKUP_ROOT}/backup.log"

cleanup() {
    rm -rf "${MANIFEST_DIR}"
}
trap cleanup EXIT

mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_ROOT}" "${BACKUP_DIR}"

{
    echo "Goshinsho backup manifest"
    echo "created_at_utc=${STAMP}"
    echo "project_root=${PROJECT_ROOT}"
    echo "archive=${ARCHIVE}"
    echo
    echo "disk_usage_project:"
    du -sh "${PROJECT_ROOT}" || true
    echo
    echo "git_status_short:"
    git -C "${PROJECT_ROOT}" status --short || true
    echo
    echo "git_head:"
    git -C "${PROJECT_ROOT}" log -1 --format='%H %an <%ae> %s' || true
    echo
    echo "important_artifacts:"
    ls -lh "${PROJECT_ROOT}"/*.pkl "${PROJECT_ROOT}"/*.faiss 2>/dev/null || true
    ls -lh "${PROJECT_ROOT}/experiments" 2>/dev/null || true
    ls -lh "${PROJECT_ROOT}/experiments/uploaded_indexes" 2>/dev/null || true
} > "${MANIFEST}"

tar \
    --create \
    --gzip \
    --file "${ARCHIVE}" \
    --warning=no-file-changed \
    --exclude="${PROJECT_NAME}/venv" \
    --exclude="${PROJECT_NAME}/.venv" \
    --exclude="${PROJECT_NAME}/**/__pycache__" \
    --exclude="${PROJECT_NAME}/.pytest_cache" \
    --exclude="${PROJECT_NAME}/.cleanup_quarantine" \
    --exclude="${PROJECT_NAME}/restored_from_pyc" \
    --exclude="${PROJECT_NAME}/node_modules" \
    --exclude="${PROJECT_NAME}/android-app/.gradle" \
    --exclude="${PROJECT_NAME}/android-app/app/build" \
    --exclude="${PROJECT_NAME}/admin-android-app/.gradle" \
    --exclude="${PROJECT_NAME}/admin-android-app/app/build" \
    --exclude="${PROJECT_NAME}/data/clean_corpus" \
    --exclude="${PROJECT_NAME}/experiments/rebuilt_large_indexes" \
    --exclude="${PROJECT_NAME}/experiments/uploaded_indexes_backup_*" \
    --exclude="${PROJECT_NAME}/exports" \
    --exclude="${PROJECT_NAME}/logs/*.log" \
    --exclude="${PROJECT_NAME}/logs/*.jsonl" \
    --exclude="${PROJECT_NAME}/logs/*.tmp" \
    --exclude="${PROJECT_NAME}/logo.before-*.png" \
    --exclude="${PROJECT_NAME}/logo.original.png" \
    -C "${PROJECT_PARENT}" "${PROJECT_NAME}" \
    -C "${MANIFEST_DIR}" "MANIFEST.txt"

chmod 600 "${ARCHIVE}"
sha256sum "${ARCHIVE}" > "${ARCHIVE}.sha256"
chmod 600 "${ARCHIVE}.sha256"

ln -sfn "${ARCHIVE}" "${BACKUP_ROOT}/latest.tar.gz"
ln -sfn "${ARCHIVE}.sha256" "${BACKUP_ROOT}/latest.tar.gz.sha256"

find "${BACKUP_DIR}" -type f -name 'goshinsho_*.tar.gz' -mtime "+${RETENTION_DAYS}" -delete
find "${BACKUP_DIR}" -type f -name 'goshinsho_*.tar.gz.sha256' -mtime "+${RETENTION_DAYS}" -delete

{
    echo "${STAMP} created ${ARCHIVE}"
    ls -lh "${ARCHIVE}" "${ARCHIVE}.sha256"
} >> "${LOG_FILE}"

echo "${ARCHIVE}"
