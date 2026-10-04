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

export function createCredentialWriteQueue(save: () => Promise<void>): {
  enqueue: () => Promise<void>
  flush: () => Promise<void>
} {
  let pending = Promise.resolve()
  return {
    enqueue: () => {
      pending = pending.then(save)
      return pending
    },
    flush: () => pending,
  }
}
