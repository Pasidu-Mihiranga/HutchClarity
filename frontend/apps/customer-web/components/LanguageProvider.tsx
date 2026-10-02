"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { type Lang } from "@clarity/i18n";

type LangContextValue = {
  lang: Lang;
  setLang: (lang: Lang) => void;
};

const LangContext = createContext<LangContextValue>({
  lang: "en",
  setLang: () => undefined,
});

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLang] = useState<Lang>("en");
  const value = useMemo(() => ({ lang, setLang }), [lang]);
  return (
    <LangContext.Provider value={value}>{children}</LangContext.Provider>
  );
}

export function useLanguage(): LangContextValue {
  return useContext(LangContext);
}
