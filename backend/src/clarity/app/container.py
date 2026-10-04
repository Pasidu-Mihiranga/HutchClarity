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
from threading import RLock
from typing import Any

from sqlalchemy import create_engine

from clarity.ai.buckets import TokenBuckets
from clarity.ai.cassettes import CassetteLibrary, RecordedProvider
from clarity.ai.gateway import (
    AIGateway,
    ModelProvider,
    Prompt,
    TemplateProvider,
    Usage,
)
from clarity.ai.guard import Guard
from clarity.ai.local import LOCAL_IMPLEMENTATIONS
from clarity.ai.providers import ProviderConfig, VertexAIProvider, provider_for
from clarity.ai.roles import LOCAL_PROVIDERS, ModelCatalogue, ModelRole
from clarity.ai.routing import RoleRouter
from clarity.app.desk import ServiceCaseFixer, ServiceDeskCases
from clarity.app.flow_tools import FlowToolAdapter
from clarity.app.knowledge_seed import seed_help_articles
from clarity.app.mcp_view import ResolutionServiceMCPView
from clarity.app.settings import Settings, SettingsInvalid
from clarity.contracts.case import CaseTrigger
from clarity.contracts.decision import Outcome
from clarity.contracts.events import KnowledgePublishedV1, RiskDetectedV1
from clarity.integration.drivers.mock.recurrence import MockRecurrenceProbe
from clarity.integration.drivers.mock.world import DEMO_NOW, SyntheticWorld, build_demo_world
from clarity.integration.ports import DriverMode
from clarity.integration.registry import AdapterRegistry
from clarity.kernel.common import Channel, Language
from clarity.modules.actions.capability import (
    PLANS,
    RefundBudget,
    StoredPlanRepository,
    ToolLayer,
)
from clarity.modules.autopsy.public import AutopsyService, ComplaintSource
from clarity.modules.case.public import (
    CASE_SEQUENCE,
    CASES,
    CaseAggregate,
    StoredCaseRepository,
)
from clarity.modules.conversation.public import (
    BoundedAgent,
    ConversationOrchestrator,
    FlowRouter,
    IntakeAssist,
    Intent,
    Planner,
    PlannerReply,
    load_flows,
)
from clarity.modules.decision.public import PolicyThresholds, ZenDecisionPolicy
from clarity.modules.deskops.public import DeskOps
from clarity.modules.detection.public import RuleEngine, load_packs
from clarity.modules.governance.public import (
    CHANGES,
    PolicyGovernance,
    StoredPolicyChangeRepository,
)
from clarity.modules.iam.public import (
    AuthorizationPolicy,
    CompositeTokenVerifier,
    KeycloakTokenVerifier,
    OpaAuthorizationPolicy,
    OtpService,
    PythonAuthorizationPolicy,
    TokenIssuer,
    TokenVerifier,
)
from clarity.modules.insights.public import PROJECTED, InsightsService
from clarity.modules.knowledge.public import (
    AnswerCache,
    Audience,
    KnowledgeRegistry,
    KnowledgeRetriever,
    KnowledgeService,
    RetrievalConfig,
)
from clarity.modules.notifications.public import (
    CONSUMED_EVENTS as NOTIFICATION_EVENTS,
)
from clarity.modules.notifications.public import (
    MemoryNotificationDispatcher,
    NotificationService,
)
from clarity.modules.proactive.public import CONSUMED_EVENTS as PROACTIVE_EVENTS
from clarity.modules.proactive.public import ProactiveService
from clarity.modules.receipts.public import (
    BY_PLAN,
    RECEIPT_SEQUENCE,
    RECEIPTS,
    SUBSCRIBERS,
    SUPERSEDED,
    DevSigningService,
    OpenBaoSigningService,
    ReceiptService,
    SigningService,
    StoredReceiptRepository,
)
from clarity.modules.reconciliation.public import ReconciliationService
from clarity.modules.resolution.public import ResolutionService
from clarity.modules.timeline.public import TimelineBuilder
from clarity.platform.audit.ledger import AuditLedger
from clarity.platform.config.resolver import PolicyResolver
from clarity.platform.config.switches import SwitchBoard
from clarity.platform.messaging.consumers import CollectingAlertHook, ConsumerRegistry
from clarity.platform.messaging.drivers.in_process import InProcessEventBus
from clarity.platform.messaging.envelope import Event, EventType
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


def default_flow_dir(configured: Path | None = None) -> Path:
    """Conversation flows: policy content, published like a rule pack (C02)."""
    return _shared_dir(configured, "config", "flows")


def default_retrieval_file(configured: Path | None = None) -> Path:
    """Retrieval parameters (K02): top-k, BM25 constants, rerank bonuses.

    The setting names a **file**, not a directory, so a configured value is
    used as given rather than having a filename appended to it.
    """
    if configured is not None:
        return configured
    return _shared_dir(None, "config", "ai") / "retrieval.yaml"


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


def default_models_file(configured: Path | None = None) -> Path:
    """Where the model roles are declared. Data, not code (I12)."""
    return _shared_dir(configured, "config", "ai") / "models.yaml"


def _ai_providers(configured: ModelProvider | None, settings: Settings) -> dict[str, ModelProvider]:
    """Bind each provider name in the catalogue to something that can answer.

    The local ones always exist, which is what makes "no model configured" a
    supported state rather than an outage (ADR-0009). A remote name is bound
    only when this deployment actually has that provider, and an unbound name
    is skipped by the router rather than being an error.

    In replay mode every remote provider is wrapped in a cassette, so a test
    cannot reach the network even when a key is present (A02).
    """
    providers: dict[str, ModelProvider] = {
        "template": TemplateProvider(),
        # Embeddings have no local model in the prototype; the template
        # provider stands in so the chain terminates (plan 19 section 2.1
        # names BGE-M3 for production).
        "local-bge": TemplateProvider(),
    }
    for name, implementation in LOCAL_IMPLEMENTATIONS.items():
        providers[name] = implementation()

    if configured is None:
        return providers

    library = CassetteLibrary(settings.cassette_dir, recording=settings.record_cassettes)
    # One configured provider stands behind every remote name: the prototype
    # has a single endpoint, and the catalogue decides which role reaches it.
    remote_names = ("vertex",) if isinstance(configured, VertexAIProvider) else ("groq", "gemini")
    for remote in remote_names:
        providers[remote] = RecordedProvider(
            configured,
            library=library,
            role="shared",
            provider=remote,
            model=settings.model_name,
        )
    return providers


def _guard_assist(router: RoleRouter, catalogue: ModelCatalogue) -> object | None:
    """The guard role's provider, when one is configured for it."""
    chain = catalogue.routing(ModelRole.GUARD).chain
    for step in chain:
        if not step.is_local and step.provider in router.configured:
            return _RoleProvider(router, ModelRole.GUARD)
    return None


#: The events the dashboards are built from (I01, #30).
#:
#: Derived from the projection's own `PROJECTED` tuple rather than listed here,
#: so the subscription and the fold cannot drift: a type subscribed but not
#: folded wastes deliveries, and a type folded but not subscribed makes a live
#: projection disagree with a replay of the same history, which is the one
#: thing acceptance 1 forbids.
INSIGHT_EVENTS: tuple[EventType, ...] = tuple(payload.event_type for payload in PROJECTED)


def _complaint_source() -> ComplaintSource | None:
    """Where autopsy reads complaint text from (AU01).

    The simulated complaint store, which is where complaints live in every
    synthetic profile. ``None`` when it cannot be read, which leaves the
    consumer recording "no_text" and the relay redelivering: a store that is
    not there is not a reason to lose an event.
    """

    class MockStoreComplaints:
        def text_for(self, complaint_id: str) -> str | None:
            try:
                from clarity.integration.drivers.mock.store import (
                    list_complaints,
                    session_scope,
                )

                with session_scope() as session:
                    for row in list_complaints(session):
                        if str(row.get("id") or row.get("complaint_id")) == complaint_id:
                            text = row.get("text")
                            return str(text) if text else None
            except Exception:
                return None
            return None

    return MockStoreComplaints()


def _intake_assist(router: RoleRouter, catalogue: ModelCatalogue) -> IntakeAssist | None:
    """The `extract` role, for intake the keyword rules were unsure about (C04).

    Mirrors `_guard_assist` and `_planner`, including returning ``None``. A
    template cannot classify an intent, so wiring one would mean a rejected
    answer on every uncertain turn. ``None`` is the supported default
    (ADR-0009): the rules answer alone, and they measure F1 at or above 0.93
    per language on the golden set without any model.
    """
    chain = catalogue.routing(ModelRole.EXTRACT).chain
    for step in chain:
        if not step.is_local and step.provider in router.configured:
            return _RoleIntakeAssist(router)
    return None


class _RoleIntakeAssist:
    """Adapts the `extract` role to the intake assist interface.

    Asks for one intent name and nothing else. The caller validates it against
    the catalogue, so this does not need to: a model naming an intent that does
    not exist is a rejected answer rather than a new intent.
    """

    def __init__(self, router: RoleRouter) -> None:
        self._router = router

    def classify(self, text: str) -> str | None:
        answer = self._router.invoke(
            ModelRole.EXTRACT,
            Prompt(
                system=(
                    "Name the single intent this message is about. Reply with one "
                    "name from this list and nothing else: "
                    + ", ".join(intent.value for intent in Intent)
                ),
                facts={},
                # The masked text, because this is the one place a customer's
                # words reach a provider on this path (I13). The orchestrator
                # masks before intake runs.
                user_masked=text,
                language=Language.EN,
            ),
        )
        if answer.is_refusal or answer.provider in LOCAL_PROVIDERS:
            return None
        return answer.text.strip()


def _planner(router: RoleRouter, catalogue: ModelCatalogue) -> Planner | None:
    """The planner for agentic flow states, when a model is configured (C03).

    Mirrors ``_guard_assist`` deliberately, including returning ``None``. A
    template cannot choose a tool, so wiring one would mean a rejected plan and
    a wasted call on every agentic state. ``None`` is the supported default
    (ADR-0009): the deterministic step runs and the conversation completes.
    """
    chain = catalogue.routing(ModelRole.REASON).chain
    for step in chain:
        if not step.is_local and step.provider in router.configured:
            return _RolePlanner(router)
    return None


class _RolePlanner:
    """Adapts the ``reason`` role to the planner interface the agent expects.

    No facts and no customer text go in the prompt: what the agent sends is the
    state's tool list and the tool output it has gathered, already delimited as
    untrusted. The reply is text, and validating it is the agent's job (I1).
    """

    def __init__(self, router: RoleRouter) -> None:
        self._router = router

    def propose(self, prompt: str) -> PlannerReply | None:
        answer = self._router.invoke(
            ModelRole.REASON,
            Prompt(system=prompt, facts={}, user_masked="", language=Language.EN),
        )
        if answer.is_refusal or answer.provider in LOCAL_PROVIDERS:
            # A template answered. It has nothing to say about which tool to
            # use, and treating its wording as a plan would be a rejection
            # dressed up as a decision.
            return None
        return PlannerReply(
            text=answer.text,
            tokens=answer.spent_tokens,
            model_role=ModelRole.REASON.value,
            model=answer.model,
        )


class _RoleProvider:
    """Adapts a role to the provider interface the guard expects."""

    def __init__(self, router: RoleRouter, role: ModelRole) -> None:
        self._router = router
        self._role = role
        self.name = f"role:{role.value}"

    def complete(self, prompt: Prompt) -> tuple[str, Usage]:
        answer = self._router.invoke(self._role, prompt)
        return answer.text, answer.usage


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
        verify_base: str = "http://localhost:3002/r",
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
        configured_verify_base = (
            self.settings.verify_base if verify_base == "http://localhost:3002/r" else verify_base
        )
        self._verify_base = configured_verify_base
        self._daily_refund_limit_lkr = daily_refund_limit_lkr
        configured_provider = provider
        if configured_provider is None and self.settings.vertex_project:
            configured_provider = VertexAIProvider(
                project=self.settings.vertex_project,
                location=self.settings.vertex_location,
                model=self.settings.model_name,
                timeout_seconds=self.settings.model_timeout_seconds,
            )
        if configured_provider is None:
            configured_provider = provider_for(
                ProviderConfig.of(
                    base_url=self.settings.model_base_url,
                    model=self.settings.model_name,
                    api_key=self.settings.model_api_key,
                    timeout_seconds=self.settings.model_timeout_seconds,
                )
            )
        self._provider = configured_provider
        self.world, persist = _world_for_profile(self.profile, world, clock, self.settings)
        # Every module's state lives behind this seam (B02). The profile chooses
        # the driver; nothing in a module knows which one it got.
        self.store: MemoryStore | PostgresStore
        self.store, self.open_unit, self._repository = _persistence_for_profile(
            self.profile, self.settings
        )
        adapter_mode = DriverMode.HUTCH_SIM if self.profile is Profile.FULL else DriverMode.MOCK
        self.registry = AdapterRegistry(
            mode=adapter_mode,
            world=self.world,
            base_url=self.settings.hutch_sim_url,
            timeout_seconds=self.settings.hutch_sim_timeout_seconds,
        )
        self.rules = RuleEngine(load_packs(rules_dir or default_rules_dir(self.settings.rules_dir)))
        self.policy = ZenDecisionPolicy.from_file(
            default_policy_dir(policy_dir or self.settings.policy_dir) / "decision-table.json",
            thresholds=thresholds,
        )
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
        self.tokens = tokens or TokenIssuer(open_unit=self.open_unit)
        self.otp = otp or OtpService(open_unit=self.open_unit)
        self.token_verifier: TokenVerifier = self.tokens
        if self.settings.keycloak_issuer:
            self.token_verifier = CompositeTokenVerifier(
                self.tokens,
                KeycloakTokenVerifier(
                    self.settings.keycloak_issuer,
                    self.settings.keycloak_audience,
                    jwks_url=self.settings.keycloak_jwks_url,
                    timeout_seconds=self.settings.auth_timeout_seconds,
                ),
            )
        self.authorization: AuthorizationPolicy = (
            OpaAuthorizationPolicy(
                self.settings.opa_url,
                timeout_seconds=self.settings.auth_timeout_seconds,
            )
            if self.settings.opa_url
            else PythonAuthorizationPolicy()
        )
        self.signing = signing or (
            OpenBaoSigningService(
                self.settings.signer_url,
                key_name=self.settings.signer_key_name,
                token=self.settings.signer_token or "",
                mount=self.settings.signer_mount,
                namespace=self.settings.signer_namespace,
                timeout_seconds=self.settings.signer_timeout_seconds,
            )
            if self.settings.signer_url
            else DevSigningService(key_path=self.settings.signing_key_path)
        )
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
            verify_base=configured_verify_base,
            persist=persist,
            open_unit=self.open_unit,
        )
        # No model is configured by default: the gateway answers from
        # approved templates, which is the deck's "works without the LLM" path.
        self.ai = AIGateway(
            provider=self._provider,
            prefer_templates=self.settings.prefer_templates or self._provider is None,
        )
        # Roles, not models (A01, I12). The catalogue is the only place a model
        # ID appears; code asks for a role and this walks the chain it declares.
        self.models = ModelCatalogue.from_file(default_models_file(self.settings.models_file))
        self.ai_quotas = TokenBuckets()
        self.roles = RoleRouter(
            self.models,
            providers=_ai_providers(self._provider, self.settings),
            buckets=self.ai_quotas,
        )
        # Heuristics always; the guard role assists when a provider is set. It
        # can only ever add a refusal, never clear one (A03).
        self.guard = Guard(assist=_guard_assist(self.roles, self.models))
        self.policies = PolicyResolver.from_directory(
            policy_dir or default_policy_dir(self.settings.policy_dir)
        )
        self.switches = SwitchBoard(audit_sink=self.audit)
        # Messaging: the bus, the relay that drains the outbox onto it, and the
        # consumer framework that wraps each handler in deduplication, backoff
        # and dead-lettering (B03, B04).
        self.bus = InProcessEventBus()
        self.relay = Relay(open_unit=self.open_unit, bus=self.bus)
        self._delivery_lock = RLock()
        self._delivering_events = False
        self.dead_letters = CollectingAlertHook()
        self.consumers = ConsumerRegistry(
            open_unit=self.open_unit,
            bus=self.bus,
            alert=self.dead_letters,
        )
        self.notification_dispatcher = MemoryNotificationDispatcher()
        self.notifications = NotificationService(
            open_unit=self.open_unit,
            dispatcher=self.notification_dispatcher,
            clock=lambda: clock or DEMO_NOW,
        )
        self.proactive = ProactiveService(open_unit=self.open_unit, policies=self.policies)
        # The aggregate owns the case; the resolution service orchestrates
        # (M-CASE, plan 21 section 2.2).
        self.case_aggregate = CaseAggregate(
            StoredCaseRepository(
                self._repository(CASES),
                self._repository(CASE_SEQUENCE),
            ),
            clock=clock,
        )
        self.reconciliation = ReconciliationService(
            open_unit=self.open_unit,
            confirmations=self.registry.command_port,
            clock=self.case_aggregate._now,
        )
        self.governance = PolicyGovernance(
            StoredPolicyChangeRepository(self._repository(CHANGES)),
            policies=self.policies,
            audit=self.audit,
            clock=self.case_aggregate._now,
            open_unit=self.open_unit,
            deliver_events=self.deliver_events,
        )
        self.cases = ResolutionService(
            aggregate=self.case_aggregate,
            open_unit=self.open_unit,
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
        self.consumers.register(
            EventType.ACTION_COMPLETED,
            group="reconciliation",
            handler=self.reconciliation.on_action_completed,
        )
        for event_type in NOTIFICATION_EVENTS:
            self.consumers.register(
                event_type,
                group="notifications",
                handler=self.notifications.consume_event,
            )
        for event_type in PROACTIVE_EVENTS:
            self.consumers.register(
                event_type,
                group="proactive",
                handler=self.proactive.consume_event,
            )
        self.consumers.register(
            EventType.RISK_DETECTED,
            group="proactive-cases",
            handler=self._open_zero_contact_case,
        )
        # MCP gets the narrow view, never the case service itself (ADR-0004).
        # The MCP server itself is an interface, built by the interface layer.
        self.mcp_view = ResolutionServiceMCPView(self.cases, self.receipts, self.world)

        # Governed knowledge content (K01, #31). The registry is wired here and
        # starts empty: the corpus is HUTCH content (catalogue, T&C, Gazette
        # text, help articles) and inventing any of it would be inventing HUTCH
        # regulations (I16). K02 (#32) ranks whatever has been published.
        self.knowledge = KnowledgeRegistry(
            open_unit=self.open_unit,
            clock=self.case_aggregate._now,
        )
        # Retrieval over whatever has been published (K02, #32). The lexical
        # index only: there is no embedding model in the system, so no semantic
        # ranker is wired and the hybrid weights renormalise onto BM25. ADR-0009
        # makes that a supported state rather than a degradation.
        self.retrieval_config = RetrievalConfig.from_file(
            default_retrieval_file(self.settings.retrieval_file)
        )
        self.retriever = KnowledgeRetriever(self.knowledge, self.retrieval_config)
        # The corpus (K03). The simulated help articles already served by
        # /v1/knowledge/search, published here so that route can be served by
        # the module without regressing to answering nothing. Nothing is
        # invented: see app/knowledge_seed.py.
        seed_help_articles(self.knowledge)
        self.retriever.index(self.knowledge.chunks_as_of(audience=Audience.STAFF))
        # Grounded answers (K03). No composer: with no model configured the
        # template path quotes the source verbatim and cites it, which is the
        # floor ADR-0009 requires and is never worse than correct.
        self.answer_cache = AnswerCache()
        self.answers = KnowledgeService(
            self.knowledge,
            self.retriever,
            cache=self.answer_cache,
            clock=self.case_aggregate._now,
        )
        self.consumers.register(
            EventType.KNOWLEDGE_PUBLISHED,
            group="knowledge-cache",
            handler=self._invalidate_answer_cache,
        )

        # Complaint Autopsy, fed by events rather than run as a batch over
        # demo data (AU01, #13). The event carries no complaint text, so the
        # service fetches it through a source the composition root supplies:
        # putting customer words in the bus is what `complaint.created` was
        # shaped to avoid.
        self.autopsy = AutopsyService(
            open_unit=self.open_unit,
            source=_complaint_source(),
            clock=self.case_aggregate._now,
        )
        self.consumers.register(
            EventType.COMPLAINT_CREATED,
            group="autopsy",
            handler=self.autopsy.on_complaint_created,
        )

        # Insights read models, folded from the event log (I01, #30). The
        # dashboards used to read live objects, which meant whatever was in one
        # process; a stored projection survives a restart and two replicas
        # agree, and `rebuild_from` makes the model agree with the log again
        # after a projection changes.
        self.insights = InsightsService(open_unit=self.open_unit)
        for projected in INSIGHT_EVENTS:
            self.consumers.register(
                projected,
                group="insights",
                handler=self.insights.on_event,
            )

        # Desk operations (D01, #26). The fixer is the ordinary single-case
        # path, so a bulk fix cannot reach anything an operator could not do
        # one case at a time, and it does not get its own execution code.
        self.desk = DeskOps(
            fixer=ServiceCaseFixer(self.cases),
            cases=ServiceDeskCases(self.cases),
            open_unit=self.open_unit,
            clock=self.case_aggregate._now,
        )

        # The stateful turn pipeline (C01) driving the published flows (C02).
        # Conversation state is keyed by case, so a customer continues the same
        # conversation on any channel.
        #
        # The router reaches tools through FlowToolAdapter over the narrow MCP
        # view, which has no execute capability at all. A flow proposing is the
        # strongest thing that can happen here (I1).
        self.flows = load_flows(default_flow_dir(self.settings.flows_dir))
        # Intake: keyword rules first, the `extract` role only when they are
        # unsure (C04, #23). None configured means the rules answer alone.
        self.intake_assist = _intake_assist(self.roles, self.models)
        self.conversation = ConversationOrchestrator(
            flow=FlowRouter(
                self.flows,
                tools=FlowToolAdapter(self.mcp_view, answers=self.answers),
                # The bounded agent step (C03, #22). With no model configured
                # this is an agent with no planner, which leaves an agentic
                # state behaving exactly like a deterministic one.
                agent=BoundedAgent(_planner(self.roles, self.models)),
            ),
            audit=self.audit,
            open_unit=self.open_unit,
            intake_assist=self.intake_assist,
        )

    def _invalidate_answer_cache(self, event: Event) -> None:
        """Drop cached answers composed against an older corpus (K03).

        Housekeeping, not correctness: the corpus fingerprint is part of the
        cache key, so a stale entry is already unreachable. This stops a
        long-lived process carrying dead ones, and re-indexes the new chunks.
        """
        payload = event.payload()
        if not isinstance(payload, KnowledgePublishedV1):
            return
        self.retriever.index(self.knowledge.chunks_as_of(audience=Audience.STAFF))
        if payload.corpus_version:
            self.answers.on_knowledge_published(payload.corpus_version)

    def _open_zero_contact_case(self, event: Event) -> None:
        payload = event.payload()
        if not isinstance(payload, RiskDetectedV1) or payload.risk_type != "duplicate_reload":
            return
        if not payload.evidence_refs:
            return
        charge_ref = payload.evidence_refs[-1]
        account = self.world.account(event.subject)
        existing = next(
            (
                record
                for record in self.cases.all_cases()
                if record.subscriber_ref == event.subject
                and record.case.trigger is CaseTrigger.STREAM
                and record.case.charge_ref == charge_ref
            ),
            None,
        )
        case = (
            existing.case
            if existing is not None
            else self.cases.open_case(
                subscriber_ref=event.subject,
                msisdn_masked=account.masked if account is not None else "07X XXX XXXX",
                channel=Channel.SYSTEM,
                trigger=CaseTrigger.STREAM,
                language=account.language if account is not None else Language.EN,
                charge_ref=charge_ref,
            )
        )
        decision = self.cases.evaluate(case.case_id)
        if decision.outcome is not Outcome.AUTO_FIX:
            return
        record = self.cases.get(case.case_id)
        if not record.plans:
            self.cases.propose(case.case_id, created_by="clarity-stream-detector")

    def _complete_zero_contact_cases(self) -> None:
        """Execute persisted stream plans after their triggering event is consumed."""
        for record in self.cases.all_cases():
            if (
                record.case.trigger is not CaseTrigger.STREAM
                or record.decision is None
                or record.decision.outcome is not Outcome.AUTO_FIX
                or record.execution is not None
                or not record.plans
            ):
                continue
            plan = next(iter(record.plans.values()))
            self.cases.auto_fix(record.case_id, plan.plan_id)

    def deliver_events(self) -> None:
        """Publish whatever the last unit of work committed, then consume it.

        Called by the case module after a state change that produced events, so
        a synchronous API can still answer with what the event caused. A
        deployment runs the relay as its own process instead; the seam is the
        same either way.
        """
        # A consumer may atomically write a follow-on event, such as
        # receipt.issued after action.completed. Keep draining until no newly
        # committed outbox row remains. Domain operations called by a handler
        # also request delivery, so the guard leaves their rows for this active
        # loop instead of consuming the queue head recursively.
        with self._delivery_lock:
            if self._delivering_events:
                return
            self._delivering_events = True
            try:
                while True:
                    report = self.relay.run_once()
                    self.bus.drain()
                    if report.published == 0:
                        break
            finally:
                self._delivering_events = False
        # The stream handler persists the case and plan, then returns so the
        # risk event can leave its partition. Executing here lets the normal
        # action.completed consumer issue the receipt without re-entering the
        # still-active risk handler. Persisted plans also survive a restart.
        self._complete_zero_contact_cases()

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
