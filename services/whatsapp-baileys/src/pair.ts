import makeWASocket, {
  makeCacheableSignalKeyStore,
  useMultiFileAuthState,
} from "@whiskeysockets/baileys"
import pino from "pino"
import { loadConfig, pairingPhone } from "./config.js"

const config = loadConfig({ ...process.env, WHATSAPP_ENABLED: "false" })
const phone = pairingPhone()
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
const code = await socket.requestPairingCode(phone)
process.stdout.write(`${code.match(/.{1,4}/g)?.join("-") ?? code}\n`)
setTimeout(() => process.exit(0), 120_000)
