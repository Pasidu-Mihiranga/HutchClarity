"""clarity-worker entrypoint — runs registered JobQueue jobs.

Lite profile: in-process ``JobQueue``. Full profile binds Procrastinate at the
composition root; this module stays thin and only loads / runs jobs.
"""

from __future__ import annotations

import logging

from clarity.platform.app import AppBuilder
from clarity.platform.config.settings import get_settings
from clarity.platform.messaging.jobs import JobQueue
from clarity.platform.observability.otel import setup_otel

logger = logging.getLogger("clarity.worker")


def create_worker() -> JobQueue:
    settings = get_settings()
    setup_otel(exporter=settings.otel_exporter, service_name="clarity-worker")
    builder = AppBuilder(profile=settings.profile.value, settings=settings)
    queue = JobQueue()
    builder.provide(JobQueue, queue)

    # Modules that register cron jobs do so via JobQueue when composed.
    from clarity.modules.reconciliation.module import ReconciliationModule

    builder.register_module(ReconciliationModule())
    return queue


def main(job_name: str | None = None) -> list[str]:
    """Run one named job, or all registered jobs when ``job_name`` is None."""
    logging.basicConfig(level=logging.INFO)
    queue = create_worker()
    if job_name:
        queue.run(job_name)
        logger.info("ran job %s", job_name)
        return [job_name]
    ran = queue.run_all()
    logger.info("ran jobs: %s", ran)
    return ran


if __name__ == "__main__":
    main()
