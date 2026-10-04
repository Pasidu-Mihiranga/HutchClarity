"""The transcript is a record, never memory (A4, ADR-0040).

Plan 22 section 9 forbids "long-term memory of conversation content", and
`state.py` cites it as the reason conversation state holds flow, slots and a
turn counter and nothing else. ADR-0040 keeps a transcript anyway, on one
argument: the thing section 9 is protecting against is content that accumulates
and then *steers a later answer*. A record that nothing in the turn pipeline
reads back is not that, any more than the audit trail is.

That argument is only worth anything if it stays true, and a comment saying
"never read this back" is exactly the kind of promise that quietly stops being
kept. So it is a test.

What this file asserts:

1. Nothing in the turn pipeline reads a transcript. `transcript.py` may be
   imported to *write* (the orchestrator does, once, after the reply is final),
   but `for_case` must not be called from intake, composition, retrieval, the
   router, the agent step or the orchestrator.
2. `transcript.py` imports nothing from the modules that decide a turn, so it
   cannot grow a back channel.
"""

from __future__ import annotations

import ast
from pathlib import Path

MODULE = Path(__file__).resolve().parents[2] / "src" / "clarity" / "modules" / "conversation"

#: Files that decide what a turn says. None of them may read a transcript.
PIPELINE = (
    "orchestrator.py",
    "service.py",
    "intake.py",
    "router.py",
    "agent.py",
    "flows.py",
    "suggestions.py",
    "verify.py",
)

#: The read method. Writing is allowed; reading back into a turn is not.
READERS = {"for_case"}


def _calls(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute):
                found.add(func.attr)
            elif isinstance(func, ast.Name):
                found.add(func.id)
    return found


def test_no_part_of_the_turn_pipeline_reads_a_transcript() -> None:
    offenders = {
        name: sorted(_calls(MODULE / name) & READERS)
        for name in PIPELINE
        if (MODULE / name).exists() and _calls(MODULE / name) & READERS
    }

    assert offenders == {}, (
        "a transcript was read inside the turn pipeline: that turns a record "
        "into memory and breaks the argument ADR-0040 rests on. Read it from "
        "an interface (the customer's own history, the desk's handoff view), "
        f"never from a turn. Offenders: {offenders}"
    )


def test_the_transcript_module_cannot_reach_the_deciders() -> None:
    """No import back into intake, flows or the orchestrator.

    Without this the module could grow a helper that summarises a transcript
    "just for the prompt", which is the same thing by another name.
    """
    tree = ast.parse((MODULE / "transcript.py").read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)

    forbidden = sorted(
        name
        for name in imported
        if name.startswith("clarity.modules.conversation.")
        and not name.endswith(("transcript", "state"))
    )

    assert forbidden == [], (
        "transcript.py imported part of the turn pipeline; it holds records and "
        f"must not reach what decides a turn: {forbidden}"
    )


def test_the_orchestrator_writes_the_transcript_after_the_reply_is_final() -> None:
    """Ordering, because it is the other half of the argument.

    Writing before verification would store a reply the customer never saw, and
    a transcript that disagrees with what was said is worse than none: it is
    the document a dispute would be settled with.
    """
    source = (MODULE / "orchestrator.py").read_text(encoding="utf-8")

    verified = source.index("verifier = ")
    remembered = source.index("self._remember(")

    assert verified < remembered, (
        "the transcript is written before the reply is verified, so a "
        "substituted reply would be recorded as the original"
    )
