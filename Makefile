# Hutch Clarity - development tasks.
.PHONY: help dev check test lint types imports demo tokens

help:
	@echo "make dev     - run the app (UI + API) on http://localhost:8000"
	@echo "make check   - everything CI runs: lint, types, import contracts, tests"
	@echo "make test    - tests only"
	@echo "make demo    - walk the four journeys in the terminal"
	@echo "make tokens  - measured AI usage per journey"

dev:
	.venv/bin/uvicorn clarity.api.main:app --reload

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

demo:
	.venv/bin/python scripts/demo.py

tokens:
	.venv/bin/python scripts/measure_tokens.py
