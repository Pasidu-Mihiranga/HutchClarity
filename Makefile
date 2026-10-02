# Hutch Clarity - development tasks.
.PHONY: help dev dev-new up-lite up-full down db-reset keys check test test-g1 seed demo lint types imports tokens

help:
	@echo "make dev       - run the old app (src/clarity) on http://localhost:8000"
	@echo "make dev-new   - run the new backend entrypoint (backend/src/clarity)"
	@echo "make up-lite   - docker compose profile lite (Postgres)"
	@echo "make up-full   - docker compose profile full (Postgres + Kafka + …)"
	@echo "make down      - stop all compose profiles"
	@echo "make db-reset  - wipe Postgres volume and restart lite Postgres"
	@echo "make keys      - generate Ed25519 signing keypair into .keys/"
	@echo "make check     - lint, types, import contracts, tests (old tree)"
	@echo "make test      - old-tree tests only"
	@echo "make test-g1   - G1 baseline tests (backend/src, in-memory)"
	@echo "make seed      - load synthetic world into DATABASE_URL"
	@echo "make demo      - walk the four journeys in the terminal"
	@echo "make lint      - ruff check + format --check"
	@echo "make types     - mypy"
	@echo "make tokens    - measured AI usage per journey"

dev:
	.venv/bin/uvicorn clarity.api.main:app --reload

dev-new:
	PYTHONPATH=backend/src .venv/bin/uvicorn clarity.entrypoints.api:app --reload --port 8000

up-lite:
	docker compose --profile lite up -d

up-full:
	docker compose --profile full up -d

down:
	docker compose --profile lite --profile full down

db-reset:
	docker compose --profile lite --profile full down -v
	docker compose --profile lite up -d postgres
	@echo "Waiting for Postgres…"
	@until docker compose --profile lite exec -T postgres pg_isready -U clarity -d clarity >/dev/null 2>&1; do sleep 1; done
	@echo "Postgres ready (volume wiped)."

keys:
	.venv/bin/python scripts/keys.py

seed:
	.venv/bin/python scripts/seed.py

check: lint types imports test

lint:
	.venv/bin/ruff check .
	.venv/bin/ruff format --check .

types:
	.venv/bin/mypy

imports:
	.venv/bin/lint-imports

test:
	.venv/bin/pytest

test-g1:
	PYTHONPATH=backend/src .venv/bin/pytest backend/tests/g1 backend/tests/unit -q -o pythonpath=backend/src

demo:
	.venv/bin/python scripts/demo.py

tokens:
	.venv/bin/python scripts/measure_tokens.py
