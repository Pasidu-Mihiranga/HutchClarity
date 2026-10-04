import assert from "node:assert/strict"
import { createHmac } from "node:crypto"
import test from "node:test"
import {
  VOICE_FALLBACK,
  deliveryState,
  handleInbound,
  normalizeMessage,
  sendApprovedNotification,
  signedHeaders,
  type IncomingMessage,
} from "../src/bridge.js"

const direct = (overrides: Partial<IncomingMessage> = {}): IncomingMessage => ({
  key: { id: "provider-1", remoteJid: "94781234567@s.whatsapp.net", fromMe: false },
  message: { conversation: "Why was I charged?" },
  ...overrides,
})

test("normalizes a direct message and keeps provider identity", () => {
  assert.deepEqual(normalizeMessage(direct()), {
    deliveryId: "provider-1",
    jid: "94781234567@s.whatsapp.net",
    msisdn: "+94781234567",
    text: "Why was I charged?",
  })
})

test("ignores own, group, status, broadcast, newsletter and system messages", () => {
  const refused = [
    direct({ key: { ...direct().key, fromMe: true } }),
    direct({ key: { id: "2", remoteJid: "1203630@g.us" } }),
    direct({ key: { id: "3", remoteJid: "status@broadcast" } }),
    direct({ key: { id: "4", remoteJid: "x@broadcast" } }),
    direct({ key: { id: "5", remoteJid: "x@newsletter" } }),
    direct({ key: { id: "6", remoteJid: "94781234567@s.whatsapp.net" }, message: {} }),
  ]
  for (const message of refused) assert.equal(normalizeMessage(message), null)
})

test("uses the approved voice fallback", () => {
  const message = direct({ message: { audioMessage: {} } })
  assert.equal(normalizeMessage(message)?.text, VOICE_FALLBACK)
})

test("signs the timestamp and exact raw body", () => {
  const headers = signedHeaders("secret", "{\"a\":1}", "provider-1", "2026-10-04T12:00:00Z")
  const digest = createHmac("sha256", "secret")
    .update('2026-10-04T12:00:00Z.{"a":1}')
    .digest("hex")
  assert.equal(headers["x-clarity-signature"], `sha256=${digest}`)
  assert.equal(headers["x-clarity-delivery-id"], "provider-1")
})

test("forwards a signed event and sends the exact gateway reply", async () => {
  let sent: [string, string] | undefined
  let forwardedBody = ""
  const request: typeof fetch = async (_url, init) => {
    forwardedBody = String(init?.body)
    return new Response(JSON.stringify({ accepted: true, reply: "Exact Clarity reply" }), {
      status: 200,
      headers: { "content-type": "application/json" },
    })
  }
  const result = await handleInbound(
    direct(),
    "http://gateway/webhooks/whatsapp",
    "secret",
    async (jid, text) => {
      sent = [jid, text]
    },
    request,
  )
  assert.equal(result, "replied")
  assert.equal(JSON.parse(forwardedBody).channel, "whatsapp")
  assert.deepEqual(sent, ["94781234567@s.whatsapp.net", "Exact Clarity reply"])
})

test("does not invent a reply for an unknown subscriber", async () => {
  let sends = 0
  const request: typeof fetch = async () =>
    new Response(JSON.stringify({ accepted: true, known_subscriber: false, reply: null }))
  const result = await handleInbound(
    direct(),
    "http://gateway/webhooks/whatsapp",
    "secret",
    async () => {
      sends += 1
    },
    request,
  )
  assert.equal(result, "forwarded")
  assert.equal(sends, 0)
})

test("errors expose only gateway status and never the signing secret", async () => {
  const request: typeof fetch = async () => new Response("private upstream detail", { status: 401 })
  await assert.rejects(
    handleInbound(direct(), "http://gateway", "top-secret", async () => undefined, request),
    (error: Error) => error.message === "channel gateway refused delivery with status 401",
  )
})

test("sends an already-approved proactive template exactly once", async () => {
  const sent: Array<[string, string]> = []
  const key = await sendApprovedNotification(
    {
      jid: "94781234567@s.whatsapp.net",
      templateId: "receipt_issued_v1",
      text: "Your receipt is ready: TR-1",
      idempotencyKey: "event-1:subscriber:receipt_issued_v1",
    },
    async (jid, text) => {
      sent.push([jid, text])
    },
  )
  assert.equal(key, "event-1:subscriber:receipt_issued_v1")
  assert.deepEqual(sent, [["94781234567@s.whatsapp.net", "Your receipt is ready: TR-1"]])
})

test("normalizes provider delivery state without message content", () => {
  assert.deepEqual(deliveryState({ deliveryId: "provider-1", status: 3 }), {
    deliveryId: "provider-1",
    status: "3",
  })
})
