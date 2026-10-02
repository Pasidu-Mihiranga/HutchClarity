"use client";

import { createElement, useEffect, useRef } from "react";
import { registerClarityWhyCard } from "@clarity/widget";
import { useLanguage } from "./LanguageProvider";

type WhyWidgetProps = {
  cause?: string;
  amount?: string;
  currency?: string;
  onFix?: () => void;
};

export function WhyWidget({
  cause = "Pack expired overnight",
  amount = "45.00",
  currency = "LKR",
  onFix,
}: WhyWidgetProps) {
  const { lang } = useLanguage();
  const ref = useRef<HTMLElement | null>(null);

  useEffect(() => {
    registerClarityWhyCard();
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (!el || !onFix) return;
    const handler = () => onFix();
    el.addEventListener("clarity-fix", handler);
    return () => el.removeEventListener("clarity-fix", handler);
  }, [onFix]);

  return createElement("clarity-why-card", {
    ref,
    cause,
    amount,
    currency,
    lang,
  });
}
