import assert from "node:assert/strict"
import test from "node:test"
import {
  createCredentialWriteQueue,
  shouldRequestPairingCode,
  shouldRestartPairedSession,
} from "../src/pairing.js"

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

test("pairing waits for serialized credential writes before completion", async () => {
  const events: string[] = []
  let releaseFirst: (() => void) | undefined
  const firstWrite = new Promise<void>((resolve) => {
    releaseFirst = resolve
  })
  let writes = 0
  const queue = createCredentialWriteQueue(async () => {
    writes += 1
    events.push(`start-${writes}`)
    if (writes === 1) await firstWrite
    events.push(`end-${writes}`)
  })

  const first = queue.enqueue()
  const second = queue.enqueue()
  const flushed = queue.flush().then(() => events.push("flushed"))
  await Promise.resolve()
  assert.deepEqual(events, ["start-1"])

  releaseFirst?.()
  await Promise.all([first, second, flushed])
  assert.deepEqual(events, ["start-1", "end-1", "start-2", "end-2", "flushed"])
})
