import en from "./messages/en.json";
import si from "./messages/si.json";
import ta from "./messages/ta.json";

export type Lang = "en" | "si" | "ta";

// Derived from the English catalogue rather than hand-listed. A hand-listed
// union drifts the moment somebody adds a string, and the drift is silent: the
// key still renders, because `t` falls back to the key itself.
export type MessageKey = keyof typeof en;

const catalogues: Record<Lang, Record<string, string>> = {
  en: en as Record<string, string>,
  si: si as Record<string, string>,
  ta: ta as Record<string, string>,
};

export const supportedLangs: Lang[] = ["en", "si", "ta"];

/**
 * One string, in the requested language.
 *
 * Falls back to English and then to the key itself. Returning the key rather
 * than an empty string is deliberate: a missing string shows up in the UI as
 * `confirm.cta` and gets fixed, where an empty one renders as a blank button
 * nobody notices.
 *
 * `values` interpolates `{name}` placeholders. Nothing is escaped here because
 * React escapes on render; a caller putting this into `innerHTML` would be the
 * bug, and nothing in this repository does.
 */
export function t(
  lang: Lang | string,
  key: MessageKey | string,
  values?: Record<string, string | number>,
): string {
  const catalogue = catalogues[(lang as Lang) in catalogues ? (lang as Lang) : "en"];
  const template = catalogue[key as string] ?? catalogues.en[key as string] ?? String(key);
  if (!values) return template;
  return template.replace(/\{(\w+)\}/g, (whole, name: string) =>
    name in values ? String(values[name]) : whole,
  );
}

/** Every key the catalogues carry. Used by the test that keeps them in step. */
export function messageKeys(): string[] {
  return Object.keys(en).sort();
}

/** A language's catalogue, for the parity test. */
export function catalogue(lang: Lang): Record<string, string> {
  return catalogues[lang];
}

export { en, si, ta };
