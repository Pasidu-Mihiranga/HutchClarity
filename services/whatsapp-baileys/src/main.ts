import { loadConfig } from "./config.js"
import { WhatsAppRuntime } from "./runtime.js"

const runtime = new WhatsAppRuntime(loadConfig())
await runtime.start()

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.once(signal, () => void runtime.stop().finally(() => process.exit(0)))
}
