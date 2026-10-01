# 0003 - Every policy change has a class, an impact report and two sets of eyes

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-10-02 |
| Plan references | `docs/enterprise-plan/09` §14.4; `docs/improvement-plan.md` A6, A7; alternative design chapter 19 |

## Context
Once policy is data (ADR-0002), the editor is no longer the control. What stops
a wrong cap reaching production is the lifecycle around it.

## Decision
- The **change class** (C0-C4, E) is computed from the artefact's tags. It can
  be raised manually, never lowered.
- **Maker is never checker.** A money- or regulatory-affecting change needs a
  second, different approver with MFA step-up.
- A C2/C3/C4 change cannot be approved without a **replay impact report**:
  historic cases re-decided under the candidate, with outcome deltas, money
  delta and samples.
- **Kill switches** (`auto_fix_global`, `auto_fix.<rule>`, `customer_actions`,
  `llm_explanations`) degrade behaviour in seconds without a deploy. Every flip
  is audited.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Review in a pull request | Business users cannot use it, and it couples policy to release |
| Approval without impact evidence | An approver cannot judge a cap change without seeing what it does |

## Consequences
Changing a cap takes longer and produces evidence. Kill switches must always
degrade, never break: auto-fix off means staff approval, not failure.

## Compliance
`tests/unit/test_policy.py` asserts the maker cannot approve, that a money
change needs two approvers and an impact report, that a class cannot be
lowered, and that switches degrade to staff rather than to nothing.
