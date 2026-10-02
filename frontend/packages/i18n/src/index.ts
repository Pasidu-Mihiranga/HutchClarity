import en from "./messages/en.json";
import si from "./messages/si.json";
import ta from "./messages/ta.json";

export type Lang = "en" | "si" | "ta";

export type MessageKey =
  | "app.title"
  | "why.heading"
  | "fix.cta"
  | "receipt.verify"
  | "desk.queue";

const catalogues: Record<Lang, Record<MessageKey, string>> = {
  en: en as Record<MessageKey, string>,
  si: si as Record<MessageKey, string>,
  ta: ta as Record<MessageKey, string>,
};

export const supportedLangs: Lang[] = ["en", "si", "ta"];

export function t(lang: Lang | string, key: MessageKey | string): string {
  const catalogue = catalogues[(lang as Lang) in catalogues ? (lang as Lang) : "en"];
  return catalogue[key as MessageKey] ?? catalogues.en[key as MessageKey] ?? key;
}

export { en, si, ta };
