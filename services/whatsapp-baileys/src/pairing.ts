export function shouldRequestPairingCode(input: {
  mode: "phone" | "qr"
  qr: string | undefined
  requested: boolean
}): boolean {
  return input.mode === "phone" && Boolean(input.qr) && !input.requested
}

export function shouldRestartPairedSession(statusCode: number | undefined, registered: boolean): boolean {
  return statusCode === 515 && registered
}
