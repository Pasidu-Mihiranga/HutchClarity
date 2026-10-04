import { Boom } from "@hapi/boom"
import makeWASocket, {
  makeCacheableSignalKeyStore,
  useMultiFileAuthState,
} from "@whiskeysockets/baileys"
import pino from "pino"
import qrcode from "qrcode-terminal"
import { loadConfig, pairingPhone } from "./config.js"
import { shouldRequestPairingCode, shouldRestartPairedSession } from "./pairing.js"

process.umask(0o077)
const config = loadConfig({ ...process.env, WHATSAPP_ENABLED: "false" })
const mode = process.env.WHATSAPP_PAIRING_MODE === "qr" ? "qr" : "phone"
const phone = mode === "phone" ? pairingPhone() : null
const logger = pino({ level: "silent" })
async function connect(requestPhoneCode: boolean): Promise<"paired" | "restart"> {
  const { state, saveCreds } = await useMultiFileAuthState(config.authDir)
  const socket = makeWASocket({
    auth: {
      creds: state.creds,
      keys: makeCacheableSignalKeyStore(state.keys, logger),
    },
    logger,
    markOnlineOnConnect: false,
  })
  socket.ev.on("creds.update", saveCreds)

  return new Promise((resolve, reject) => {
    let requested = !requestPhoneCode
    const timer = setTimeout(() => reject(new Error("WhatsApp pairing timed out")), 120_000)
    socket.ev.on("connection.update", ({ connection, lastDisconnect, qr }) => {
      if (mode === "qr" && qr) {
        process.stdout.write("Scan this QR in WhatsApp Linked Devices:\n")
        qrcode.generate(qr, { small: true })
      }
      if (phone && shouldRequestPairingCode({ mode, qr, requested })) {
        requested = true
        void socket.requestPairingCode(phone).then((code) => {
          process.stdout.write(`${code.match(/.{1,4}/g)?.join("-") ?? code}\n`)
        }, reject)
      }
      if (connection === "open") {
        clearTimeout(timer)
        resolve("paired")
      }
      if (connection === "close") {
        clearTimeout(timer)
        const error = lastDisconnect?.error
        const status = error instanceof Boom ? error.output.statusCode : undefined
        if (shouldRestartPairedSession(status, state.creds.registered)) resolve("restart")
        else reject(error ?? new Error("pairing connection closed"))
      }
    })
  })
}

let requestPhoneCode = true
while (true) {
  const outcome = await connect(requestPhoneCode)
  if (outcome === "paired") break
  if (outcome === "restart") requestPhoneCode = false
}
process.stdout.write("paired\n")
process.exit(0)
