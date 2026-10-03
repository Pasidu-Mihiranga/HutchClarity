# Hutch Clarity - development tasks. Run from the repository root.
#
# The default `lite` profile needs only Python: no Docker, Kubernetes, Terraform,
# database or broker (ADR-0027). The `full` profile (real infrastructure) is
# added in migration step R2 (docs/enterprise-plan/21-migration-and-deployment-plan.md).

PY      := $(CURDIR)/.venv/bin
BACKEND := backend

COMPOSE := deploy/compose/full.yml
# 5440, not 5432: a developer machine usually already runs PostgreSQL there.
FULL_DATABASE_URL := postgresql+psycopg://clarity:clarity@localhost:5440/clarity

.PHONY: help setup dev mcp check lint format types imports test demo tokens keys seed eval \
        up-full down-full test-full dev-e2e e2e e2e-install channel-gateway \
        contracts contracts-check \
        licences secrets \
        web-install web-build web-customer web-console web-verify

help:
	@echo "make setup   - create .venv and install the backend with dev tools"
	@echo "make dev     - run the app (UI + API) on http://localhost:8000 (lite profile)"
	@echo "make mcp     - run clarity-mcp (MCP over Streamable HTTP) on :8099"
	@echo "make channel-gateway - WhatsApp/SMS/USSD ingress on :8102 (N02)"
	@echo "make check   - everything CI runs: lint, types, import contracts, tests"
	@echo "make test    - tests only"
	@echo "make format  - apply formatting and safe lint fixes"
	@echo "make demo    - walk the four journeys in the terminal"
	@echo "make tokens  - measured AI usage per journey"
	@echo "make eval    - run the evaluation sets and apply the release gates"
	@echo "make keys    - generate a local Ed25519 signing key into .keys/"
	@echo "make seed    - load the synthetic world into DATABASE_URL (full profile)"
	@echo "make up-full - start the full profile's components (Kafka); needs Docker"
	@echo "make down-full - stop them and remove their volumes"
	@echo "make test-full - run the parity suites against the full profile"
	@echo "make e2e      - browser journeys (needs: make e2e-install once)"
	@echo "make contracts - re-export contracts/openapi.json and regenerate the SDK types"
	@echo "make contracts-check - fail if the committed schema or SDK types are stale"
	@echo "make licences - check every dependency licence is neutral and OSI-approved"
	@echo "make secrets  - scan the history for secrets (needs Docker)"
	@echo "make web-install / web-build - frontend (Node 18+, npm workspaces)"
	@echo "make web-customer | web-console | web-verify - run one Next.js app"

# --clear so a venv left at this path by an older interpreter is replaced
# rather than half-reused: a stale bin/python symlink pointing at a different
# Python leaves the console scripts and `python` disagreeing, and every
# Makefile target that calls `python` directly then fails to import clarity.
setup:
	python3 -m venv --clear .venv
	$(PY)/pip install -e "$(BACKEND)[dev]"

dev:
	cd $(BACKEND) && $(PY)/uvicorn clarity.entrypoints.asgi:app --reload

# The clarity-mcp deployable (A04, ADR-0018), on :8099. Needs the simulated
# Keycloak realm for tokens: `docker compose -f deploy/compose/full.yml up -d
# --wait keycloak`. Walkthrough: docs/walkthroughs/WT-10-external-mcp-client.md
mcp:
	cd $(BACKEND) && \
		CLARITY_KEYCLOAK_ISSUER=http://localhost:8081/realms/clarity \
		CLARITY_KEYCLOAK_AUDIENCE=clarity-api \
		CLARITY_MCP_RESOURCE_URL=http://127.0.0.1:8099/mcp \
		CLARITY_MCP_ALLOWED_HOSTS=127.0.0.1:8099 \
		$(PY)/uvicorn clarity.entrypoints.mcp_asgi:app --host 127.0.0.1 --port 8099

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

# The evaluation harness (A05, plan 22 section 10). Exits non-zero when any
# gate fails or could not be evaluated, which is what blocks a release. No
# live model call in the default mode; the nightly job passes --mode live.
eval:
	cd $(BACKEND) && $(PY)/python scripts/evaluate.py

keys:
	cd $(BACKEND) && $(PY)/python scripts/keys.py

seed:
	cd $(BACKEND) && $(PY)/python scripts/seed.py

# The `full` profile: real components instead of in-process drivers (ADR-0027).
# Needs Docker. `lite` stays the default and needs none of this.
up-full:
	docker compose -f $(COMPOSE) up -d --wait

down-full:
	docker compose -f $(COMPOSE) down -v

# The parity suites against the real drivers. Each one skips unless its
# component is reachable, so this is honest about what it actually verified.
channel-gateway:
	@# The clarity-channel-gateway deployable (N02, #40), on :8102. Refuses
	@# every webhook unless CLARITY_CHANNEL_WEBHOOK_SECRET is set, which is
	@# the safe direction; /sim/* needs no signature for the demo journey.
	cd $(BACKEND) && $(PY)/uvicorn --app-dir ../services/channel-gateway/src \
		main:app --host 127.0.0.1 --port 8102

dev-e2e:
	@# The API the browser suite drives (C05). A fixed port so Playwright can
	@# wait on it, the lite profile so it needs no services (ADR-0006), and
	@# OTEL off so the output stays readable in the suite's logs.
	cd $(BACKEND) && CLARITY_PROFILE=lite OTEL_EXPORTER=none \
		$(PY)/uvicorn clarity.entrypoints.asgi:app --host 127.0.0.1 --port 8100

e2e:
	cd frontend && npm run e2e

e2e-install:
	cd frontend && npm install && npm run e2e:install

test-full:
	$(PY)/pip install -e "$(BACKEND)[dev,kafka,postgres]"
	cd $(BACKEND) && \
		CLARITY_KAFKA_BOOTSTRAP=localhost:9092 \
		CLARITY_TEST_DATABASE_URL=$(FULL_DATABASE_URL) \
		CLARITY_OPA_URL=http://localhost:8181 \
		CLARITY_OPENBAO_URL=http://localhost:8200 \
		CLARITY_OPENBAO_TOKEN=clarity-development-only \
		CLARITY_KEYCLOAK_URL=http://localhost:8081 \
		$(PY)/pytest tests/contract tests/integration -v

# Contracts: the OpenAPI schema is committed, so a change shows up in a diff and
# CI can tell a generated client is stale without starting the app (B09).
contracts:
	cd $(BACKEND) && $(PY)/python scripts/export_openapi.py
	cd frontend && npm run sdk:generate

contracts-check:
	cd $(BACKEND) && $(PY)/python scripts/export_openapi.py --check
	cd frontend && npm run sdk:check

# Supply chain: the same gates CI runs, so a failure is found before the push.
licences:
	$(PY)/pip install -q pip-licenses
	$(PY)/pip-licenses --format=json --with-urls > licences.json
	cd $(BACKEND) && $(PY)/python scripts/check_licences.py ../licences.json

secrets:
	docker run --rm -v "$(CURDIR)":/repo -w /repo zricethezav/gitleaks:latest \
		detect --config .gitleaks.toml --no-banner --redact --exit-code 1

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
