"""clarity-api entrypoint — composes modules into a FastAPI app."""

from __future__ import annotations

from clarity.platform.app import AppBuilder
from clarity.platform.audit.ledger import AuditLedger
from clarity.platform.authz.policy import PythonPolicy
from clarity.platform.config.resolver import ConfigResolver
from clarity.platform.config.settings import get_settings
from clarity.platform.idempotency.store import MemoryIdempotencyStore
from clarity.platform.messaging.jobs import JobQueue
from clarity.platform.messaging.outbox import InMemoryBus
from clarity.platform.observability.otel import setup_otel
from clarity.platform.vault.tokens import TokenVault


def create_app() -> object:
    settings = get_settings()
    setup_otel(exporter=settings.otel_exporter, service_name="clarity-api")
    builder = AppBuilder(profile=settings.profile.value, settings=settings)

    builder.provide(TokenVault, TokenVault(hmac_key=settings.subscriber_key_bytes))
    builder.provide(AuditLedger, AuditLedger())
    builder.provide(PythonPolicy, PythonPolicy())
    builder.provide(ConfigResolver, ConfigResolver())
    builder.provide(InMemoryBus, InMemoryBus())
    builder.provide(JobQueue, JobQueue())
    builder.provide(MemoryIdempotencyStore, MemoryIdempotencyStore())

    # Modules register themselves. Import lazily so empty stubs still load.
    from clarity.modules.actions.module import ActionsModule
    from clarity.modules.autopsy.module import AutopsyModule
    from clarity.modules.case.module import CaseModule
    from clarity.modules.content.module import ContentModule
    from clarity.modules.conversation.module import ConversationModule
    from clarity.modules.customer.module import CustomerModule
    from clarity.modules.decision.module import DecisionModule
    from clarity.modules.deskops.module import DeskOpsModule
    from clarity.modules.detection.module import DetectionModule
    from clarity.modules.foresight.module import ForesightModule
    from clarity.modules.governance.module import GovernanceModule
    from clarity.modules.iam.module import IamModule
    from clarity.modules.insights.module import InsightsModule
    from clarity.modules.knowledge.module import KnowledgeModule
    from clarity.modules.notifications.module import NotificationsModule
    from clarity.modules.proactive.module import ProactiveModule
    from clarity.modules.receipts.module import ReceiptsModule
    from clarity.modules.reconciliation.module import ReconciliationModule
    from clarity.modules.timeline.module import TimelineModule

    for module_cls in (
        IamModule,
        CustomerModule,
        CaseModule,
        TimelineModule,
        DetectionModule,
        DecisionModule,
        ActionsModule,
        ReceiptsModule,
        ReconciliationModule,
        ConversationModule,
        NotificationsModule,
        KnowledgeModule,
        ProactiveModule,
        GovernanceModule,
        DeskOpsModule,
        AutopsyModule,
        ForesightModule,
        InsightsModule,
        ContentModule,
    ):
        builder.register_module(module_cls())

    return builder.build_fastapi(title="Hutch Clarity")


app = create_app()
