"""The `/v1/foresight` contract (C4, F06).

Black-box over HTTP, like the rest of the acceptance suite. Three groups:

1. **The route is `/v1/foresight`, not `/v1/simulation`.** Plan 10 section 250
   says the latter; everything else, including the module, says foresight. Plan
   10 is a chapter 01-17 document and therefore lowest precedence, so the plan
   is what changed. A test pins the choice so the contradiction cannot come
   back quietly.
2. **The permissions, and the separation between them.** `product` may draft and
   run; it may **not** record what a launch actually produced. The person who
   wants the calibration gate open must not be the one writing the evidence that
   opens it.
3. **Idempotency.** A repeated run request returns the original run, including
   its original outcome. The risk here is a double *finding*, not a double
   charge.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.acceptance.conftest import bearer, staff_token

_SCENARIO = {
    "name": "Retire the 10GB pack",
    "change_type": "pack_retired",
    "effective_date": "2027-10-01",
}


def product(api: TestClient) -> dict[str, str]:
    return bearer(staff_token(api, "pm:anusha", ["product"], step_up=False))


def cx(api: TestClient) -> dict[str, str]:
    return bearer(staff_token(api, "cx:ruwan", ["cx_engineer"], step_up=False))


def agent(api: TestClient) -> dict[str, str]:
    return bearer(staff_token(api, "agent:nadeesha", ["agent"], step_up=False))


def drafted(api: TestClient) -> dict[str, object]:
    made = api.post("/v1/foresight/scenarios", json=_SCENARIO, headers=product(api))
    assert made.status_code == 201, made.text
    return dict(made.json())


def ran(api: TestClient, version_id: str, key: str = "run-key-00001") -> dict[str, object]:
    answer = api.post(
        "/v1/foresight/runs",
        json={"scenario_version_id": version_id},
        headers={**product(api), "Idempotency-Key": key},
    )
    assert answer.status_code == 202, answer.text
    return dict(answer.json())


# --------------------------------------------------------------------------- #
# The path
# --------------------------------------------------------------------------- #


def test_the_resource_is_foresight_not_simulation(api: TestClient):
    """Plan 10 section 250 said `/v1/simulation`. Everything else said foresight."""
    paths = api.get("/openapi.json").json()["paths"]

    assert any(path.startswith("/v1/foresight") for path in paths)
    assert not any(path.startswith("/v1/simulation") for path in paths)


# --------------------------------------------------------------------------- #
# Deny by default (I9)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/v1/foresight/scenarios"),
        ("get", "/v1/foresight/runs"),
        ("get", "/v1/foresight/launches"),
        ("get", "/v1/foresight/backtests"),
        ("get", "/v1/foresight/calibration"),
        ("get", "/v1/foresight/spikes"),
        ("post", "/v1/foresight/scenarios"),
        ("post", "/v1/foresight/runs"),
        ("post", "/v1/foresight/launches"),
        ("post", "/v1/foresight/backtests"),
    ],
)
def test_every_route_refuses_an_anonymous_caller(api: TestClient, method: str, path: str):
    answer = api.request(method.upper(), path, json={} if method == "post" else None)

    assert answer.status_code in {401, 403}, answer.text


def test_a_role_without_foresight_permissions_is_refused(api: TestClient):
    answer = api.get("/v1/foresight/scenarios", headers=agent(api))

    assert answer.status_code == 403


# --------------------------------------------------------------------------- #
# Separation of duties: who may record the evidence
# --------------------------------------------------------------------------- #


def test_product_may_draft_and_run(api: TestClient):
    version = drafted(api)

    assert version["version"] == 1
    assert ran(api, str(version["version_id"]))["status"] == "succeeded"


def test_product_may_not_record_what_a_launch_actually_produced(api: TestClient):
    """The whole point of the permission split.

    Recorded outcomes are the only thing that can move a backtest to
    CALIBRATED, and product is the role that wants the gate open.
    """
    version = drafted(api)

    answer = api.post(
        "/v1/foresight/launches",
        json={"scenario_version_id": version["version_id"], "provenance": "synthetic"},
        headers=product(api),
    )

    assert answer.status_code == 403


def test_cx_may_record_a_launch_but_not_draft_a_scenario(api: TestClient):
    version = drafted(api)

    recorded = api.post(
        "/v1/foresight/launches",
        json={"scenario_version_id": version["version_id"], "provenance": "synthetic"},
        headers=cx(api),
    )
    drafting = api.post("/v1/foresight/scenarios", json=_SCENARIO, headers=cx(api))

    assert recorded.status_code == 201, recorded.text
    assert drafting.status_code == 403


def test_recording_a_real_launch_is_refused(api: TestClient):
    """C6 owns the capability and the evidence check; until then, 403."""
    version = drafted(api)

    answer = api.post(
        "/v1/foresight/launches",
        json={
            "scenario_version_id": version["version_id"],
            "provenance": "real",
            "evidence_ref": "HUTCH-LAUNCH-1",
        },
        headers=cx(api),
    )

    assert answer.status_code == 403
    assert "capability" in answer.json()["detail"]


def test_a_refused_real_launch_stores_nothing(api: TestClient):
    version = drafted(api)
    api.post(
        "/v1/foresight/launches",
        json={"scenario_version_id": version["version_id"], "provenance": "real"},
        headers=cx(api),
    )

    listed = api.get("/v1/foresight/launches", headers=cx(api))

    assert listed.json()["launches"] == []


# --------------------------------------------------------------------------- #
# Scenarios and versions
# --------------------------------------------------------------------------- #


def test_a_scenario_id_is_stable_and_a_revision_keeps_it(api: TestClient):
    first = drafted(api)

    second = api.post(
        f"/v1/foresight/scenarios/{first['scenario_id']}/versions",
        json={**_SCENARIO, "name": "Retire the 10GB pack, phased"},
        headers=product(api),
    )

    assert second.status_code == 201, second.text
    body = second.json()
    assert body["scenario_id"] == first["scenario_id"]
    assert body["version"] == 2
    assert body["supersedes"] == first["version_id"]


def test_both_versions_stay_readable(api: TestClient):
    """A stored run cites a version, so the version it cites must survive."""
    first = drafted(api)
    api.post(
        f"/v1/foresight/scenarios/{first['scenario_id']}/versions",
        json={**_SCENARIO, "severity": "2.0"},
        headers=product(api),
    )

    read = api.get(f"/v1/foresight/scenarios/{first['scenario_id']}", headers=product(api))

    versions = read.json()["versions"]
    assert [v["version"] for v in versions] == [1, 2]
    assert versions[0]["severity"] == "1.0"
    assert versions[1]["severity"] == "2.0"


def test_revising_a_scenario_nobody_drafted_is_a_404(api: TestClient):
    answer = api.post(
        "/v1/foresight/scenarios/SIM-nothing/versions", json=_SCENARIO, headers=product(api)
    )

    assert answer.status_code == 404


def test_an_unknown_change_type_is_refused_rather_than_predicting_nothing(api: TestClient):
    """A missing catalogue and a misspelled change type are different problems."""
    answer = api.post(
        "/v1/foresight/scenarios",
        json={**_SCENARIO, "change_type": "not_a_change_type"},
        headers=product(api),
    )

    assert answer.status_code == 422


def test_an_effective_date_is_required(api: TestClient):
    body = {k: v for k, v in _SCENARIO.items() if k != "effective_date"}

    answer = api.post("/v1/foresight/scenarios", json=body, headers=product(api))

    assert answer.status_code == 422


def test_listing_scenarios_gives_the_latest_version_of_each(api: TestClient):
    first = drafted(api)
    api.post(
        f"/v1/foresight/scenarios/{first['scenario_id']}/versions",
        json={**_SCENARIO, "name": "revised"},
        headers=product(api),
    )

    listed = api.get("/v1/foresight/scenarios", headers=product(api)).json()["scenarios"]

    assert len(listed) == 1
    assert listed[0]["version"] == 2


# --------------------------------------------------------------------------- #
# Runs: 202, a poll URL, and idempotency
# --------------------------------------------------------------------------- #


def test_a_run_answers_202_with_a_poll_url(api: TestClient):
    version = drafted(api)

    answer = api.post(
        "/v1/foresight/runs",
        json={"scenario_version_id": version["version_id"]},
        headers={**product(api), "Idempotency-Key": "run-key-00001"},
    )

    assert answer.status_code == 202
    assert answer.headers["Location"] == f"/v1/foresight/runs/{answer.json()['run_id']}"
    assert answer.json()["poll_url"] == answer.headers["Location"]


def test_the_idempotency_key_is_required_not_optional(api: TestClient):
    """I8. Two runs of one scenario, reported twice, is a double finding."""
    version = drafted(api)

    answer = api.post(
        "/v1/foresight/runs",
        json={"scenario_version_id": version["version_id"]},
        headers=product(api),
    )

    assert answer.status_code == 422


def test_a_repeated_request_returns_the_original_run(api: TestClient):
    version = drafted(api)
    first = ran(api, str(version["version_id"]), key="same-key-0001")

    second = api.post(
        "/v1/foresight/runs",
        json={"scenario_version_id": version["version_id"]},
        headers={**product(api), "Idempotency-Key": "same-key-0001"},
    )

    assert second.status_code == 202
    assert second.json()["run_id"] == first["run_id"]
    assert second.json()["replayed"] is True
    assert len(api.get("/v1/foresight/runs", headers=product(api)).json()["runs"]) == 1


def test_a_repeat_carries_the_original_outcome(api: TestClient):
    """D1: a duplicate gets the original outcome, not a fresh queued run."""
    version = drafted(api)
    first = ran(api, str(version["version_id"]), key="same-key-0002")

    second = api.post(
        "/v1/foresight/runs",
        json={"scenario_version_id": version["version_id"]},
        headers={**product(api), "Idempotency-Key": "same-key-0002"},
    ).json()

    assert second["status"] == "succeeded"
    assert second["report_id"] == first["report_id"]


def test_a_different_key_starts_a_second_run(api: TestClient):
    version = drafted(api)
    ran(api, str(version["version_id"]), key="key-one-0001")
    ran(api, str(version["version_id"]), key="key-two-0002")

    assert len(api.get("/v1/foresight/runs", headers=product(api)).json()["runs"]) == 2


def test_polling_a_run_returns_its_report(api: TestClient):
    version = drafted(api)
    run = ran(api, str(version["version_id"]))

    polled = api.get(f"/v1/foresight/runs/{run['run_id']}", headers=product(api))

    report = polled.json()["report"]
    assert report is not None
    assert report["predictions"]
    assert report["scenario_id"] == version["scenario_id"]


def test_a_report_states_it_read_no_individual_data(api: TestClient):
    """Deck S8: Foresight on aggregates only."""
    version = drafted(api)
    run = ran(api, str(version["version_id"]))

    report = api.get(f"/v1/foresight/runs/{run['run_id']}", headers=product(api)).json()["report"]

    assert "no individual" in report["basis"].lower()


def test_a_report_is_not_decision_ready_without_a_calibration(api: TestClient):
    """Plan 02 section 3.4: no launch decision rests on an uncalibrated model."""
    version = drafted(api)
    run = ran(api, str(version["version_id"]))

    report = api.get(f"/v1/foresight/runs/{run['run_id']}", headers=product(api)).json()["report"]

    assert report["decision_ready"] is False
    assert any("not backtested" in c.lower() for c in report["caveats"])


def test_a_prediction_is_a_band_never_a_complaint_count(api: TestClient):
    version = drafted(api)
    run = ran(api, str(version["version_id"]))

    report = api.get(f"/v1/foresight/runs/{run['run_id']}", headers=product(api)).json()["report"]

    for prediction in report["predictions"]:
        assert prediction["band"] in {"low", "medium", "high"}
        assert "count" not in prediction
        assert "complaints" not in prediction


def test_running_a_scenario_version_nobody_drafted_is_a_404(api: TestClient):
    answer = api.post(
        "/v1/foresight/runs",
        json={"scenario_version_id": "SCV-nothing"},
        headers={**product(api), "Idempotency-Key": "missing-00001"},
    )

    assert answer.status_code == 404


def test_polling_a_run_nobody_requested_is_a_404(api: TestClient):
    answer = api.get("/v1/foresight/runs/RUN-nothing", headers=product(api))

    assert answer.status_code == 404


# --------------------------------------------------------------------------- #
# Outcomes, backtests and calibration
# --------------------------------------------------------------------------- #


def test_an_outcome_is_recorded_against_a_launch(api: TestClient):
    version = drafted(api)
    launch = api.post(
        "/v1/foresight/launches",
        json={"scenario_version_id": version["version_id"], "provenance": "synthetic"},
        headers=cx(api),
    ).json()

    answer = api.post(
        f"/v1/foresight/launches/{launch['launch_id']}/outcomes",
        json={"theme": "pack sunset confusion", "segment": "students", "band": "high"},
        headers=cx(api),
    )

    assert answer.status_code == 201, answer.text
    assert answer.json()["recorded_by"] == "cx:ruwan"


def test_an_unknown_band_is_refused(api: TestClient):
    version = drafted(api)
    launch = api.post(
        "/v1/foresight/launches",
        json={"scenario_version_id": version["version_id"], "provenance": "synthetic"},
        headers=cx(api),
    ).json()

    answer = api.post(
        f"/v1/foresight/launches/{launch['launch_id']}/outcomes",
        json={"theme": "t", "segment": "s", "band": "catastrophic"},
        headers=cx(api),
    )

    assert answer.status_code == 422


def test_calibration_is_a_404_before_any_backtest_has_run(api: TestClient):
    """Different from "not calibrated", and only one of them is measured."""
    answer = api.get("/v1/foresight/calibration", headers=product(api))

    assert answer.status_code == 404


def test_a_synthetic_backtest_never_claims_calibration(api: TestClient):
    """I16: a launch we authored cannot validate the model that predicted it."""
    version = drafted(api)
    launch = api.post(
        "/v1/foresight/launches",
        json={"scenario_version_id": version["version_id"], "provenance": "synthetic"},
        headers=cx(api),
    ).json()
    api.post(
        f"/v1/foresight/launches/{launch['launch_id']}/outcomes",
        json={"theme": "pack sunset confusion", "segment": "students", "band": "high"},
        headers=cx(api),
    )

    backtest = api.post("/v1/foresight/backtests", headers=product(api))

    body = backtest.json()
    assert backtest.status_code == 201, backtest.text
    assert body["calibrated"] is False
    assert body["status"] == "not_calibrated"
    assert body["real_launches"] == 0
    assert any("validates nothing" in c.lower() for c in body["caveats"])


def test_a_backtest_with_nothing_comparable_reports_no_error_not_a_perfect_one(
    api: TestClient,
):
    """A 0.000 over zero pairs would read as a flawless model."""
    backtest = api.post("/v1/foresight/backtests", headers=product(api)).json()

    assert backtest["compared"] == 0
    assert backtest["mean_absolute_band_error"] is None
    assert backtest["exact_band_rate"] is None
    assert "not measurable" in backtest["summary"]


def test_the_latest_calibration_is_readable_once_a_backtest_has_run(api: TestClient):
    api.post("/v1/foresight/backtests", headers=product(api))

    answer = api.get("/v1/foresight/calibration", headers=product(api))

    assert answer.status_code == 200
    assert answer.json()["status"] == "not_calibrated"


def test_a_later_run_rests_on_the_stored_calibration(api: TestClient):
    version = drafted(api)
    api.post("/v1/foresight/backtests", headers=product(api))
    run = ran(api, str(version["version_id"]))

    report = api.get(f"/v1/foresight/runs/{run['run_id']}", headers=product(api)).json()["report"]

    assert report["backtested"] is False
    assert any("backtest" in c.lower() for c in report["caveats"])


def test_spikes_are_empty_until_the_radar_fills_them(api: TestClient):
    """C5 supplies the detector. The route exists so the console can poll it."""
    answer = api.get("/v1/foresight/spikes", headers=product(api))

    assert answer.status_code == 200
    assert answer.json()["spikes"] == []
