# Changelog

All notable changes to Hutch Clarity are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Modular monolith scaffold under `backend/src/clarity` (kernel, platform,
  modules, entrypoints).
- Runtime profiles `lite` / `full` via Docker Compose and composition-root
  drivers (mock bus/cache/blob; Kafka / Valkey / SeaweedFS stubs).
- OPA policy stubs (`deploy/opa`), Helm and OpenTofu placeholders.
- CI jobs: lint, test-legacy, test-new, gitleaks (continue-on-error), SBOM
  placeholder.

## [0.2.0-baseline] - 2026-10-02

### Added

- Baseline tag target for architecture alignment with HutchClarity-new plan
  (modular monolith + satellites, schema-per-module, outbox, lite/full
  profiles). See `VERSION` and `scripts/tag_baseline.sh`.

## [0.1.0] - hackathon prototype

### Added

- Legacy in-process prototype (`src/clarity`): cases, rules, decision, tools,
  Trust Receipts, web UI, MCP server, synthetic HUTCH mocks.
