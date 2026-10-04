export type WhatsAppConfig = {
  enabled: boolean
  authDir: string
  gatewayUrl: string
  webhookSecret: string
  healthPort: number
}

export function loadConfig(env: NodeJS.ProcessEnv = process.env): WhatsAppConfig {
  const enabled = env.WHATSAPP_ENABLED === "true"
  const webhookSecret = env.CLARITY_CHANNEL_WEBHOOK_SECRET ?? ""
  if (enabled && webhookSecret.length < 32) {
    throw new Error("WHATSAPP_ENABLED requires CLARITY_CHANNEL_WEBHOOK_SECRET of at least 32 characters")
  }
  return {
    enabled,
    authDir: env.WHATSAPP_AUTH_DIR ?? "/var/lib/clarity-whatsapp/auth",
    gatewayUrl:
      env.WHATSAPP_GATEWAY_URL ??
      "http://clarity-channel-gateway:8102/webhooks/whatsapp",
    webhookSecret,
    healthPort: Number.parseInt(env.WHATSAPP_HEALTH_PORT ?? "8104", 10),
  }
}

export function pairingPhone(env: NodeJS.ProcessEnv = process.env): string {
  const raw = env.WHATSAPP_PAIRING_PHONE ?? ""
  const digits = raw.replace(/\D/g, "")
  if (!/^\d{8,15}$/.test(digits)) {
    throw new Error("WHATSAPP_PAIRING_PHONE must include the country code and digits only")
  }
  return digits
}
