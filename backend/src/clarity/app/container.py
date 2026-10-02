"""Wiring: one place that builds the whole Clarity core (plan §22).

The container decides which drivers and which clock are in play. Everything
else takes its collaborators as arguments, so tests can build the same object
graph with a different world or a frozen clock.
"""

from __future__ import annotations

import os
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from clarity.ai.gateway import AIGateway, ModelProvider
from clarity.app.mcp_view import CaseServiceMCPView
from clarity.integration.drivers.mock.recurrence import MockRecurrenceProbe
from clarity.integration.drivers.mock.world import DEMO_NOW, SyntheticWorld, build_demo_world
from clarity.integration.ports import DriverMode
from clarity.integration.registry import AdapterRegistry
from clarity.modules.actions.capability import RefundBudget, ToolLayer
from clarity.modules.case.public import CaseService
from clarity.modules.decision.public import DecisionPolicy, PolicyThresholds
from clarity.modules.detection.public import RuleEngine, load_packs
from clarity.modules.iam.public import OtpService, TokenIssuer
from clarity.modules.receipts.public import DevSigningService, ReceiptService, SigningService
from clarity.modules.timeline.public import TimelineBuilder
from clarity.platform.audit.ledger import AuditLedger
from clarity.platform.config.resolver import PolicyResolver
from clarity.platform.config.switches import SwitchBoard


class Profile(StrEnum):
    """Which drivers this process runs with.

    Adopted from the alternative design's ADR-0014. The point is that a profile
    chooses **drivers only**: the outbox, idempotency keys, Money, the clock,
    permissions and correlation IDs exist in every profile, so a lighter
    profile skips servers, never seams.

    This is the only place in the codebase that reads CLARITY_PROFILE. Business
    code that branches on the profile is how light and real paths drift apart.
    """

    DEMO = "demo"
    """Everything in memory. Needs only Python. The default, so a reviewer can
    clone and run with no infrastructure."""

    FULL = "full"
    """Synthetic HUTCH world backed by SQL (Postgres or SQLite via DATABASE_URL)."""

    PROD = "prod"
    """HUTCH platform. No driver is implemented for this yet."""

    @classmethod
    def _missing_(cls, value: object) -> Profile | None:
        """Accept ``lite``, the name the plan and ADR-0027 use for ``demo``."""
        return cls.DEMO if value == "lite" else None


class ProfileNotAvailable(NotImplementedError):
    """A profile was requested whose drivers do not exist yet."""


def _shared_dir(env: str, *parts: str) -> Path:
    """Locate a shared artefact directory (rule packs, policy).

    Deployments set the path explicitly (deployment contract: configuration
    comes from the environment). In a checkout the directory is found by
    walking up from this file, so the layout can move without code changes.
    """
    if configured := os.environ.get(env):
        return Path(configured)
    for parent in Path(__file__).resolve().parents:
        candidate = parent.joinpath(*parts)
        if candidate.is_dir():
            return candidate
    return Path.cwd().joinpath(*parts)


#: Rule packs live outside the Python package: rules are data, not code (§13.1).
DEFAULT_RULES_DIR = _shared_dir("CLARITY_RULES_DIR", "rules", "packs")

#: Policy artefacts: caps, thresholds and windows that change without a deploy.
DEFAULT_POLICY_DIR = _shared_dir("CLARITY_POLICY_DIR", "config", "policy")


def _world_for_profile(
    profile: Profile,
    world: SyntheticWorld | None,
    clock: datetime | None,
) -> tuple[SyntheticWorld, bool]:
    """Return (world, persist_receipts)."""
    if profile is Profile.DEMO:
        return world or build_demo_world(now=clock or DEMO_NOW), False
    if profile is Profile.FULL:
        # An explicit world (tests) keeps DEMO-style memory unless they seed.
        if world is not None:
            return world, bool(getattr(world, "_persist", False))
        from clarity.integration.drivers.mock.store import (
            create_schema,
            load_world,
            save_complaints,
            save_world,
            session_scope,
            upsert_knowledge,
            world_is_seeded,
        )
        from clarity.integration.drivers.mock.store.knowledge import KNOWLEDGE_ARTICLES
        from clarity.integration.drivers.mock.store.volume import generate_complaints

        create_schema()
        with session_scope() as session:
            if world_is_seeded(session):
                chosen = load_world(session, now=clock or DEMO_NOW)
            else:
                chosen = build_demo_world(now=clock or DEMO_NOW, persist=False)
                save_world(session, chosen)
                upsert_knowledge(session, KNOWLEDGE_ARTICLES)
                save_complaints(session, generate_complaints(2000))
            chosen._persist = True
        return chosen, True
    raise ProfileNotAvailable(
        f"the {profile.value} profile has no drivers yet: real HUTCH adapters are not implemented"
    )


class Clarity:
    """The assembled application."""

    def __init__(
        self,
        *,
        rules_dir: Path | None = None,
        policy_dir: Path | None = None,
        world: SyntheticWorld | None = None,
        thresholds: PolicyThresholds | None = None,
        signing: SigningService | None = None,
        clock: datetime | None = DEMO_NOW,
        verify_base: str = "http://localhost:8000/v",
        provider: ModelProvider | None = None,
        daily_refund_limit_lkr: str = "250000.00",
        profile: Profile | str | None = None,
        tokens: TokenIssuer | None = None,
        otp: OtpService | None = None,
    ) -> None:
        # The composition root, and the only reader of CLARITY_PROFILE.
        self.profile = Profile(profile or os.environ.get("CLARITY_PROFILE", Profile.DEMO))
        self._rules_dir = rules_dir
        self._policy_dir = policy_dir
        self._clock = clock
        self._verify_base = verify_base
        self._daily_refund_limit_lkr = daily_refund_limit_lkr
        self._provider = provider
        self.world, persist = _world_for_profile(self.profile, world, clock)
        self.registry = AdapterRegistry(mode=DriverMode.MOCK, world=self.world)
        self.rules = RuleEngine(load_packs(rules_dir or DEFAULT_RULES_DIR))
        self.policy = DecisionPolicy(thresholds)
        self.timeline = TimelineBuilder(self.registry.read_ports())
        self.tools = ToolLayer(
            self.registry.command_port,
            budget=RefundBudget(daily_limit_lkr=daily_refund_limit_lkr),
        )
        self.audit = AuditLedger()
        # Identity is not demo data: a reset of the synthetic world must not
        # sign everyone out mid-demonstration, so these carry over.
        self.tokens = tokens or TokenIssuer()
        self.otp = otp or OtpService()
        self.signing = signing or DevSigningService()
        self.receipts = ReceiptService(
            self.signing,
            probe=MockRecurrenceProbe(self.world),
            verify_base=verify_base,
            persist=persist,
        )
        # No model is configured by default: the gateway answers from
        # approved templates, which is the deck's "works without the LLM" path.
        self.ai = AIGateway(provider=provider, prefer_templates=provider is None)
        self.policies = PolicyResolver.from_directory(policy_dir or DEFAULT_POLICY_DIR)
        self.switches = SwitchBoard(audit_sink=self.audit)
        self.cases = CaseService(
            timeline=self.timeline,
            rules=self.rules,
            policy=self.policy,
            tools=self.tools,
            receipts=self.receipts,
            policies=self.policies,
            switches=self.switches,
            clock=clock,
        )
        # MCP gets the narrow view, never the case service itself (ADR-0004).
        # The MCP server itself is an interface, built by the interface layer.
        self.mcp_view = CaseServiceMCPView(self.cases, self.receipts)

    def reset(self) -> Clarity:
        """Build a fresh instance with the same configuration.

        The demo mutates balances and subscriptions, so a reset gives a clean
        synthetic world without restarting the process.
        """
        if self.profile is Profile.FULL:
            from clarity.integration.drivers.mock.store import reset_engine

            # Drop the file/DB seed so the next construct re-seeds cleanly when
            # using the default SQLite file; Postgres users should run make seed.
            reset_engine()
            from clarity.integration.drivers.mock.store import (
                create_schema,
                save_complaints,
                save_world,
                session_scope,
                upsert_knowledge,
            )
            from clarity.integration.drivers.mock.store.knowledge import KNOWLEDGE_ARTICLES
            from clarity.integration.drivers.mock.store.volume import generate_complaints

            create_schema()
            fresh = build_demo_world(now=self._clock or DEMO_NOW, persist=False)
            with session_scope() as session:
                save_world(session, fresh)
                upsert_knowledge(session, KNOWLEDGE_ARTICLES)
                save_complaints(session, generate_complaints(2000))
            fresh._persist = True
            return Clarity(
                rules_dir=self._rules_dir,
                policy_dir=self._policy_dir,
                world=fresh,
                thresholds=self.policy.thresholds,
                clock=self._clock,
                verify_base=self._verify_base,
                daily_refund_limit_lkr=self._daily_refund_limit_lkr,
                provider=self._provider,
                profile=self.profile,
                tokens=self.tokens,
                otp=self.otp,
            )
        return Clarity(
            rules_dir=self._rules_dir,
            policy_dir=self._policy_dir,
            world=build_demo_world(),
            thresholds=self.policy.thresholds,
            clock=self._clock,
            verify_base=self._verify_base,
            daily_refund_limit_lkr=self._daily_refund_limit_lkr,
            provider=self._provider,
            profile=self.profile,
            tokens=self.tokens,
            otp=self.otp,
        )
