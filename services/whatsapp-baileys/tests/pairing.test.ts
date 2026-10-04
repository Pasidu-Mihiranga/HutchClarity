import assert from "node:assert/strict"
import test from "node:test"
import { waitForSocketOpen } from "../src/pairing.js"

test("pairing waits until the provider socket is open", async () => {
  const socket = { isOpen: false }
  let polls = 0
  await waitForSocketOpen(socket, {
    pause: async () => {
      polls += 1
      socket.isOpen = true
    },
  })
  assert.equal(polls, 1)
})

test("pairing fails safely when the provider socket never opens", async () => {
  let time = 0
  await assert.rejects(
    waitForSocketOpen({ isOpen: false }, {
      timeoutMs: 10,
      pollMs: 5,
      now: () => time,
      pause: async (milliseconds) => {
        time += milliseconds
      },
    }),
    /did not become ready/,
  )
})
