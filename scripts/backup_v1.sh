#!/usr/bin/env bash
# Phase 1 backup of The Daily Slop v1 — DB + images.
# Pulls from the live v1 VM (`daily-slop` in project `the-daily-slop`, zone europe-west2-a),
# writes a local working copy and a checksummed tarball, then mirrors to a versioned
# GCS bucket in the v1 project. Idempotent on bucket creation; each run produces a
# uniquely-timestamped tarball in the bucket.
set -euo pipefail

V1_PROJECT="${V1_PROJECT:-the-daily-slop}"
V1_INSTANCE="${V1_INSTANCE:-daily-slop}"
V1_ZONE="${V1_ZONE:-europe-west2-a}"
V1_REMOTE_DB_DIR="${V1_REMOTE_DB_DIR:-/opt/the-daily-slop/backend/data}"
V1_REMOTE_IMAGES_DIR="${V1_REMOTE_IMAGES_DIR:-/opt/the-daily-slop/backend/public/images}"

ARCHIVE_BUCKET="${ARCHIVE_BUCKET:-the-daily-slop-archive}"
ARCHIVE_REGION="${ARCHIVE_REGION:-europe-west2}"

TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_ROOT="${BACKUP_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/backups/v1}"
WORK_DIR="${BACKUP_ROOT}/${TS}"
DB_DIR="${WORK_DIR}/db"
IMAGES_DIR="${WORK_DIR}/images"
CSV_DIR="${DB_DIR}/csv"
TARBALL="${BACKUP_ROOT}/v1-backup-${TS}.tar.gz"
SHA256_FILE="${TARBALL}.sha256"

log() { printf '[backup_v1] %s\n' "$*"; }
die() { printf '[backup_v1][ERROR] %s\n' "$*" >&2; exit 1; }

require_cmd() { command -v "$1" >/dev/null 2>&1 || die "missing required command: $1"; }

require_cmd gcloud
require_cmd sqlite3
require_cmd tar
require_cmd shasum

mkdir -p "${DB_DIR}" "${IMAGES_DIR}" "${CSV_DIR}"

log "VM: ${V1_INSTANCE} (project=${V1_PROJECT}, zone=${V1_ZONE})"
log "Remote DB dir: ${V1_REMOTE_DB_DIR}"
log "Remote images dir: ${V1_REMOTE_IMAGES_DIR}"
log "Local work dir: ${WORK_DIR}"

# 1) SCP DB + images. We use sudo on the remote side via gcloud ssh to copy into /tmp first
#    because the SQLite file and image dirs may be owned by a different user than the SSH login.
TMP_REMOTE="/tmp/v1-backup-${TS}"
log "Staging remote files into ${TMP_REMOTE} on the VM..."
gcloud --project "${V1_PROJECT}" compute ssh "${V1_INSTANCE}" \
  --zone "${V1_ZONE}" --command "
    set -euo pipefail
    sudo mkdir -p '${TMP_REMOTE}'
    sudo cp -a '${V1_REMOTE_DB_DIR}/.' '${TMP_REMOTE}/db/'
    sudo cp -a '${V1_REMOTE_IMAGES_DIR}/.' '${TMP_REMOTE}/images/'
    sudo chown -R \$(id -un):\$(id -gn) '${TMP_REMOTE}'
    du -sh '${TMP_REMOTE}'/* || true
  "

log "Copying DB to ${DB_DIR}..."
gcloud --project "${V1_PROJECT}" compute scp --recurse --zone "${V1_ZONE}" \
  "${V1_INSTANCE}:${TMP_REMOTE}/db" "${WORK_DIR}/"

log "Copying images to ${IMAGES_DIR} (this is ~500MB, may take a few minutes)..."
gcloud --project "${V1_PROJECT}" compute scp --recurse --zone "${V1_ZONE}" \
  "${V1_INSTANCE}:${TMP_REMOTE}/images" "${WORK_DIR}/"

log "Cleaning up remote staging dir..."
gcloud --project "${V1_PROJECT}" compute ssh "${V1_INSTANCE}" \
  --zone "${V1_ZONE}" --command "sudo rm -rf '${TMP_REMOTE}'" >/dev/null

# 2) Integrity check on the SQLite file.
DB_FILE="$(find "${DB_DIR}" -maxdepth 2 -name '*.db' | head -n1)"
[[ -n "${DB_FILE}" ]] || die "no .db file found under ${DB_DIR}"
log "SQLite file: ${DB_FILE}"
log "Running PRAGMA integrity_check..."
RESULT="$(sqlite3 "${DB_FILE}" 'PRAGMA integrity_check;')"
if [[ "${RESULT}" != "ok" ]]; then
  die "integrity_check failed: ${RESULT}"
fi
log "integrity_check = ok"

# 3) CSV dumps for human-readable safety net.
log "Dumping CSVs..."
sqlite3 -header -csv "${DB_FILE}" 'SELECT * FROM stories;' > "${CSV_DIR}/stories.csv"
sqlite3 -header -csv "${DB_FILE}" 'SELECT * FROM source_articles;' > "${CSV_DIR}/source_articles.csv" || \
  log "(source_articles dump skipped — table may not exist)"

# 4) Tarball + sha256.
log "Creating tarball ${TARBALL}..."
tar -czf "${TARBALL}" -C "${WORK_DIR}" db images
shasum -a 256 "${TARBALL}" | tee "${SHA256_FILE}"

LOCAL_SIZE="$(du -h "${TARBALL}" | awk '{print $1}')"
log "Tarball size: ${LOCAL_SIZE}"

# 5) Ensure the archive bucket exists in the v1 project.
GS_URL="gs://${ARCHIVE_BUCKET}"
if gcloud --project "${V1_PROJECT}" storage buckets describe "${GS_URL}" >/dev/null 2>&1; then
  log "Archive bucket already exists: ${GS_URL}"
else
  log "Creating archive bucket ${GS_URL} in ${ARCHIVE_REGION}..."
  gcloud --project "${V1_PROJECT}" storage buckets create "${GS_URL}" \
    --location="${ARCHIVE_REGION}" \
    --uniform-bucket-level-access \
    --public-access-prevention
  log "Enabling versioning..."
  gcloud --project "${V1_PROJECT}" storage buckets update "${GS_URL}" --versioning
  log "Setting noncurrent-version lifecycle (delete after 365 days)..."
  LIFECYCLE_TMP="$(mktemp)"
  cat > "${LIFECYCLE_TMP}" <<'JSON'
{
  "lifecycle": {
    "rule": [
      {
        "action": {"type": "Delete"},
        "condition": {"daysSinceNoncurrentTime": 365}
      }
    ]
  }
}
JSON
  gcloud --project "${V1_PROJECT}" storage buckets update "${GS_URL}" \
    --lifecycle-file="${LIFECYCLE_TMP}"
  rm -f "${LIFECYCLE_TMP}"
fi

# 6) Upload tarball + sha256.
log "Uploading tarball + sha256 to ${GS_URL}/..."
gcloud --project "${V1_PROJECT}" storage cp \
  "${TARBALL}" "${SHA256_FILE}" "${GS_URL}/"

# 7) Summary.
log "DONE."
log "  Local tarball : ${TARBALL}"
log "  sha256        : $(awk '{print $1}' "${SHA256_FILE}")"
log "  GCS object    : ${GS_URL}/$(basename "${TARBALL}")"
log "  Working tree  : ${WORK_DIR}"
