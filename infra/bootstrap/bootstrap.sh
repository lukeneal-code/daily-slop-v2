#!/usr/bin/env bash
# One-shot bootstrap for the v2 GCP project.
#   1. Creates the GCP project (if it doesn't exist) and links it to the configured billing account.
#   2. Enables the APIs that Terraform itself needs to bootstrap.
#   3. Creates the GCS bucket that backs the Terraform remote state (versioned).
#   4. Creates *empty* secrets in Secret Manager. Prints the `gcloud` command lines
#      to add real values — the script itself never reads or writes secret material.
#   5. Creates a Workload Identity Pool + provider for GitHub Actions deploys.
#   6. Grants gha-deploy the curated set of project roles needed to run the
#      deploy workflow end to end (build/push, terraform apply, frontend sync).
#
# This script is idempotent. Re-run safely.
set -euo pipefail

PROJECT_ID="${PROJECT_ID:-daily-slop-v2}"
PROJECT_NAME="${PROJECT_NAME:-Daily Slop v2}"
REGION="${REGION:-europe-west2}"
TFSTATE_BUCKET="${TFSTATE_BUCKET:-${PROJECT_ID}-tfstate}"
GH_REPO="${GH_REPO:-lukeneal-code/daily-slop-v2}"

# Comma-separated billing account ID, or empty to skip linking. Fetch yours with:
#   gcloud billing accounts list --format='value(name)'
BILLING_ACCOUNT="${BILLING_ACCOUNT:-}"

SECRETS=(
  anthropic-api-key
  openai-api-key
  xai-api-key
  langfuse-db-password
  langfuse-nextauth-secret
  langfuse-salt
  langfuse-encryption-key
  linkedin-client-id
  linkedin-client-secret
  linkedin-access-token
  linkedin-refresh-token
)

REQUIRED_APIS=(
  cloudresourcemanager.googleapis.com
  iam.googleapis.com
  iamcredentials.googleapis.com
  secretmanager.googleapis.com
  serviceusage.googleapis.com
  storage.googleapis.com
)

log() { printf '[bootstrap] %s\n' "$*"; }

# 1) Project.
if gcloud projects describe "${PROJECT_ID}" >/dev/null 2>&1; then
  log "Project ${PROJECT_ID} exists."
else
  log "Creating project ${PROJECT_ID}..."
  gcloud projects create "${PROJECT_ID}" --name="${PROJECT_NAME}"
fi

if [[ -n "${BILLING_ACCOUNT}" ]]; then
  log "Linking billing account ${BILLING_ACCOUNT}..."
  gcloud --quiet billing projects link "${PROJECT_ID}" --billing-account="${BILLING_ACCOUNT}"
else
  log "BILLING_ACCOUNT not set — skipping billing link. Many resources will fail until billing is attached."
fi

gcloud config set project "${PROJECT_ID}" >/dev/null

# 2) APIs.
log "Enabling required APIs..."
gcloud services enable "${REQUIRED_APIS[@]}"

# 3) tfstate bucket.
GS_URL="gs://${TFSTATE_BUCKET}"
if gcloud storage buckets describe "${GS_URL}" >/dev/null 2>&1; then
  log "tfstate bucket already exists: ${GS_URL}"
else
  log "Creating tfstate bucket ${GS_URL} in ${REGION}..."
  gcloud storage buckets create "${GS_URL}" \
    --location="${REGION}" \
    --uniform-bucket-level-access \
    --public-access-prevention
fi
gcloud storage buckets update "${GS_URL}" --versioning >/dev/null

# 4) Empty secrets.
log "Ensuring empty secrets exist..."
for s in "${SECRETS[@]}"; do
  if gcloud secrets describe "${s}" >/dev/null 2>&1; then
    log "  - ${s} (exists)"
  else
    gcloud secrets create "${s}" --replication-policy="automatic" >/dev/null
    log "  - ${s} (created, EMPTY)"
  fi
done

cat <<EOF

──────────────────────────────────────────────────────────────────────
NEXT STEP — populate secret values manually:

  # Anthropic (Nigel)
  printf "%s" "<anthropic key>" | gcloud secrets versions add anthropic-api-key --data-file=-

  # OpenAI (Elle, image gen)
  printf "%s" "<openai key>" | gcloud secrets versions add openai-api-key --data-file=-

  # xAI (Steve)
  printf "%s" "<xai key>" | gcloud secrets versions add xai-api-key --data-file=-

  # LangFuse (use openssl rand)
  openssl rand -base64 32 | gcloud secrets versions add langfuse-db-password --data-file=-
  openssl rand -base64 32 | gcloud secrets versions add langfuse-nextauth-secret --data-file=-
  openssl rand -base64 32 | gcloud secrets versions add langfuse-salt --data-file=-
  openssl rand -hex   32  | gcloud secrets versions add langfuse-encryption-key --data-file=-

  # LinkedIn — run backend/scripts/linkedin_oauth.py to populate all four:
  #   LINKEDIN_CLIENT_ID=… LINKEDIN_CLIENT_SECRET=… GCP_PROJECT_ID=${PROJECT_ID} \\
  #     uv run python -m scripts.linkedin_oauth

──────────────────────────────────────────────────────────────────────

EOF

# 5) GitHub Workload Identity Federation.
log "Setting up GitHub WIF pool..."
POOL_ID="github-pool"
PROVIDER_ID="github-provider"

if ! gcloud iam workload-identity-pools describe "${POOL_ID}" --location=global >/dev/null 2>&1; then
  gcloud iam workload-identity-pools create "${POOL_ID}" \
    --location=global --display-name="GitHub Actions"
  log "  - pool created"
else
  log "  - pool exists"
fi

POOL_NAME="$(gcloud iam workload-identity-pools describe "${POOL_ID}" --location=global --format='value(name)')"

if ! gcloud iam workload-identity-pools providers describe "${PROVIDER_ID}" \
    --location=global --workload-identity-pool="${POOL_ID}" >/dev/null 2>&1; then
  gcloud iam workload-identity-pools providers create-oidc "${PROVIDER_ID}" \
    --location=global \
    --workload-identity-pool="${POOL_ID}" \
    --display-name="GitHub OIDC" \
    --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository" \
    --attribute-condition="assertion.repository=='${GH_REPO}'" \
    --issuer-uri="https://token.actions.githubusercontent.com"
  log "  - provider created"
else
  log "  - provider exists"
fi

PROVIDER_NAME="$(gcloud iam workload-identity-pools providers describe "${PROVIDER_ID}" \
  --location=global --workload-identity-pool="${POOL_ID}" --format='value(name)')"

# Service accounts for GHA.
for sa in gha-ci gha-deploy; do
  if ! gcloud iam service-accounts describe "${sa}@${PROJECT_ID}.iam.gserviceaccount.com" >/dev/null 2>&1; then
    gcloud iam service-accounts create "${sa}" --display-name="GitHub Actions: ${sa}"
    log "  - SA ${sa} created"
  fi
done

# Bind WIF principal to SAs.
for sa in gha-ci gha-deploy; do
  gcloud iam service-accounts add-iam-policy-binding \
    "${sa}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/${POOL_NAME}/attribute.repository/${GH_REPO}" >/dev/null
done

# Project roles for gha-deploy. Curated to what the deploy workflow actually
# does: push images, run terraform apply (Cloud Run, Cloud SQL, networking,
# LB/CDN, secrets, scheduler, IAM), sync the frontend bucket, invalidate CDN.
log "Granting project roles to gha-deploy..."
DEPLOY_MEMBER="serviceAccount:gha-deploy@${PROJECT_ID}.iam.gserviceaccount.com"
for ROLE in \
  roles/artifactregistry.writer \
  roles/storage.admin \
  roles/run.admin \
  roles/iam.serviceAccountUser \
  roles/iam.serviceAccountAdmin \
  roles/compute.loadBalancerAdmin \
  roles/compute.networkAdmin \
  roles/secretmanager.admin \
  roles/cloudsql.admin \
  roles/servicenetworking.networksAdmin \
  roles/vpcaccess.admin \
  roles/cloudscheduler.admin \
  roles/serviceusage.serviceUsageAdmin; do
  gcloud projects add-iam-policy-binding "${PROJECT_ID}" \
    --member="${DEPLOY_MEMBER}" \
    --role="${ROLE}" \
    --condition=None \
    --quiet >/dev/null
done

cat <<EOF

──────────────────────────────────────────────────────────────────────
GitHub repo secrets to set (Settings → Secrets and variables → Actions):

  GCP_WIF_PROVIDER  = ${PROVIDER_NAME}
  GCP_DEPLOY_SA     = gha-deploy@${PROJECT_ID}.iam.gserviceaccount.com

Terraform backend init:

  cd infra/terraform
  terraform init -backend-config=envs/prod.backend.hcl

──────────────────────────────────────────────────────────────────────

EOF

log "DONE."
