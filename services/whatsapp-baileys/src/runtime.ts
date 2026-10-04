import { EventEmitter } from "node:events"
import { createServer, type Server } from "node:http"
import { Boom } from "@hapi/boom"
import makeWASocket, {
  DisconnectReason,
  makeCacheableSignalKeyStore,
  useMultiFileAuthState,
  type WASocket,
  type WAMessage,
} from "@whiskeysockets/baileys"
import pino from "pino"
import { deliveryState, handleInbound, skipReason } from "./bridge.js"
import type { WhatsAppConfig } from "./config.js"

const logger = pino({
  level: process.env.LOG_LEVEL ?? "info",
  redact: ["req.headers.authorization", "webhookSecret", "qr", "pairingCode"],
})

export class WhatsAppRuntime extends EventEmitter {
  private socket: WASocket | null = null
  private healthServer: Server | null = null
  private reconnectTimer: NodeJS.Timeout | null = null
  private stopping = false
  private connected = false
  private paired = false

  constructor(private readonly config: WhatsAppConfig) {
    super()
  }

  async start(): Promise<void> {
    this.startHealthServer()
    if (!this.config.enabled) {
      logger.info("WhatsApp transport disabled")
      return
    }
    await this.connect()
  }

  async stop(): Promise<void> {
    this.stopping = true
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.socket?.ws.close()
    await new Promise<void>((resolve) => this.healthServer?.close(() => resolve()) ?? resolve())
  }

  private async connect(): Promise<void> {
    const { state, saveCreds } = await useMultiFileAuthState(this.config.authDir)
    this.paired = state.creds.registered
    this.socket = makeWASocket({
      auth: {
        creds: state.creds,
        keys: makeCacheableSignalKeyStore(state.keys, logger),
      },
      logger,
      markOnlineOnConnect: false,
      syncFullHistory: false,
      shouldIgnoreJid: (jid) =>
        jid === "status@broadcast" ||
        jid.endsWith("@g.us") ||
        jid.endsWith("@broadcast") ||
        jid.endsWith("@newsletter"),
    })
    this.socket.ev.on("creds.update", saveCreds)
    this.socket.ev.on("messages.upsert", ({ messages, type }) => {
      if (type !== "notify") return
      for (const message of messages) void this.onMessage(message)
    })
    this.socket.ev.on("messages.update", (updates) => {
      for (const update of updates) {
        if (update.key.id) {
          logger.info(
            deliveryState({ deliveryId: update.key.id, status: update.update.status }),
            "WhatsApp delivery state updated",
          )
        }
      }
    })
    this.socket.ev.on("connection.update", ({ connection, lastDisconnect, qr }) => {
      if (qr) logger.warn("WhatsApp is unpaired; run the operator pairing command")
      if (connection === "open") {
        this.connected = true
        this.paired = true
        logger.info("WhatsApp transport connected")
      }
      if (connection === "close") this.onDisconnect(lastDisconnect?.error)
    })
  }

  private async onMessage(message: WAMessage): Promise<void> {
    if (!this.socket) return
    try {
      const outcome = await handleInbound(
        message,
        this.config.gatewayUrl,
        this.config.webhookSecret,
        async (jid, text) => this.socket?.sendMessage(jid, { text }),
      )
      if (outcome === "ignored") {
        // The reason only: never the text or the sender.
        logger.info(
          { deliveryId: message.key.id, reason: skipReason(message) },
          "WhatsApp message ignored",
        )
      } else {
        logger.info({ deliveryId: message.key.id, outcome }, "WhatsApp message handled")
      }
    } catch (error) {
      logger.error(
        { deliveryId: message.key.id, error: safeError(error) },
        "WhatsApp message failed",
      )
    }
  }

  private onDisconnect(error: unknown): void {
    this.connected = false
    const status = error instanceof Boom ? error.output.statusCode : undefined
    if (status === DisconnectReason.loggedOut) {
      this.paired = false
      logger.error("WhatsApp session logged out; operator pairing is required")
      return
    }
    if (!this.stopping) {
      logger.warn({ status }, "WhatsApp disconnected; reconnecting")
      this.reconnectTimer = setTimeout(() => void this.connect(), 5_000)
    }
  }

  private startHealthServer(): void {
    this.healthServer = createServer((request, response) => {
      if (request.url !== "/health") {
        response.writeHead(404).end()
        return
      }
      response.setHeader("content-type", "application/json")
      response.end(
        JSON.stringify({
          status: "ok",
          enabled: this.config.enabled,
          paired: this.paired,
          connected: this.connected,
        }),
      )
    })
    this.healthServer.listen(this.config.healthPort, "0.0.0.0")
  }
}

function safeError(error: unknown): string {
  return error instanceof Error ? error.message.slice(0, 300) : "unknown error"
}
