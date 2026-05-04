# The Daily Slop — v2

A satirical British news site, rebuilt. v2 keeps v1's tone, masthead, and palette, and adds:

- **6 sections**: Politics, Business, Tech, Culture, Sport, Royals.
- **Agentic backend** (LangGraph): **Nigel** (Claude) is the main writer, **Elle** (GPT) is an antagonistic editor with the final word, **Steve** (Grok 4) writes riskier left-field pieces. Each writer can push back once.
- **Charles-Addams-styled cartoons** without the gothic — Private-Eye-flavoured ink illustrations.
- **Self-hosted LangFuse** with synthetic eval datasets.
- **Modern GCP**: Cloud Run + Cloud SQL Postgres + Cloud Scheduler + GCS+CDN, Terraform-managed, GitHub Actions CI/CD via Workload Identity Federation.

## Layout

| Path | What it is |
|---|---|
| `backend/` | FastAPI + LangGraph daily-generation pipeline (Python 3.12). |
| `frontend/` | React 19 + Vite SPA. |
| `infra/terraform/` | Production infra. |
| `infra/bootstrap/` | One-shot setup of GCP project, tfstate bucket, secrets, WIF pool. |
| `langfuse/` | Self-hosted LangFuse (compose for local dev; Cloud Run for prod). |
| `scripts/` | Operational scripts (`backup_v1.sh`, eval seeding, etc). |
| `docs/` | Architecture, runbook, cutover notes. |

## Development quick start

```sh
# Backend
cd backend && uv sync && uv run pytest -m "not eval"
uv run uvicorn app.main:app --reload

# Frontend
cd frontend && pnpm install && pnpm dev

# LangFuse (local)
cd langfuse && docker compose up
```

See `docs/runbook.md` for the deploy/cutover playbook.

## Status

v2 is in active build-out. v1 (`https://dailyslop.co.uk`) keeps running until v2 passes its 3-day soak; then the DNS A-record flips at the registrar and v1 is decommissioned. v1 articles + images are backed up locally under `backups/v1/` and to the versioned bucket `gs://the-daily-slop-archive/` in the v1 GCP project.
# daily-slop-v2
