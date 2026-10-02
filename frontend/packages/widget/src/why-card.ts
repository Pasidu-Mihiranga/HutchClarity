import { t, type Lang } from "@clarity/i18n";

export type WhyCardDetail = {
  cause: string;
  amount: string;
  currency?: string;
  lang?: Lang | string;
};

/**
 * Embeddable &lt;clarity-why-card&gt; custom element.
 * Attributes: cause, amount, currency, lang
 */
export class ClarityWhyCard extends HTMLElement {
  static get observedAttributes(): string[] {
    return ["cause", "amount", "currency", "lang"];
  }

  connectedCallback(): void {
    this.render();
  }

  attributeChangedCallback(): void {
    this.render();
  }

  private render(): void {
    const cause = this.getAttribute("cause") ?? "Unknown cause";
    const amount = this.getAttribute("amount") ?? "0";
    const currency = this.getAttribute("currency") ?? "LKR";
    const lang = (this.getAttribute("lang") ?? "en") as Lang;
    const cta = t(lang, "fix.cta");
    const heading = t(lang, "why.heading");

    this.innerHTML = `
      <style>
        :host { display: block; font-family: system-ui, sans-serif; }
        .card {
          border: 1px solid #e2e8f0;
          border-radius: 8px;
          padding: 16px;
          background: #fff;
          color: #0f172a;
          max-width: 360px;
        }
        .heading { font-size: 14px; color: #64748b; margin: 0 0 8px; }
        .cause { font-size: 16px; font-weight: 600; margin: 0 0 4px; }
        .amount { font-size: 22px; font-weight: 700; margin: 0 0 12px; }
        button {
          background: #0369a1;
          color: #fff;
          border: 0;
          border-radius: 6px;
          padding: 8px 14px;
          font-size: 14px;
          cursor: pointer;
        }
        button:hover { background: #075985; }
      </style>
      <div class="card" part="card">
        <p class="heading">${escapeHtml(heading)}</p>
        <p class="cause">${escapeHtml(cause)}</p>
        <p class="amount">${escapeHtml(currency)} ${escapeHtml(amount)}</p>
        <button type="button" part="cta" data-action="fix">${escapeHtml(cta)}</button>
      </div>
    `;

    const button = this.querySelector("button");
    button?.addEventListener("click", () => {
      this.dispatchEvent(
        new CustomEvent("clarity-fix", {
          bubbles: true,
          composed: true,
          detail: { cause, amount, currency, lang } satisfies WhyCardDetail,
        }),
      );
    });
  }
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

declare global {
  interface HTMLElementTagNameMap {
    "clarity-why-card": ClarityWhyCard;
  }
}

export function registerClarityWhyCard(
  tagName = "clarity-why-card",
): void {
  if (typeof customElements === "undefined") return;
  if (!customElements.get(tagName)) {
    customElements.define(tagName, ClarityWhyCard);
  }
}
