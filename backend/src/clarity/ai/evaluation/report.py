"""The report artefact a run leaves behind (A05, plan 22 section 10).

One run, one file, in two forms: JSON for a later run to diff against, and
Markdown for the person reading the CI job.

The report records what was **not** measured as prominently as what was, because
the number a reader most needs is not the score, it is whether the score covers
the thing they are about to ship. A report listing four green gates is
misleading if two more existed and were skipped, so unevaluable gates appear in
the same table as the rest.

Time is a parameter, never ``datetime.now()`` (I11): a report has to be
reproducible from a recorded run, and a timestamp read from the wall clock makes
two runs of the same inputs differ.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from clarity.ai.evaluation.gates import GateStatus, Release

#: How a run obtained its model answers. Recorded is the only mode CI uses on a
#: pull request (A02); live runs nightly, and only where a provider is set up.
RECORDED = "recorded"
LIVE = "live"


@dataclass(frozen=True)
class Report:
    """A single evaluation run: when, how, over what, and what it concluded."""

    run_at: datetime
    mode: str
    gate_set_version: int
    release: Release
    dataset_sizes: dict[str, dict[str, int]]
    notes: tuple[str, ...] = ()

    @property
    def blocked(self) -> bool:
        return self.release.blocked

    def to_document(self) -> dict[str, Any]:
        return {
            "run_at": self.run_at.isoformat(),
            "mode": self.mode,
            "gate_set_version": self.gate_set_version,
            "release": {
                "blocked": self.release.blocked,
                "summary": self.release.summary(),
                "failing_metrics": list(self.release.failing_metrics),
            },
            "dataset_sizes": self.dataset_sizes,
            "verdicts": [
                {
                    "gate": verdict.gate,
                    "metric": verdict.metric,
                    "language": verdict.language,
                    "status": verdict.status.value,
                    "required": verdict.required,
                    "observed": verdict.observed,
                    "sample_size": verdict.sample_size,
                    "reason": verdict.reason,
                }
                for verdict in self.release.verdicts
            ],
            "notes": list(self.notes),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_document(), indent=2, ensure_ascii=False) + "\n"

    def to_markdown(self) -> str:
        lines = [
            "# Evaluation report",
            "",
            f"- Run at: {self.run_at.isoformat()}",
            f"- Mode: {self.mode} "
            + ("(recorded responses, no live calls)" if self.mode == RECORDED else "(live models)"),
            f"- Gate set: version {self.gate_set_version} (`config/ai/gates.yaml`)",
            f"- **{self.release.summary()}**",
            "",
            "Every threshold below is a PROPOSED TARGET - REQUIRES HUTCH VALIDATION",
            "(plan 22 section 10). No figure here is a measurement of HUTCH traffic.",
            "",
            "## Gates",
            "",
            "| Gate | Metric | Language | Status | Observed | Required | n | Note |",
            "|---|---|---|---|---|---|---|---|",
        ]
        for verdict in self.release.verdicts:
            observed = "-" if verdict.observed is None else f"{verdict.observed:.3f}"
            marker = "ok" if verdict.status is GateStatus.PASS else "**blocks**"
            lines.append(
                f"| {verdict.gate} | {verdict.metric} | {verdict.language or 'all'} "
                f"| {verdict.status.value} ({marker}) | {observed} "
                f"| {verdict.required:.3f} | {verdict.sample_size} | {verdict.reason} |"
            )

        if self.dataset_sizes:
            lines += ["", "## Dataset sizes", ""]
            lines += ["| Dataset | Language | Examples |", "|---|---|---|"]
            for dataset, counts in sorted(self.dataset_sizes.items()):
                if not counts:
                    lines.append(f"| {dataset} | - | 0 (not built) |")
                    continue
                for language, count in sorted(counts.items()):
                    lines.append(f"| {dataset} | {language} | {count} |")

        if self.notes:
            lines += ["", "## Notes", ""] + [f"- {note}" for note in self.notes]
        return "\n".join(lines) + "\n"


__all__ = ["LIVE", "RECORDED", "Report"]
