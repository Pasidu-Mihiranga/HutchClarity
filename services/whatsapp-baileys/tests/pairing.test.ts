import assert from "node:assert/strict"
import test from "node:test"
import { shouldRequestPairingCode, shouldRestartPairedSession } from "../src/pairing.js"

test("phone pairing waits for the provider QR readiness event", () => {
  assert.equal(shouldRequestPairingCode({ mode: "phone", qr: undefined, requested: false }), false)
  assert.equal(shouldRequestPairingCode({ mode: "phone", qr: "ready", requested: false }), true)
  assert.equal(shouldRequestPairingCode({ mode: "phone", qr: "ready", requested: true }), false)
  assert.equal(shouldRequestPairingCode({ mode: "qr", qr: "ready", requested: false }), false)
})

test("post-pair restart is expected only after credentials register", () => {
  assert.equal(shouldRestartPairedSession(515, true), true)
  assert.equal(shouldRestartPairedSession(515, false), false)
  assert.equal(shouldRestartPairedSession(401, true), false)
})
