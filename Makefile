# Hutch Clarity - development tasks. Run from the repository root.
#
# The default `lite` profile needs only Python: no Docker, Kubernetes, Terraform,
# database or broker (ADR-0027). The `full` profile (real infrastructure) is
# added in migration step R2 (docs/enterprise-plan/21-migration-and-deployment-plan.md).

PY      := $(CURDIR)/.venv/bin
BACKEND := backend

.PHONY: help setup dev check lint format types imports test demo tokens keys seed \
        web-install web-build web-customer web-console web-verify

help:
	@echo "make setup   - create .venv and install the backend with dev tools"
	@echo "make dev     - run the app (UI + API) on http://localhost:8000 (lite profile)"
	@echo "make check   - everything CI runs: lint, types, import contracts, tests"
	@echo "make test    - tests only"
	@echo "make format  - apply formatting and safe lint fixes"
	@echo "make demo    - walk the four journeys in the terminal"
	@echo "make tokens  - measured AI usage per journey"
	@echo "make keys    - generate a local Ed25519 signing key into .keys/"
	@echo "make seed    - load the synthetic world into DATABASE_URL (full profile)"
	@echo "make web-install / web-build - frontend (Node 18+, npm workspaces)"
	@echo "make web-customer | web-console | web-verify - run one Next.js app"

setup:
	python3 -m venv .venv
	$(PY)/pip install -e "$(BACKEND)[dev]"

dev:
	cd $(BACKEND) && $(PY)/uvicorn clarity.entrypoints.asgi:app --reload

check: lint types imports test

lint:
	cd $(BACKEND) && $(PY)/ruff check . && $(PY)/ruff format --check .

format:
	cd $(BACKEND) && $(PY)/ruff check --fix . && $(PY)/ruff format .

types:
	cd $(BACKEND) && $(PY)/mypy

imports:
	cd $(BACKEND) && $(PY)/lint-imports

test:
	cd $(BACKEND) && $(PY)/pytest

demo:
	cd $(BACKEND) && $(PY)/python scripts/demo.py

tokens:
	cd $(BACKEND) && $(PY)/python scripts/measure_tokens.py

keys:
	cd $(BACKEND) && $(PY)/python scripts/keys.py

seed:
	cd $(BACKEND) && $(PY)/python scripts/seed.py

# Frontend (Next.js apps). Optional: the backend serves a static UI on its own.
web-install:
	cd frontend && npm install

web-build:
	cd frontend && npm run build

web-customer:
	cd frontend && npm run dev:customer

web-console:
	cd frontend && npm run dev:console

web-verify:
	cd frontend && npm run dev:verify
