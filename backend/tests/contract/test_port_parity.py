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
from collections.abc import Callable
from datetime import timedelta
from decimal import Decimal

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from clarity.contracts.decision import ActionType
from clarity.contracts.receipt import RecurrenceResult
from clarity.integration.drivers.mock.adapters import MockCommandAdapter, MockReadAdapter
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
READ_DRIVERS: list[tuple[str, Callable[[EventSource], ReadPort]]] = [
    ("mock", lambda source: MockReadAdapter(source, build_demo_world())),
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

COMMAND_DRIVERS: list[tuple[str, Callable[[], tuple[CommandPort, object]]]] = [
    ("mock", lambda: (lambda w: (MockCommandAdapter(w), w))(build_demo_world())),
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


def _openbao_signer() -> OpenBaoSigningService:
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
    ("openbao", _openbao_signer),
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
