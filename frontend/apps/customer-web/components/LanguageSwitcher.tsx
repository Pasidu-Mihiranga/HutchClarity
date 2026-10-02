"use client";

import { supportedLangs, type Lang } from "@clarity/i18n";
import { useLanguage } from "./LanguageProvider";

const labels: Record<Lang, string> = {
  en: "EN",
  si: "සිං",
  ta: "தமிழ்",
};

export function LanguageSwitcher() {
  const { lang, setLang } = useLanguage();

  return (
    <div className="flex gap-1" role="group" aria-label="Language">
      {supportedLangs.map((code) => (
        <button
          key={code}
          type="button"
          onClick={() => setLang(code)}
          className="rounded px-2 py-1 text-xs font-medium"
          style={
            lang === code
              ? { background: "var(--orange)", color: "#fff" }
              : { background: "#f4f4f5", color: "#52525b" }
          }
        >
          {labels[code]}
        </button>
      ))}
    </div>
  );
}
