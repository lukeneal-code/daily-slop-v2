SHELL := /usr/bin/env bash

.PHONY: dev down logs backend-test frontend-test ci backup-v1 reset-db

dev:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

reset-db:
	docker compose down -v
	docker compose up -d db

backend-test:
	cd backend && uv run pytest -m "not eval"

frontend-test:
	cd frontend && pnpm test

ci: backend-test frontend-test

backup-v1:
	./scripts/backup_v1.sh
