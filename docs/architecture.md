# Daily Slop v2 — Architecture

```
                                  ┌──────────────────────┐
                Cloud Scheduler ──┤ /admin/generate (OIDC)│
                    06:00 UK      └──────────┬───────────┘
                                             │
                                             ▼
   ┌────────────────────────────  Cloud Run: api  ────────────────────────────┐
   │                                                                          │
   │   FastAPI                                                                │
   │   ├── /healthz                                                           │
   │   ├── /api/{sections, articles, dates}                                   │
   │   └── /admin/generate                                                    │
   │            │                                                             │
   │            ▼                                                             │
   │   pipeline/daily.py                                                      │
   │   ├── scraping/rss.py     ── upsert source_articles                      │
   │   ├── for each section:                                                  │
   │   │     candidates = select_candidates(...)                              │
   │   │     for each candidate (asyncio.gather):                             │
   │   │           graph.ainvoke(state)                                       │
   │   │              ┌──────────────────┐                                    │
   │   │              │   write   ───►   │       Anthropic / xAI              │
   │   │              │     │            │                                    │
   │   │              │   edit  ───►     │       OpenAI                       │
   │   │              │   ┌──┴────┐      │                                    │
   │   │              │  approve  revise │                                    │
   │   │              │     │       │    │                                    │
   │   │              │   image_gen │    │       OpenAI / DALL-E              │
   │   │              │     │       │    │                                    │
   │   │              │   END    pushback│                                    │
   │   │              └──────────────────┘                                    │
   │   ├── front_page.select_top3                                             │
   │   └── persist articles + image_assets + agent_runs + agent_steps         │
   │                                                                          │
   └──────────────────────────┬───────────────────────────────────────────────┘
                              │
              ┌───────────────┴────────────────┐
              ▼                                ▼
    Cloud SQL Postgres 16            GCS daily-slop-v2-images-prod
    ├── slop (app)                   ├── 2026-05-03/<slug>.png ──┐
    └── langfuse                                                  │
                              ┌───────────────────────────────────┘
                              │
                              ▼
   ┌─────────────────  HTTPS LB + Cloud CDN  ─────────────────┐
   │  /api/*, /admin/*, /healthz   →  Cloud Run: api          │
   │  /images/*                    →  GCS images (immutable)  │
   │  default (/, /article/...)    →  GCS frontend (SPA)      │
   └──────────────────────────────────────────────────────────┘
                              │
                              ▼
                     dailyslop.co.uk
```

## Service-by-service notes

### Cloud Run: api
- Image: `europe-west2-docker.pkg.dev/daily-slop-v2/app/api:<sha>`
- Min instances 0, max 4. Cold starts are acceptable because the public path is mostly served from CDN.
- Reaches Cloud SQL via the serverless VPC connector + private IP (no public Postgres exposure).
- Auth on `/admin/generate` is OIDC: only the Cloud Scheduler SA can invoke. Local mode swaps in a static dev token.

### Cloud Run: langfuse-web
- Image: `langfuse/langfuse:3` (vendored).
- Same Cloud SQL instance, separate `langfuse` DB.
- Public ingress disabled; access via `gcloud run services proxy langfuse-web` for the operator only.

### Cloud SQL
- Single `db-f1-micro` Postgres 16 instance — adequate for the workload (≤ 18 articles/day, ~50 LangFuse spans/day).
- Two databases: `slop`, `langfuse`. App and observability share an instance to halve cost; PITR backups + pg_dump make a future split a one-hour migration.
- Private IP only.

### GCS
- `daily-slop-v2-images-prod` — uniform IAM, public-read, `Cache-Control: public, max-age=31536000, immutable`. Behind Cloud CDN at `/images/*`.
- `daily-slop-v2-frontend-prod` — same config, serves the React build at `/`.
- `daily-slop-v2-tfstate` — Terraform remote state, versioned.

### Load balancer + CDN
- Single global external HTTPS LB with a managed SSL cert for `dailyslop.co.uk`.
- URL-map routes by path:
  - `/api/*`, `/admin/*`, `/healthz` → api Cloud Run via serverless NEG.
  - `/images/*` → images backend bucket (CDN, 1y immutable).
  - default → frontend backend bucket (CDN, 1h with revalidation).
- HTTP → HTTPS redirect on port 80.

### Cloud Scheduler
- Single job `daily-slop-generate-prod`, cron `0 6 * * *` Europe/London.
- HTTP target POSTs to `/admin/generate` with an OIDC token; audience = the api service URL.

### Secrets
- All API keys and LangFuse runtime secrets live in Secret Manager. Terraform reads them via `data` blocks; key material never enters tfstate.

### Networking
- Custom VPC `slop-vpc` with private services access for Cloud SQL.
- Serverless VPC connector `slop-vpc-conn` lets Cloud Run reach private-IP Cloud SQL.

### Observability
- LangFuse trace per `run_id`; one observation per article; one span per LangGraph node.
- Durable `agent_runs` / `agent_steps` rows in Postgres double as a SQL-queryable record when LangFuse is unavailable.

## What v2 deliberately does not do

- **No Kubernetes.** Cloud Run scales to zero and is operationally cheaper.
- **No long-lived service-account keys.** GitHub Actions auths via Workload Identity Federation.
- **No multi-region.** A single `europe-west2` deployment is enough for a satirical news site; HA can be added by promoting Cloud SQL to `REGIONAL` and the LB is already global.
- **No human-in-the-loop publish gate.** LangFuse traces are the after-the-fact review surface.
