export type SocketState = { readonly isOpen: boolean }

export async function waitForSocketOpen(
  socket: SocketState,
  options: {
    timeoutMs?: number
    pollMs?: number
    now?: () => number
    pause?: (milliseconds: number) => Promise<void>
  } = {},
): Promise<void> {
  const timeoutMs = options.timeoutMs ?? 15_000
  const pollMs = options.pollMs ?? 50
  const now = options.now ?? Date.now
  const pause = options.pause ?? ((milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds)))
  const deadline = now() + timeoutMs
  while (!socket.isOpen) {
    if (now() >= deadline) throw new Error("WhatsApp connection did not become ready for pairing")
    await pause(pollMs)
  }
}
