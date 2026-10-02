"""Wiring: one place that builds the whole Clarity core (plan §22).

The container decides which drivers and which clock are in play. Everything
else takes its collaborators as arguments, so tests can build the same object
graph with a different world or a frozen clock.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from sqlalchemy import create_engine

from clarity.ai.gateway import AIGateway, ModelProvider
from clarity.app.mcp_view import CaseServiceMCPView
from clarity.app.settings import Settings, SettingsInvalid
from clarity.integration.drivers.mock.recurrence import MockRecurrenceProbe
from clarity.integration.drivers.mock.world import DEMO_NOW, SyntheticWorld, build_demo_world
from clarity.integration.ports import DriverMode
from clarity.integration.registry import AdapterRegistry
from clarity.modules.actions.capability import (
    PLANS,
    RefundBudget,
    StoredPlanRepository,
    ToolLayer,
)
from clarity.modules.case.public import (
    CASE_SEQUENCE,
    CASES,
    CaseService,
    StoredCaseRepository,
)
from clarity.modules.decision.public import DecisionPolicy, PolicyThresholds
from clarity.modules.detection.public import RuleEngine, load_packs
from clarity.modules.iam.public import OtpService, TokenIssuer
from clarity.modules.receipts.public import (
    BY_PLAN,
    RECEIPT_SEQUENCE,
    RECEIPTS,
    SUBSCRIBERS,
    SUPERSEDED,
    DevSigningService,
    ReceiptService,
    SigningService,
    StoredReceiptRepository,
)
from clarity.modules.timeline.public import TimelineBuilder
from clarity.platform.audit.ledger import AuditLedger
from clarity.platform.config.resolver import PolicyResolver
from clarity.platform.config.switches import SwitchBoard
from clarity.platform.messaging.consumers import CollectingAlertHook, ConsumerRegistry
from clarity.platform.messaging.drivers.in_process import InProcessEventBus
from clarity.platform.messaging.envelope import EventType
from clarity.platform.messaging.relay import Relay
from clarity.platform.observability import configure_logging, configure_tracing
from clarity.platform.persistence import (
    AutocommitRepository,
    MemoryStore,
    MemoryUnitOfWork,
    Repository,
    UnitOfWorkFactory,
)
from clarity.platform.persistence.postgres import PostgresStore


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


def _shared_dir(configured: Path | None, *parts: str) -> Path:
    """Locate a shared artefact directory (rule packs, policy).

    A deployment sets the path in its settings. In a checkout the directory is
    found by walking up from this file, so the layout can move without a code
    change.
    """
    if configured is not None:
        return configured
    for parent in Path(__file__).resolve().parents:
        candidate = parent.joinpath(*parts)
        if candidate.is_dir():
            return candidate
    return Path.cwd().joinpath(*parts)


def default_rules_dir(configured: Path | None = None) -> Path:
    """Rule packs live outside the Python package: rules are data, not code."""
    return _shared_dir(configured, "rules", "packs")


def default_policy_dir(configured: Path | None = None) -> Path:
    """Policy artefacts: caps, thresholds and windows that change without a deploy."""
    return _shared_dir(configured, "config", "policy")


def _world_for_profile(
    profile: Profile,
    world: SyntheticWorld | None,
    clock: datetime | None,
    settings: Settings,
) -> tuple[SyntheticWorld, bool]:
    """Return (world, persist_receipts)."""
    if profile is Profile.DEMO:
        return world or build_demo_world(now=clock or DEMO_NOW), False
    if profile is Profile.FULL:
        # An explicit world (tests) keeps DEMO-style memory unless they seed.
        if world is not None:
            return world, bool(getattr(world, "_persist", False))
        from clarity.integration.drivers.mock.store import (
            configure,
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

        # The driver is told which database to use; it never reads the
        # environment itself (B07).
        configure(settings.require_database_url())
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


#: How a profile gets its persistence: the store, a unit-of-work factory, and a
#: factory for the autocommit repositories the services hold.
_Persistence = tuple[
    "MemoryStore | PostgresStore",
    UnitOfWorkFactory,
    Callable[[str], Repository[Any, Any]],
]


def _persistence_for_profile(profile: Profile, settings: Settings) -> _Persistence:
    """Bind the persistence driver this profile runs with (ADR-0014, B05).

    This is the only place that chooses. Both drivers pass
    ``tests/contract/test_repository_parity.py``, so no module can tell which
    one it was handed.
    """
    if profile is Profile.DEMO:
        store = MemoryStore()
        return (
            store,
            lambda: MemoryUnitOfWork(store),
            lambda collection: AutocommitRepository(store, collection),
        )

    from clarity.app.collections import ALL_COLLECTIONS
    from clarity.platform.persistence.migrations import create_schema
    from clarity.platform.persistence.postgres import (
        PostgresAutocommitRepository,
        PostgresStore,
    )

    url = settings.require_database_url()
    if not url.startswith("postgresql"):
        raise SettingsInvalid(
            f"CLARITY_PROFILE=full needs a PostgreSQL DATABASE_URL, got {url!r}. "
            "Clarity's own state uses a schema and a role per module and "
            "row-level security (ADR-0013), none of which SQLite provides. "
            "Use the demo profile to run with no database."
        )
    engine = create_engine(url, future=True, pool_pre_ping=True)
    # Idempotent, so a replica that starts second finds the schema already there.
    create_schema(engine, ALL_COLLECTIONS)
    postgres = PostgresStore(engine)
    return (
        postgres,
        postgres.unit,
        lambda collection: PostgresAutocommitRepository(postgres, collection),
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
        settings: Settings | None = None,
    ) -> None:
        # The only place this process reads its environment (B07, I20). Tests
        # pass a Settings instance instead of setting variables.
        self.settings = settings or Settings()
        # Installed before any driver is built, so startup itself is traced and
        # redacted. Both are idempotent, so building a second Clarity in one
        # process (tests, `reset`) does not double the handlers or the spans.
        configure_logging(log_format=self.settings.log_format)
        configure_tracing(
            exporter=self.settings.otel_exporter,
            endpoint=self.settings.otlp_endpoint,
        )
        # The composition root, and the only reader of CLARITY_PROFILE.
        self.profile = Profile(profile or self.settings.profile)
        self._rules_dir = rules_dir
        self._policy_dir = policy_dir
        self._clock = clock
        self._verify_base = verify_base
        self._daily_refund_limit_lkr = daily_refund_limit_lkr
        self._provider = provider
        self.world, persist = _world_for_profile(self.profile, world, clock, self.settings)
        # Every module's state lives behind this seam (B02). The profile chooses
        # the driver; nothing in a module knows which one it got.
        self.store: MemoryStore | PostgresStore
        self.store, self.open_unit, self._repository = _persistence_for_profile(
            self.profile, self.settings
        )
        self.registry = AdapterRegistry(mode=DriverMode.MOCK, world=self.world)
        self.rules = RuleEngine(load_packs(rules_dir or default_rules_dir(self.settings.rules_dir)))
        self.policy = DecisionPolicy(thresholds)
        self.timeline = TimelineBuilder(self.registry.read_ports())
        self.tools = ToolLayer(
            self.registry.command_port,
            plans=StoredPlanRepository(self._repository(PLANS)),
            open_unit=self.open_unit,
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
            ledger=StoredReceiptRepository(
                self._repository(RECEIPTS),
                self._repository(SUPERSEDED),
                self._repository(SUBSCRIBERS),
                self._repository(RECEIPT_SEQUENCE),
                self._repository(BY_PLAN),
            ),
            probe=MockRecurrenceProbe(self.world),
            verify_base=verify_base,
            persist=persist,
        )
        # No model is configured by default: the gateway answers from
        # approved templates, which is the deck's "works without the LLM" path.
        self.ai = AIGateway(provider=provider, prefer_templates=provider is None)
        self.policies = PolicyResolver.from_directory(
            policy_dir or default_policy_dir(self.settings.policy_dir)
        )
        self.switches = SwitchBoard(audit_sink=self.audit)
        # Messaging: the bus, the relay that drains the outbox onto it, and the
        # consumer framework that wraps each handler in deduplication, backoff
        # and dead-lettering (B03, B04).
        self.bus = InProcessEventBus()
        self.relay = Relay(open_unit=self.open_unit, bus=self.bus)
        self.dead_letters = CollectingAlertHook()
        self.consumers = ConsumerRegistry(
            open_unit=self.open_unit,
            bus=self.bus,
            alert=self.dead_letters,
        )
        self.cases = CaseService(
            cases=StoredCaseRepository(
                self._repository(CASES),
                self._repository(CASE_SEQUENCE),
            ),
            deliver_events=self.deliver_events,
            timeline=self.timeline,
            rules=self.rules,
            policy=self.policy,
            tools=self.tools,
            receipts=self.receipts,
            policies=self.policies,
            switches=self.switches,
            clock=clock,
        )
        # The first event-driven flow (B06): the tool layer writes
        # action.completed with the plan it completed, and the receipt is the
        # consequence of that fact rather than a second call on the money path.
        self.consumers.register(
            EventType.ACTION_COMPLETED,
            group="receipts",
            handler=self.cases.on_action_completed,
        )
        # MCP gets the narrow view, never the case service itself (ADR-0004).
        # The MCP server itself is an interface, built by the interface layer.
        self.mcp_view = CaseServiceMCPView(self.cases, self.receipts)

    def deliver_events(self) -> None:
        """Publish whatever the last unit of work committed, then consume it.

        Called by the case module after a state change that produced events, so
        a synchronous API can still answer with what the event caused. A
        deployment runs the relay as its own process instead; the seam is the
        same either way.
        """
        self.relay.run_once()
        self.bus.drain()

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
