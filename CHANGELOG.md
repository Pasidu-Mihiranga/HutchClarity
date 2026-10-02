# Changelog

All notable changes to Hutch Clarity are recorded here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/). Contract changes (`contracts/`) must be listed with their new contract version.

## [Unreleased]

### Added
- Next.js console staff roles: bottom role switcher (9 roles + step-up), permission-gated Desk / Insights / Studio / Admin wired to the live API; `GET/POST /v1/admin/switches` and merchant suspend demo route.
- Kodee-style immersive Clarity chat on the legacy self-care UI (`clarity-chat.js` / `clarity-chat.css`): welcome suggestion cards, topic browser, investigation progress, confirm modal, in-thread Trust Receipt, and localStorage chat history.
- Conversation turn accepts prior `facts` (`product`, `amount_lkr`, `case_id`, `chat_intent`) so follow-ups like "Can you stop it?" keep the discussed service.
- Enterprise plan v1.1, including chapters 17 (build blueprint), 18 (tech stack and AI) and 19 (policy change management).
- Runtime profiles (`lite`, `full`, `prod`) and local database and secrets workflow (ADR-0014, plan v1.2).
- Commit rules (single author, no attribution, short bullet bodies) and no-em-dash rule.
- Repository governance: AGENTS.md, ARCHITECTURE.md, CONTRIBUTING.md, ADRs 0001–0014, documentation templates, module registry, walkthrough index, development log.
