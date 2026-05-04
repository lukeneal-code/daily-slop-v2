# Daily Slop v2 — Operational Runbook

This is the playbook for taking v2 from "code is green on main" to "live at https://dailyslop.co.uk". Everything before §6 is reversible; §6 changes DNS at the registrar and is the point of no return.

## 0. Prerequisites

- `gcloud` authenticated as an owner of project `daily-slop-v2`.
- Billing account `017077-74BDB0-80CDED` linked (already done by `bootstrap.sh`).
- API keys in hand: Anthropic, OpenAI, xAI.
- Access to the registrar holding `dailyslop.co.uk`.

## 1. Populate Secret Manager values

`bootstrap.sh` created **empty** secrets. Add the real values:

```sh
printf "%s" "<anthropic key>" | gcloud secrets versions add anthropic-api-key   --data-file=- --project=daily-slop-v2
printf "%s" "<openai key>"    | gcloud secrets versions add openai-api-key      --data-file=- --project=daily-slop-v2
printf "%s" "<xai key>"       | gcloud secrets versions add xai-api-key         --data-file=- --project=daily-slop-v2

openssl rand -base64 32 | gcloud secrets versions add langfuse-db-password     --data-file=- --project=daily-slop-v2
openssl rand -base64 32 | gcloud secrets versions add langfuse-nextauth-secret --data-file=- --project=daily-slop-v2
openssl rand -base64 32 | gcloud secrets versions add langfuse-salt            --data-file=- --project=daily-slop-v2
openssl rand -hex   32  | gcloud secrets versions add langfuse-encryption-key  --data-file=- --project=daily-slop-v2
```

## 2. Push the first API image

CI/CD will eventually do this on every merge to `main`, but for the first deploy you need the image to exist *before* `terraform apply` so the Cloud Run service can pull it.

```sh
gcloud auth configure-docker europe-west2-docker.pkg.dev --quiet --project=daily-slop-v2

# From the repo root:
docker build -t europe-west2-docker.pkg.dev/daily-slop-v2/app/api:bootstrap backend/
docker push europe-west2-docker.pkg.dev/daily-slop-v2/app/api:bootstrap
```

Then export the tag:

```sh
export TF_VAR_api_image_tag=bootstrap
```

## 3. First terraform apply

```sh
cd infra/terraform
terraform init -backend-config=envs/prod.backend.hcl
terraform apply -var-file=envs/prod.tfvars
```

This creates: VPC + private services access, Cloud SQL, Artifact Registry, GCS buckets, Cloud Run (api + langfuse), Cloud Scheduler, HTTPS load balancer with managed cert and Cloud CDN.

The first apply takes **~15 minutes** because:
- Cloud SQL provisioning is slow (~8 min).
- Managed SSL cert provisioning waits on the domain pointing at the LB IP — see §5.

Note the outputs:
- `lb_ip` → registrar A-record target.
- `api_service_url` → for ad-hoc curls.
- `scheduler_sa_email` → already wired into the api service's OIDC verifier.

## 4. Run the initial Alembic migration against Cloud SQL

Cloud Run doesn't auto-migrate; we run Alembic from a Cloud Build job, the api container, or your laptop via the auth proxy.

Easiest from your laptop:

```sh
gcloud sql connect slop-pg --user=slop --database=slop --project=daily-slop-v2
# Cancel out — we just wanted to verify connectivity.

cloud_sql_proxy -instances=daily-slop-v2:europe-west2:slop-pg=tcp:5433 &

cd backend
DATABASE_URL_SYNC="postgresql+psycopg://slop:<password>@127.0.0.1:5433/slop" \
  uv run alembic upgrade head
kill %1
```

The slop user password is in `terraform.tfstate` — fetch with `terraform output -raw cloudsql_slop_password` (or grep the state file). Alternatively wire a one-shot Cloud Run job to run `alembic upgrade head` on container start; left out of v0 for simplicity.

## 5. Bring the domain up

The managed SSL cert won't validate until the domain resolves to the LB IP.

1. **Lower the registrar TTL on `dailyslop.co.uk` to 300s 24h ahead of cutover.**
2. **Add an A record** pointing `dailyslop.co.uk` (and `www.dailyslop.co.uk`) at `terraform output -raw lb_ip`. Don't remove the v1 record yet — at this point you've got two A records, traffic is split. (Or use a temporary subdomain like `staging.dailyslop.co.uk` for soak testing — this is what the plan recommends.)
3. Wait up to 30 min for the managed cert to flip from `PROVISIONING` to `ACTIVE`:
   ```sh
   gcloud compute ssl-certificates describe slop-cert --project=daily-slop-v2 --format='value(managed.status)'
   ```

## 6. Verify before cutover

Run through this checklist before flipping the registrar:

```sh
# 1. API health
curl -fs https://staging.dailyslop.co.uk/healthz  # → {"status":"ok",...}

# 2. Trigger one full pipeline run via Cloud Scheduler manually
gcloud scheduler jobs run daily-slop-generate-prod --location=europe-west2 --project=daily-slop-v2
gcloud run services logs tail api --project=daily-slop-v2 --region=europe-west2

# 3. Confirm front page populated
curl -s https://staging.dailyslop.co.uk/api/articles | jq '.stories[].headline'

# 4. Confirm a section page populated
curl -s 'https://staging.dailyslop.co.uk/api/articles?section=politics' | jq '.articles[].headline'

# 5. Confirm an image renders
curl -fI https://staging.dailyslop.co.uk/images/2026-05-03/<slug>.png

# 6. Frontend
open https://staging.dailyslop.co.uk
# Eyeball: masthead, six-section nav, three front-page stories, ad slots in
# different positions on each page.

# 7. LangFuse trace shows up
gcloud run services proxy langfuse-web --port=8090 --project=daily-slop-v2 --region=europe-west2
# In another terminal: open http://localhost:8090 and verify the run trace.

# 8. Soak: leave it running for 3 daily Cloud Scheduler firings.
#    Spot-check the new articles each morning. Watch the LangFuse eval mean
#    against the calibration target from Phase 7.
```

## 7. Cutover

```sh
# At the registrar:
# 1. Remove the v1 A record (34.13.59.148).
# 2. Confirm dailyslop.co.uk resolves to the v2 LB IP.
# 3. Wait 5–10 min for caches to flush.

# Verify resolution
dig +short dailyslop.co.uk

# Stop (don't delete) the v1 VM — we keep it as a 14-day rollback.
gcloud --project the-daily-slop compute instances stop daily-slop --zone=europe-west2-a
```

## 8. Rollback (if needed within 14 days)

```sh
# Repoint the registrar A record back to 34.13.59.148.
gcloud --project the-daily-slop compute instances start daily-slop --zone=europe-west2-a
```

## 9. Decommission v1 (after the 14-day soak)

```sh
gcloud --project the-daily-slop compute instances delete daily-slop --zone=europe-west2-a --quiet
# Backup remains in gs://the-daily-slop-archive/ (versioned, 365d non-current retention).
# Keep the v1 project around at least until the next billing close.
```
