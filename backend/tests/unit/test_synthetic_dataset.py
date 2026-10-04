"""DATA01 deterministic synthetic telecom corpus."""

from clarity.integration.drivers.mock.synthetic_dataset import (
    CauseFamily,
    generate_synthetic_dataset,
)


def test_same_seed_and_configuration_are_identical():
    assert generate_synthetic_dataset(count=100, seed=7) == generate_synthetic_dataset(
        count=100, seed=7
    )


def test_every_cause_and_unknown_are_covered():
    dataset = generate_synthetic_dataset(count=190)
    assert {row.ground_truth_issue_family for row in dataset.complaints} == {
        cause.value for cause in CauseFamily
    }


def test_every_record_is_synthetic_and_fictional():
    dataset = generate_synthetic_dataset(count=100)
    assert dataset.provenance == "SYNTHETIC"
    assert all(
        row.synthetic and row.synthetic_customer_id.startswith("SYN-CUST-")
        for row in dataset.complaints
    )
    assert all(event.synthetic for event in dataset.events)


def test_multilingual_duplicates_repeats_and_partial_evidence_exist():
    dataset = generate_synthetic_dataset(count=200)
    assert {"en", "si", "ta", "si-en", "ta-en"} <= {row.language for row in dataset.complaints}
    assert len({row.text for row in dataset.complaints}) < len(dataset.complaints)
    assert any(row.repeat_contact_count > 0 for row in dataset.complaints)
    assert any(not row.underlying_event_refs for row in dataset.complaints)


def test_evidence_is_separate_and_agrees_with_ground_truth():
    dataset = generate_synthetic_dataset(count=100)
    events = {event.event_ref: event for event in dataset.events}
    for complaint in dataset.complaints:
        for ref in complaint.underlying_event_refs:
            assert events[ref].fact == complaint.ground_truth_issue_family
            assert events[ref].synthetic_customer_id == complaint.synthetic_customer_id


def test_foresight_derivative_contains_aggregates_only():
    aggregate = generate_synthetic_dataset(count=100).foresight_aggregates[0]
    assert not hasattr(aggregate, "synthetic_customer_id")
    assert not hasattr(aggregate, "text")
    assert not hasattr(aggregate, "complaint_id")
