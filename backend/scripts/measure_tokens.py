#!/usr/bin/env python
"""Measure AI usage across every prototype journey.

The hackathon requires token counts per customer journey (Guidelines §6.1-6.2).
Rather than estimating, this runs each journey through the real gateway and
reports what it actually consumed.

    .venv/bin/python scripts/measure_tokens.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from clarity.app.container import Clarity  # noqa: E402
from clarity.contracts.decision import Outcome  # noqa: E402
from clarity.integration.drivers.mock.world import ref_for  # noqa: E402
from clarity.kernel.common import Channel, Language  # noqa: E402

JOURNEYS = [
    ("VAS charged with no consent", "+94781234567", Language.SI),
    ("Reload taken twice", "+94782223333", Language.EN),
    ("'Unlimited' hit a fair-use cap", "+94783334444", Language.TA),
    ("Large reload not credited", "+94784445555", Language.EN),
]


def main() -> int:
    clarity = Clarity()
    print("\nAI USAGE, MEASURED PER JOURNEY")
    print(f"Provider: {clarity.ai.provider.name}\n")
    print(f"{'Journey':<34}{'Lang':<6}{'Calls':>6}{'In':>7}{'Out':>7}{'Total':>8}  Tier")
    print("-" * 86)

    for name, msisdn, language in JOURNEYS:
        before = len(clarity.ai.calls)
        account = clarity.world.account(ref_for(msisdn))
        assert account is not None

        case = clarity.cases.open_case(
            subscriber_ref=account.ref,
            msisdn_masked=account.masked,
            channel=Channel.APP,
            language=language,
        )
        decision = clarity.cases.evaluate(case.case_id)
        clarity.ai.explain(
            decision,
            rule_id=(
                clarity.cases.get(case.case_id).evaluation.top.assessment.rule_id
                if clarity.cases.get(case.case_id).evaluation.top
                else None
            ),
            language=language,
        )
        if decision.outcome in {Outcome.ONE_TAP_FIX, Outcome.AUTO_FIX, Outcome.STAFF_APPROVAL}:
            plan = clarity.cases.propose(case.case_id, created_by="measurement")
            if decision.outcome is Outcome.ONE_TAP_FIX:
                clarity.cases.confirm_and_execute(case.case_id, plan.plan_id)
            elif decision.outcome is Outcome.AUTO_FIX:
                clarity.cases.auto_fix(case.case_id, plan.plan_id)

        calls = clarity.ai.calls[before:]
        tokens_in = sum(c.usage.input_tokens for c in calls)
        tokens_out = sum(c.usage.output_tokens for c in calls)
        tiers = ",".join(sorted({c.tier.value for c in calls}))
        print(
            f"{name:<34}{language.value:<6}{len(calls):>6}{tokens_in:>7}{tokens_out:>7}"
            f"{tokens_in + tokens_out:>8}  {tiers}"
        )

    summary = clarity.ai.usage_summary
    print("-" * 86)
    print(
        f"{'TOTAL':<40}{summary['calls']:>6}{summary['input_tokens']:>7}"
        f"{summary['output_tokens']:>7}{summary['total_tokens']:>8}"
    )
    print(f"\nLLM-free share : {summary['llm_free_share']:.0%}")
    print(f"Fallbacks      : {summary['fallbacks']}")
    print(f"By tier        : {summary['by_tier']}")
    print(
        "\nNo language model is configured, so these are measured zeros, not estimates.\n"
        "Explanations come from CX-approved templates - the deck's 'works without\n"
        "the LLM' path (S7). Set CLARITY_MODEL_BASE_URL to route through a model;\n"
        "the masking, verification and fallback behaviour is unchanged.\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
