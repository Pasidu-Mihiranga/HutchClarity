import { createHmac } from "node:crypto"

export const VOICE_FALLBACK =
  "I cannot process voice notes yet. Please type your question so I can help."

export type IncomingKey = {
  id?: string | null
  remoteJid?: string | null
  fromMe?: boolean | null
}

export type IncomingContent = {
  conversation?: string | null
  extendedTextMessage?: { text?: string | null } | null
  imageMessage?: { caption?: string | null } | null
  videoMessage?: { caption?: string | null } | null
  audioMessage?: unknown
  ephemeralMessage?: { message?: IncomingContent | null } | null
  viewOnceMessage?: { message?: IncomingContent | null } | null
}

export type IncomingMessage = {
  key: IncomingKey
  message?: IncomingContent | null
}

export type NormalizedMessage = {
  deliveryId: string
  jid: string
  msisdn: string
  text: string
}

export type GatewayReply = {
  accepted: boolean
  known_subscriber?: boolean
  reply?: string | null
}

export type ApprovedNotification = {
  jid: string
  templateId: "receipt_issued_v1" | "risk_detected_v1" | "approval_requested_v1"
  text: string
  idempotencyKey: string
}

export type DeliveryUpdate = {
  deliveryId: string
  status: number | string | null | undefined
}

const refusedJids = new Set(["status@broadcast"])

export function normalizeMessage(input: IncomingMessage): NormalizedMessage | null {
  const jid = input.key.remoteJid ?? ""
  const deliveryId = input.key.id ?? ""
  if (
    input.key.fromMe ||
    !deliveryId ||
    !jid.endsWith("@s.whatsapp.net") ||
    jid.endsWith("@g.us") ||
    jid.endsWith("@broadcast") ||
    jid.endsWith("@newsletter") ||
    refusedJids.has(jid)
  ) {
    return null
  }

  const user = jid.slice(0, -"@s.whatsapp.net".length).split(":", 1)[0] ?? ""
  if (!/^\d{8,15}$/.test(user)) return null

  const content = unwrap(input.message)
  const text = extractText(content)
  if (!text) return null
  return { deliveryId, jid, msisdn: `+${user}`, text }
}

function unwrap(content: IncomingContent | null | undefined): IncomingContent | null {
  if (!content) return null
  return (
    content.ephemeralMessage?.message ??
    content.viewOnceMessage?.message ??
    content
  )
}

function extractText(content: IncomingContent | null): string | null {
  if (!content) return null
  const text =
    content.conversation ??
    content.extendedTextMessage?.text ??
    content.imageMessage?.caption ??
    content.videoMessage?.caption
  if (text?.trim()) return text.trim().slice(0, 2000)
  return content.audioMessage ? VOICE_FALLBACK : null
}

export function signedHeaders(
  secret: string,
  body: string,
  deliveryId: string,
  timestamp = new Date().toISOString(),
): Record<string, string> {
  const digest = createHmac("sha256", secret)
    .update(`${timestamp}.${body}`, "utf8")
    .digest("hex")
  return {
    "content-type": "application/json",
    "x-clarity-signature": `sha256=${digest}`,
    "x-clarity-timestamp": timestamp,
    "x-clarity-delivery-id": deliveryId,
  }
}

export async function forwardToGateway(
  message: NormalizedMessage,
  gatewayUrl: string,
  secret: string,
  request: typeof fetch = fetch,
): Promise<GatewayReply> {
  const body = JSON.stringify({
    channel: "whatsapp",
    msisdn: message.msisdn,
    text: message.text,
    thread_id: message.jid,
  })
  const response = await request(gatewayUrl, {
    method: "POST",
    headers: signedHeaders(secret, body, message.deliveryId),
    body,
    signal: AbortSignal.timeout(15_000),
  })
  if (!response.ok) {
    throw new Error(`channel gateway refused delivery with status ${response.status}`)
  }
  return (await response.json()) as GatewayReply
}

export async function handleInbound(
  input: IncomingMessage,
  gatewayUrl: string,
  secret: string,
  send: (jid: string, text: string) => Promise<unknown>,
  request: typeof fetch = fetch,
): Promise<"ignored" | "forwarded" | "replied"> {
  const normalized = normalizeMessage(input)
  if (!normalized) return "ignored"
  const result = await forwardToGateway(normalized, gatewayUrl, secret, request)
  if (!result.reply) return "forwarded"
  await send(normalized.jid, result.reply)
  return "replied"
}

export async function sendApprovedNotification(
  notification: ApprovedNotification,
  send: (jid: string, text: string) => Promise<unknown>,
): Promise<string> {
  if (!notification.text.trim()) throw new Error("approved notification text is required")
  await send(notification.jid, notification.text)
  return notification.idempotencyKey
}

export function deliveryState(update: DeliveryUpdate): { deliveryId: string; status: string } {
  return {
    deliveryId: update.deliveryId,
    status: update.status == null ? "unknown" : String(update.status),
  }
}
