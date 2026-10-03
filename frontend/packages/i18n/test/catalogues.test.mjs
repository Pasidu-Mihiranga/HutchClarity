/**
 * The three catalogues must carry the same keys (C05, #24).
 *
 * Uses node:test rather than adding a runner, so this costs no dependency and
 * runs anywhere Node does.
 *
 * **Why this is worth a test.** `t` falls back to English and then to the key
 * itself, which is the right behaviour at runtime and hides a missing
 * translation completely: a Sinhala customer sees the English string, and
 * nobody notices until somebody reads the screen. The fallback is a safety
 * net, not a licence to be short of strings, and this is what says so.
 */

import assert from "node:assert/strict";
import test from "node:test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const load = (lang) =>
  JSON.parse(readFileSync(join(here, "..", "src", "messages", `${lang}.json`), "utf8"));

const LANGS = ["en", "si", "ta"];
const catalogues = Object.fromEntries(LANGS.map((lang) => [lang, load(lang)]));

test("every catalogue carries exactly the English keys", () => {
  const english = Object.keys(catalogues.en).sort();
  for (const lang of LANGS) {
    const keys = Object.keys(catalogues[lang]).sort();
    assert.deepEqual(
      keys,
      english,
      `${lang} differs: missing ${english.filter((k) => !keys.includes(k))}, ` +
        `extra ${keys.filter((k) => !english.includes(k))}`,
    );
  }
});

test("no string is empty or left as its own key", () => {
  for (const lang of LANGS) {
    for (const [key, value] of Object.entries(catalogues[lang])) {
      assert.ok(typeof value === "string" && value.trim().length > 0, `${lang}:${key} is empty`);
      assert.notEqual(value, key, `${lang}:${key} is still the key, so it was never written`);
    }
  }
});

test("si and ta are actually translated, not copies of English", () => {
  // A copied English string is the failure this catches: it passes the key
  // check, renders without complaint, and leaves a customer reading a language
  // they did not ask for. Latin-script product names are the legitimate
  // exception, so this checks the share rather than every string.
  for (const lang of ["si", "ta"]) {
    const total = Object.keys(catalogues.en).length;
    const identical = Object.entries(catalogues.en).filter(
      ([key, value]) => catalogues[lang][key] === value,
    );
    assert.ok(
      identical.length / total < 0.2,
      `${identical.length} of ${total} ${lang} strings are identical to English: ` +
        identical.slice(0, 8).map(([key]) => key).join(", "),
    );
  }
});

test("placeholders match across languages", () => {
  // A translation that drops `{queue}` renders the sentence without the thing
  // it was about; one that invents `{team}` renders the brace literally.
  const placeholders = (value) => (value.match(/\{(\w+)\}/g) ?? []).sort();
  for (const [key, value] of Object.entries(catalogues.en)) {
    for (const lang of ["si", "ta"]) {
      assert.deepEqual(
        placeholders(catalogues[lang][key]),
        placeholders(value),
        `${lang}:${key} placeholders differ from English`,
      );
    }
  }
});
