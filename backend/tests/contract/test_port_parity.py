"""Parity suites: one contract per port, every driver must pass it.

Adopted from the alternative design's ADR-0014. The problem it solves is the
one that bites at integration time: a mock drifts from the real system, every
test stays green, and the gap only appears when a HUTCH sandbox is connected.

Each suite below is the contract. A HUTCH sandbox or production driver is added
to the driver list and must pass the same assertions unchanged. If it cannot,
that is a finding about the integration, found here rather than in week nine.

The drivers listed today are the mock ones, so these suites are also a
regression net for behaviour the core relies on.
"""

from __future__ import annotations

import base64
import json
import os
from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient

from clarity.contracts.decision import ActionType
from clarity.contracts.receipt import RecurrenceResult
from clarity.integration.drivers.http import HttpCommandAdapter, HttpReadAdapter
from clarity.integration.drivers.mock.adapters import MockCommandAdapter, MockReadAdapter
from clarity.integration.drivers.mock.http_service import create_hutch_sim_app
from clarity.integration.drivers.mock.recurrence import MockRecurrenceProbe
from clarity.integration.drivers.mock.world import DEMO_NOW, build_demo_world, ref_for
from clarity.integration.ports import (
    AdapterError,
    Command,
    CommandPort,
    Completeness,
    ReadPort,
)
from clarity.kernel.common import EventSource
from clarity.modules.receipts.openbao import OpenBaoSigningService
from clarity.modules.receipts.recurrence import RecurrenceProbe, run_check
from clarity.modules.receipts.signing import DevSigningService, SigningService, verify_signature

DILANI = "+94771234567"


# --------------------------------------------------------------------------- #
# ReadPort
# --------------------------------------------------------------------------- #


#: Every read driver. A HUTCH sandbox driver joins this list unchanged.
def _http_read_driver(source: EventSource) -> ReadPort:
    world = build_demo_world()
    client = TestClient(create_hutch_sim_app(world))
    return HttpReadAdapter(source, "http://hutch-sim.test", client=client)


READ_DRIVERS: list[tuple[str, Callable[[EventSource], ReadPort]]] = [
    ("mock", lambda source: MockReadAdapter(source, build_demo_world())),
    ("http", _http_read_driver),
]


@pytest.fixture(params=[name for name, _ in READ_DRIVERS], ids=lambda n: f"read:{n}")
def read_driver(request) -> Callable[[EventSource], ReadPort]:
    return dict(READ_DRIVERS)[request.param]


class TestReadPortParity:
    """What every read driver must do, whatever it reads from."""

    def test_it_answers_for_every_source(self, read_driver):
        for source in EventSource:
            port = read_driver(source)
            result = port.read(ref_for(DILANI), DEMO_NOW - timedelta(days=90), DEMO_NOW)
            assert result.source is source

    def test_events_fall_inside_the_requested_window(self, read_driver):
        port = read_driver(EventSource.CHARGING)
        window_from, window_to = DEMO_NOW - timedelta(days=90), DEMO_NOW

        result = port.read(ref_for(DILANI), window_from, window_to)

        assert all(window_from <= e.occurred_at <= window_to for e in result.events)

    def test_events_come_back_in_order(self, read_driver):
        result = read_driver(EventSource.CHARGING).read(
            ref_for(DILANI), DEMO_NOW - timedelta(days=90), DEMO_NOW
        )

        assert result.events == sorted(result.events, key=lambda e: e.occurred_at)

    def test_an_unknown_subscriber_is_missing_not_empty(self, read_driver):
        """ "We could not look" and "we found nothing" must stay distinguishable."""
        result = read_driver(EventSource.CHARGING).read(
            "sub_nobody", DEMO_NOW - timedelta(days=90), DEMO_NOW
        )

        assert result.completeness is Completeness.MISSING
        assert result.events == []

    def test_a_source_that_answers_with_nothing_is_complete(self, read_driver):
        result = read_driver(EventSource.LOANS).read(
            ref_for(DILANI), DEMO_NOW - timedelta(days=90), DEMO_NOW
        )

        assert result.completeness is Completeness.COMPLETE
        assert result.events == []

    def test_every_event_carries_its_provenance(self, read_driver):
        result = read_driver(EventSource.CHARGING).read(
            ref_for(DILANI), DEMO_NOW - timedelta(days=90), DEMO_NOW
        )

        for event in result.events:
            assert event.source_event_id, "an event must say where it came from"
            assert event.adapter_version
            assert event.evidence_hash.startswith("sha256:")

    def test_reading_twice_gives_the_same_answer(self, read_driver):
        """Decisions must be reproducible, so reads cannot be order-dependent."""
        port = read_driver(EventSource.CHARGING)
        args = (ref_for(DILANI), DEMO_NOW - timedelta(days=90), DEMO_NOW)

        first, second = port.read(*args), port.read(*args)

        assert [e.evidence_hash for e in first.events] == [e.evidence_hash for e in second.events]


# --------------------------------------------------------------------------- #
# CommandPort
# --------------------------------------------------------------------------- #


def _http_command_driver() -> tuple[CommandPort, object]:
    world = build_demo_world()
    client = TestClient(create_hutch_sim_app(world))
    return HttpCommandAdapter("http://hutch-sim.test", client=client), world


COMMAND_DRIVERS: list[tuple[str, Callable[[], tuple[CommandPort, object]]]] = [
    ("mock", lambda: (lambda w: (MockCommandAdapter(w), w))(build_demo_world())),
    ("http", _http_command_driver),
]


@pytest.fixture(params=[name for name, _ in COMMAND_DRIVERS], ids=lambda n: f"command:{n}")
def command_driver(request) -> tuple[CommandPort, object]:
    return dict(COMMAND_DRIVERS)[request.param]()


class TestCommandPortParity:
    """What every command driver must guarantee before it touches money."""

    @staticmethod
    def refund(subscriber: str, key: str) -> Command:
        return Command(
            action_type=ActionType.REFUND,
            subscriber_ref=subscriber,
            idempotency_key=key,
            amount_lkr="49.00",
        )

    def test_it_declares_what_it_supports(self, command_driver):
        port, _ = command_driver

        assert port.supports(ActionType.REFUND)
        assert not port.supports(ActionType.SEND_NOTIFICATION)

    def test_an_unsupported_action_is_refused_not_faked(self, command_driver):
        port, _ = command_driver

        result = port.execute(
            Command(
                action_type=ActionType.SEND_NOTIFICATION,
                subscriber_ref=ref_for(DILANI),
                idempotency_key="k1",
            )
        )

        assert not result.accepted
        assert result.error_code

    def test_one_key_applies_once(self, command_driver):
        """The zero-duplicate-refund invariant, at the driver boundary."""
        port, world = command_driver
        subscriber = ref_for(DILANI)
        opening = world.account(subscriber).balance_lkr

        first = port.execute(self.refund(subscriber, "same"))
        second = port.execute(self.refund(subscriber, "same"))

        assert first.accepted and second.accepted
        assert second.replayed and not first.replayed
        assert world.account(subscriber).balance_lkr == opening + Decimal("49.00")

    def test_a_successful_command_reports_before_and_after(self, command_driver):
        port, _ = command_driver

        result = port.execute(self.refund(ref_for(DILANI), "k2"))

        assert result.before_state and result.after_state
        assert result.adapter_ref, "the upstream reference is what reconciliation matches on"

    def test_status_can_be_queried_instead_of_retried_blindly(self, command_driver):
        """An ambiguous result is resolved by asking, never by re-sending."""
        port, _ = command_driver

        assert port.status_of("never-sent") is None
        port.execute(self.refund(ref_for(DILANI), "k3"))
        assert port.status_of("k3") is not None

    def test_an_invalid_amount_is_refused(self, command_driver):
        port, _ = command_driver

        result = port.execute(
            Command(
                action_type=ActionType.REFUND,
                subscriber_ref=ref_for(DILANI),
                idempotency_key="k4",
                amount_lkr="0",
            )
        )

        assert not result.accepted


# --------------------------------------------------------------------------- #
# RecurrenceProbe
# --------------------------------------------------------------------------- #

PROBE_DRIVERS: list[tuple[str, Callable[[], tuple[RecurrenceProbe, object]]]] = [
    ("mock", lambda: (lambda w: (MockRecurrenceProbe(w), w))(build_demo_world())),
]


@pytest.fixture(params=[name for name, _ in PROBE_DRIVERS], ids=lambda n: f"probe:{n}")
def probe_driver(request) -> tuple[RecurrenceProbe, object]:
    return dict(PROBE_DRIVERS)[request.param]()


class TestRecurrenceProbeParity:
    """A receipt that claims a safeguard is in force must have checked."""

    def test_an_unknown_check_cannot_tell(self, probe_driver):
        probe, _ = probe_driver

        assert probe.check("no_such_check", ref_for(DILANI), {}) is None

    def test_an_unknown_subscriber_cannot_tell(self, probe_driver):
        probe, _ = probe_driver

        assert probe.check("merchant_block_active", "sub_nobody", {"merchant_id": "M"}) is None

    def test_it_reports_a_safeguard_that_is_not_in_force(self, probe_driver):
        probe, _ = probe_driver

        assert (
            probe.check("merchant_block_active", ref_for(DILANI), {"merchant_id": "MER-GAMEHUB"})
            is False
        )

    def test_it_reports_a_safeguard_that_is_in_force(self, probe_driver):
        probe, world = probe_driver
        world.block_merchant(ref_for(DILANI), "MER-GAMEHUB")

        assert (
            probe.check("merchant_block_active", ref_for(DILANI), {"merchant_id": "MER-GAMEHUB"})
            is True
        )

    def test_an_unavailable_probe_never_becomes_a_pass(self, probe_driver):
        """UNAVAILABLE is the honest answer; PASSED would be a lie on a receipt."""

        class _Broken:
            def check(self, *_: object, **__: object) -> bool | None:
                raise RuntimeError("probe is down")

        assert run_check(_Broken(), "merchant_block_active", "sub", {}) is (
            RecurrenceResult.UNAVAILABLE
        )
        assert run_check(None, "merchant_block_active", "sub", {}) is (RecurrenceResult.UNAVAILABLE)


# --------------------------------------------------------------------------- #
# SigningService
# --------------------------------------------------------------------------- #


def _real_openbao_signer() -> OpenBaoSigningService:
    """The driver against a real OpenBao Transit engine (M-RCPT).

    Skipped unless one is configured. This is the lane that can catch a wrong
    request shape, a misread response or a token header the service rejects,
    none of which a hand-written stand-in of the API will ever disagree with.
    The key is provisioned here rather than assumed, so the lane sets up the
    state a deployment would.
    """
    address = os.environ.get("CLARITY_OPENBAO_URL")
    token = os.environ.get("CLARITY_OPENBAO_TOKEN")
    if not address or not token:
        pytest.skip("set CLARITY_OPENBAO_URL and CLARITY_OPENBAO_TOKEN to use a real OpenBao")

    headers = {"X-Vault-Token": token}
    key_name = f"clarity-parity-{uuid4().hex[:10]}"
    with httpx.Client(base_url=address.rstrip("/"), headers=headers, timeout=10) as client:
        # Idempotent: a mount that already exists is not an error here.
        client.post("/v1/sys/mounts/transit", json={"type": "transit"})
        created = client.post(
            f"/v1/transit/keys/{key_name}", json={"type": "ed25519", "exportable": True}
        )
        assert created.status_code < 300, f"could not create the key: {created.text}"

    return OpenBaoSigningService(address, key_name=key_name, token=token)


def _openbao_signer() -> OpenBaoSigningService:
    """A stand-in for the Transit API, reimplemented in Python.

    Keeps the ``demo`` profile free of infrastructure (ADR-0006). It cannot tell
    that the driver and the real service disagree, because it is written to the
    driver's expectations; ``_real_openbao_signer`` is the lane that can.
    """
    private = Ed25519PrivateKey.generate()
    public = base64.b64encode(
        private.public_key().public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
    ).decode("ascii")

    def transit(request: httpx.Request) -> httpx.Response:
        assert request.headers["X-Vault-Token"] == "parity-token"
        if "/sign/" in request.url.path:
            document = json.loads(request.content)
            payload = base64.b64decode(document["input"])
            signature = base64.b64encode(private.sign(payload)).decode("ascii")
            return httpx.Response(200, json={"data": {"signature": f"vault:v1:{signature}"}})
        if "/export/public-key/" in request.url.path:
            return httpx.Response(200, json={"data": {"keys": {"1": public}}})
        return httpx.Response(404)

    return OpenBaoSigningService(
        "http://openbao",
        key_name="parity-key",
        token="parity-token",
        client=httpx.Client(transport=httpx.MockTransport(transit)),
    )


SIGNING_DRIVERS: list[tuple[str, Callable[[], SigningService]]] = [
    ("dev", lambda: DevSigningService(kid="parity-key")),
    ("openbao-stand-in", _openbao_signer),
    ("openbao-real", _real_openbao_signer),
]


@pytest.fixture(params=[name for name, _ in SIGNING_DRIVERS], ids=lambda n: f"signer:{n}")
def signing_driver(request) -> SigningService:
    return dict(SIGNING_DRIVERS)[request.param]()


class TestSigningServiceParity:
    """What a KMS or HSM driver must do exactly as the dev signer does."""

    def test_it_signs_and_names_its_key(self, signing_driver):
        kid, signature = signing_driver.sign("sha256:abc")

        assert kid == signing_driver.active_kid
        assert signature

    def test_the_public_key_is_published(self, signing_driver):
        assert signing_driver.active_kid in signing_driver.public_keys()

    def test_a_signature_verifies_with_public_material_only(self, signing_driver):
        """Anyone, including TRCSL, verifies with nothing secret."""
        kid, signature = signing_driver.sign("sha256:abc")

        assert verify_signature(
            "sha256:abc",
            kid=kid,
            signature_b64=signature,
            public_keys=signing_driver.public_keys(),
        )

    def test_a_signature_does_not_verify_for_other_content(self, signing_driver):
        kid, signature = signing_driver.sign("sha256:abc")

        assert not verify_signature(
            "sha256:different",
            kid=kid,
            signature_b64=signature,
            public_keys=signing_driver.public_keys(),
        )

    def test_signing_is_deterministic_for_the_same_input(self, signing_driver):
        """Ed25519 is deterministic, so a receipt re-signs identically."""
        first = signing_driver.sign("sha256:abc")
        second = signing_driver.sign("sha256:abc")

        assert first == second


# --------------------------------------------------------------------------- #
# The suites must actually cover the drivers in use
# --------------------------------------------------------------------------- #


def test_every_read_source_has_a_driver():
    """A source with no driver would silently never be read."""
    world = build_demo_world()

    for source in EventSource:
        assert MockReadAdapter(source, world).source is source


def test_an_unavailable_source_raises_rather_than_returning_nothing(registry):
    """The timeline must be able to tell "down" from "nothing to report"."""
    registry.world.unavailable.add(EventSource.CHARGING)
    port = registry.read_port(EventSource.CHARGING)

    with pytest.raises(AdapterError):
        port.read(ref_for(DILANI), DEMO_NOW - timedelta(days=1), DEMO_NOW)


# --------------------------------------------------------------------------- #
# Key rotation (M-RCPT acceptance 1)
# --------------------------------------------------------------------------- #


def test_rotating_the_signing_key_keeps_old_receipts_verifiable() -> None:
    """A receipt signed before a rotation must still verify afterwards.

    This is what a Trust Receipt promises: it proves what happened whenever it
    is checked, not only until the next key rotation. So the signer has to keep
    publishing every version's public key, and new receipts have to move to the
    new one.

    Run against a real OpenBao, because rotation is the service's behaviour, not
    the driver's: a stand-in would be asserting that the test's own idea of
    rotation matches itself.
    """
    address = os.environ.get("CLARITY_OPENBAO_URL")
    token = os.environ.get("CLARITY_OPENBAO_TOKEN")
    if not address or not token:
        pytest.skip("set CLARITY_OPENBAO_URL and CLARITY_OPENBAO_TOKEN to use a real OpenBao")

    key_name = f"clarity-rotation-{uuid4().hex[:10]}"
    headers = {"X-Vault-Token": token}
    with httpx.Client(base_url=address.rstrip("/"), headers=headers, timeout=10) as admin:
        admin.post("/v1/sys/mounts/transit", json={"type": "transit"})
        created = admin.post(
            f"/v1/transit/keys/{key_name}", json={"type": "ed25519", "exportable": True}
        )
        assert created.status_code < 300, created.text

        before_rotation = OpenBaoSigningService(address, key_name=key_name, token=token)
        old_payload = "sha256:" + "11" * 32
        old_kid, old_signature = before_rotation.sign(old_payload)

        rotated = admin.post(f"/v1/transit/keys/{key_name}/rotate")
        assert rotated.status_code < 300, rotated.text

        # A fresh driver, as a restarted process would be.
        after_rotation = OpenBaoSigningService(address, key_name=key_name, token=token)
        new_kid, _ = after_rotation.sign("sha256:" + "22" * 32)
        published = after_rotation.public_keys()

    assert new_kid != old_kid, "new receipts must be signed with the new key"
    assert old_kid in published, "the old key must still be published, or old receipts die"
    assert verify_signature(
        old_payload,
        kid=old_kid,
        signature_b64=old_signature,
        public_keys=published,
    ), "a receipt signed before the rotation no longer verifies"
