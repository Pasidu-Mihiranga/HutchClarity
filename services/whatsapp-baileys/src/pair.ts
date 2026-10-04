import makeWASocket, {
  makeCacheableSignalKeyStore,
  useMultiFileAuthState,
} from "@whiskeysockets/baileys"
import pino from "pino"
import qrcode from "qrcode-terminal"
import { loadConfig, pairingPhone } from "./config.js"
import { waitForSocketOpen } from "./pairing.js"

process.umask(0o077)
const config = loadConfig({ ...process.env, WHATSAPP_ENABLED: "false" })
const mode = process.env.WHATSAPP_PAIRING_MODE === "qr" ? "qr" : "phone"
const phone = mode === "phone" ? pairingPhone() : null
const logger = pino({ level: "silent" })
const { state, saveCreds } = await useMultiFileAuthState(config.authDir)
if (state.creds.registered) {
  process.stdout.write("already-paired\n")
  process.exit(0)
}

const socket = makeWASocket({
  auth: {
    creds: state.creds,
    keys: makeCacheableSignalKeyStore(state.keys, logger),
  },
  logger,
  markOnlineOnConnect: false,
})
socket.ev.on("creds.update", saveCreds)
const paired = new Promise<void>((resolve, reject) => {
  socket.ev.on("connection.update", ({ connection, lastDisconnect, qr }) => {
    if (mode === "qr" && qr) {
      process.stdout.write("Scan this QR in WhatsApp Linked Devices:\n")
      qrcode.generate(qr, { small: true })
    }
    if (connection === "open") resolve()
    if (connection === "close") reject(lastDisconnect?.error ?? new Error("pairing connection closed"))
  })
})

if (phone) {
  await waitForSocketOpen(socket.ws)
  const code = await socket.requestPairingCode(phone)
  process.stdout.write(`${code.match(/.{1,4}/g)?.join("-") ?? code}\n`)
}

await Promise.race([
  paired,
  new Promise<never>((_, reject) =>
    setTimeout(() => reject(new Error("WhatsApp pairing timed out")), 120_000),
  ),
])
process.stdout.write("paired\n")
process.exit(0)
