/**
 * The chat's own copy: no drift between its two catalogues, and a translation
 * gap that is measured rather than invisible (A7).
 *
 * **Why this is worth a test.** The chat does not use `@clarity/i18n` for most
 * of its strings. It keeps two inline catalogues instead:
 *
 * - `CHAT_I18N` in `app/clarity/page.tsx`, with `en`, `si` and `ta` blocks;
 * - `EN` / `SI` / `TA` in `components/ClarityMessageCard.tsx`, where `SI` and
 *   `TA` are `Partial<typeof EN>` and anything absent falls back to English.
 *
 * Thirty-one keys are defined in **both**. They agree today, and nothing made
 * that true or keeps it true: editing `confirm` in one file and not the other
 * would give the customer two different words for the same button depending on
 * which component rendered it, and no type would complain. That is the first
 * test.
 *
 * The second measures the real gap. Both catalogues fall back to English
 * silently, which is correct at runtime and hides a missing translation
 * completely, so a Sinhala customer reads English and nobody finds out. The
 * numbers below are the honest count on the day they were written, recorded so
 * the gap is visible in CI and cannot quietly get worse.
 *
 * Consolidating all of this into `@clarity/i18n` and translating the
 * remainder is the rest of A7; it needs a translator, not a refactor, so the
 * strings are not invented here.
 */

import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const read = (p) => readFileSync(join(here, "..", p), "utf8");

const PAIR = /(\w+):\s*"((?:[^"\\]|\\.)*)"/g;

/** The balanced `{ ... }` object starting at or after `from`. */
function balanced(src, from) {
  const start = src.indexOf("{", from);
  let depth = 0;
  for (let i = start; i < src.length; i += 1) {
    if (src[i] === "{") depth += 1;
    else if (src[i] === "}") {
      depth -= 1;
      if (depth === 0) return src.slice(start, i + 1);
    }
  }
  throw new Error("unbalanced object literal");
}

function pairs(block) {
  const out = new Map();
  for (const [, key, value] of block.matchAll(PAIR)) out.set(key, value);
  return out;
}

const page = read("app/clarity/page.tsx");
const card = read("components/ClarityMessageCard.tsx");

const chat = balanced(page, page.indexOf("const CHAT_I18N"));
const pageEn = pairs(balanced(chat, chat.indexOf("en: {")));
const pageSi = pairs(balanced(chat, chat.indexOf("si: {")));
const pageTa = pairs(balanced(chat, chat.indexOf("ta: {")));

const cardEn = pairs(balanced(card, card.indexOf("const EN = {")));
const cardSi = pairs(balanced(card, card.indexOf("const SI: Partial<typeof EN> = {")));
const cardTa = pairs(balanced(card, card.indexOf("const TA: Partial<typeof EN> = {")));

test("the catalogues parsed, so the rest of this file means something", () => {
  assert.ok(pageEn.size > 50, `page CHAT_I18N.en parsed ${pageEn.size} keys`);
  assert.ok(cardEn.size > 50, `card EN parsed ${cardEn.size} keys`);
});

test("a key defined in both catalogues says the same thing in both", () => {
  const disagree = [];
  for (const [key, value] of pageEn) {
    if (cardEn.has(key) && cardEn.get(key) !== value) {
      disagree.push(`${key}: page=${JSON.stringify(value)} card=${JSON.stringify(cardEn.get(key))}`);
    }
  }

  assert.deepEqual(
    disagree,
    [],
    "the chat's two catalogues disagree about the same key, so the customer " +
      "sees different words depending on which component rendered them:\n  " +
      disagree.join("\n  "),
  );
});

test("Sinhala and Tamil coverage does not get worse", () => {
  const all = new Set([...pageEn.keys(), ...cardEn.keys()]);
  const si = new Set([...pageSi.keys(), ...cardSi.keys()]);
  const ta = new Set([...pageTa.keys(), ...cardTa.keys()]);

  const covered = (have) => [...all].filter((key) => have.has(key)).length;

  // Measured 2026-10-04: 110 keys, 52 with si and ta. Raise these as the gap
  // closes; a drop means a string was added in English only, which the silent
  // fallback would otherwise hide.
  const BASELINE = 52;

  assert.ok(
    covered(si) >= BASELINE,
    `Sinhala coverage fell to ${covered(si)}/${all.size}; baseline is ${BASELINE}`,
  );
  assert.ok(
    covered(ta) >= BASELINE,
    `Tamil coverage fell to ${covered(ta)}/${all.size}; baseline is ${BASELINE}`,
  );
});

test("every string the customer sees mid-turn is translated", () => {
  // The stage labels (A5) are the newest customer-facing copy and the one set
  // that is complete, so they are pinned: a stage shown in English while the
  // rest of the chat is in Sinhala is the most visible kind of gap.
  const stages = ["stageMasked", "stageUnderstood", "stageChecked", "stageComposed", "stageVerified"];

  for (const key of stages) {
    assert.ok(pageEn.has(key), `${key} is missing from the English catalogue`);
    assert.ok(pageSi.has(key), `${key} has no Sinhala`);
    assert.ok(pageTa.has(key), `${key} has no Tamil`);
  }
});
