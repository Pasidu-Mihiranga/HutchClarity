"use client";

import { createElement, useEffect, useRef } from "react";
import { registerClarityWhyCard } from "@clarity/widget";
import { useLanguage } from "./LanguageProvider";

/**
 * `cause` and `amount` are required (E4).
 *
 * They used to default to "Pack expired overnight" and "45.00", so a caller
 * that failed to load a decision rendered a card quoting a charge that did not
 * exist. There is no safe default for a figure a customer is being shown: a
 * caller without one must render something else.
 */
type WhyWidgetProps = {
  cause: string;
  amount: string;
  currency?: string;
  onFix?: () => void;
};

export function WhyWidget({
  cause,
  amount,
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
