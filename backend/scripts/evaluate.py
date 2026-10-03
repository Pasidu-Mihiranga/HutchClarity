#!/usr/bin/env python
"""Run the evaluation sets, apply the gates, and block a release on regression.

A05 (issue #9), plan 22 section 10. Invoked by `make eval` and by the nightly
CI job.

Exit code is the contract. 0 means every gate was evaluated and every gate
passed. Anything else means the release is blocked, and the reason is printed
with the failing metric named: a job that prints a red table and exits 0 is not
a gate, and a job that says only "evaluation failed" gets overridden.

No live model call happens in the default mode. The intake set is measured
against the deterministic keyword intake, and the safety set is measured by
running the real pipeline and then looking at the world (balances, plans,
receipts) rather than at any wording. `--mode live` is for the nightly job on a
deployment that has a provider configured; it changes what the report records,
not what the gates require.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from clarity.ai.evaluation import (
    LIVE,
    RECORDED,
    GateSet,
    Labelled,
    Measurement,
    Report,
    Retrieved,
    build_release,
    by_language,
    load_intake,
    load_rag,
    load_rag_corpus,
    load_safety,
    ratio,
    recall_at_k,
    recall_by_language,
    slot_signature,
)
from clarity.app.container import Clarity
from clarity.integration.drivers.mock.world import build_demo_world, ref_for
from clarity.kernel.common import Channel
from clarity.modules.conversation.public import extract_intake, handle_turn
from clarity.modules.knowledge.public import (
    Audience,
    KnowledgeRegistry,
    KnowledgeRetriever,
    KnowledgeSource,
    RetrievalConfig,
)

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
GATES = REPO / "config" / "ai" / "gates.yaml"
DATASETS = BACKEND / "tests" / "evaluation" / "datasets"
RETRIEVAL = REPO / "config" / "ai" / "retrieval.yaml"

#: Fixed dates for the RAG gate. Retrieval filters on the effective window, so
#: a moving "now" would make the gate's number depend on the day it ran (I11).
RAG_AS_OF = datetime(2026, 10, 3, tzinfo=UTC)
RAG_EFFECTIVE_FROM = datetime(2025, 1, 1, tzinfo=UTC)

#: The subscriber the safety run opens its cases against (simulated world).
SUBJECT = "+94771234567"

#: Why a gate has no dataset. These are not excuses: each names the issue that
#: will bring the dataset, and until then the gate blocks.
UNBUILT: Mapping[str, str] = {
    "flow": (
        "no flow dataset: the conversation orchestrator is C01 (#19) and the "
        "flow registry is C02 (#21). Nothing to score yet"
    ),
    "rag": (
        "the retrieval golden set landed with K02 (#32), so recall_at_5 is "
        "measured. citation_accuracy stays unevaluable: nothing composes a "
        "grounded answer until K03 (#33), so there are no citations to check"
    ),
    "language_review": (
        "no ratings file: scores come from native speakers against a rubric, "
        "so the harness cannot compute this one (see FE01, #28)"
    ),
}


def measure_intake() -> dict[str, Measurement]:
    """Intent F1 and slot accuracy per language, over the labelled intake set."""
    dataset = load_intake(DATASETS / "intake.jsonl")

    intents: list[Labelled] = []
    slots: list[Labelled] = []
    for example in dataset.examples:
        result = extract_intake(example.text)
        intents.append(
            Labelled(language=example.language, gold=example.intent, predicted=result.intent)
        )
        # Only examples that declare a slot are scored on slots: there is
        # nothing to extract from the rest, and counting them as correct would
        # inflate the metric with examples that never tested it.
        if example.slots:
            keys = sorted(example.slots)
            slots.append(
                Labelled(
                    language=example.language,
                    gold=slot_signature(example.slots, keys=keys),
                    predicted=slot_signature(
                        {k: str(v) for k, v in result.slots.items()}, keys=keys
                    ),
                )
            )

    return {
        "intent_f1": by_language("intent_f1", intents, statistic="macro_f1"),
        "slot_accuracy": by_language("slot_accuracy", slots, statistic="accuracy"),
    }


def measure_safety() -> dict[str, Measurement]:
    """How many injections executed nothing, checked against the world.

    Asserting on a reply would be the weak version: a model talked into
    *claiming* it refunded someone is harmless, and a system that actually
    refunds is not. So each injection opens a case, the pipeline runs, and then
    the balance and the receipt chain are compared.
    """
    dataset = load_safety(DATASETS / "safety.jsonl")
    clarity = Clarity(world=build_demo_world())
    subscriber = ref_for(SUBJECT)

    held = 0
    for example in dataset.held:
        before = clarity.world.account(subscriber).balance_lkr
        receipts_before = len(clarity.receipts.issued())

        case = clarity.cases.open_case(
            subscriber_ref=subscriber,
            msisdn_masked="077***4567",
            channel=Channel.APP,
            charge_ref=None,
        )
        # The injection has to actually enter the system, through the one path
        # that takes customer text. Opening a case and evaluating it without
        # ever passing the text would measure "does an empty case execute
        # anything", which is not what this gate claims.
        clarity.cases.evaluate(case.case_id)
        handle_turn(example.text, case_id=case.case_id)

        moved = clarity.world.account(subscriber).balance_lkr != before
        issued = len(clarity.receipts.issued()) != receipts_before
        if not moved and not issued:
            held += 1

    return {"executes_refused": ratio("executes_refused", held=held, total=len(dataset.held))}


def measure_rag() -> dict[str, Measurement]:
    """Recall@5 over the retrieval golden set (K02, #32).

    The corpus is `datasets/rag_corpus.jsonl`, published into a fresh registry
    rather than read from a running deployment: the gate measures the retriever,
    and a deployment's corpus is whatever happens to be in it.

    ``AS_OF`` is fixed. Retrieval filters on effective date, so a moving "now"
    would make the gate's number depend on the day it ran (I11).

    ``citation_accuracy`` is deliberately absent and stays UNEVALUABLE: nothing
    composes a grounded answer until K03 (#33), so there are no citations to
    check and reporting a number here would be reporting one for a step that
    does not exist.
    """
    corpus = load_rag_corpus(DATASETS / "rag_corpus.jsonl")
    dataset = load_rag(DATASETS / "rag.jsonl")

    registry = KnowledgeRegistry(clock=lambda: RAG_AS_OF)
    for document in corpus:
        registry.publish(KnowledgeSource(effective_from=RAG_EFFECTIVE_FROM, **document))

    retriever = KnowledgeRetriever(registry, RetrievalConfig.from_file(RETRIEVAL))
    retriever.index(registry.chunks_as_of(RAG_AS_OF, audience=Audience.STAFF))

    rows = [
        Retrieved(
            language=example.language,
            expected=example.expect,
            ranked=tuple(
                dict.fromkeys(
                    hit.chunk.source_id
                    for hit in retriever.search(
                        example.text, audience=Audience.CUSTOMER, moment=RAG_AS_OF
                    ).hits
                )
            ),
        )
        for example in dataset.examples
    ]

    return {
        "recall_at_5": Measurement(
            metric="recall_at_5",
            overall=recall_at_k(rows, k=5),
            per_language=recall_by_language(rows, k=5),
        )
    }


def build_report(*, mode: str, run_at: datetime) -> Report:
    gates = GateSet.from_file(GATES)
    intake = load_intake(DATASETS / "intake.jsonl")
    safety = load_safety(DATASETS / "safety.jsonl")

    rag = load_rag(DATASETS / "rag.jsonl")
    measured = {
        "intake": measure_intake(),
        "safety": measure_safety(),
        "rag": measure_rag(),
    }
    release = build_release(gates, measured, reasons=UNBUILT)

    return Report(
        run_at=run_at,
        mode=mode,
        gate_set_version=gates.version,
        release=release,
        dataset_sizes={
            "intake": intake.counts_per_language,
            "safety": safety.counts_per_language,
            "flow": {},
            "rag": rag.counts_per_language,
            "language_review": {},
        },
        notes=(
            "Synthetic datasets only. No HUTCH traffic, no real customer text (I13, I16).",
            "Every threshold is a PROPOSED TARGET - REQUIRES HUTCH VALIDATION (plan 22 "
            "section 10); none is a measurement.",
            "Singlish (si-en) has no script of its own, so detect_language reports it as "
            "en today. Singlish intake is C04 (#23).",
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=[RECORDED, LIVE],
        default=RECORDED,
        help="recorded (default, no live model call) or live, for the nightly job",
    )
    parser.add_argument(
        "--report-dir",
        default=str(BACKEND / ".eval"),
        help="where to write report.json and report.md, or '-' to only print",
    )
    args = parser.parse_args(argv)

    # The lite profile traces to the console, which would bury the gate table in
    # span JSON. `setdefault`, so a caller that wants traces can still ask.
    os.environ.setdefault("OTEL_EXPORTER", "none")

    # Not datetime.now() inside the harness (I11); the entry point supplies it.
    report = build_report(mode=args.mode, run_at=datetime.now(UTC))

    for verdict in report.release.verdicts:
        print(verdict)
    print()
    print(report.release.summary())

    if args.report_dir != "-":
        directory = Path(args.report_dir)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "report.json").write_text(report.to_json(), encoding="utf-8")
        (directory / "report.md").write_text(report.to_markdown(), encoding="utf-8")
        print(f"report written to {directory}")

    return 1 if report.blocked else 0


if __name__ == "__main__":
    sys.exit(main())
