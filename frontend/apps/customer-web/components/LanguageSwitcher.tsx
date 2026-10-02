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
          className={`rounded px-2 py-1 text-xs font-medium ${
            lang === code
              ? "bg-sky-700 text-white"
              : "bg-slate-100 text-slate-700 hover:bg-slate-200"
          }`}
        >
          {labels[code]}
        </button>
      ))}
    </div>
  );
}
