import { t, type Lang } from "@clarity/i18n";

export type WhyCardDetail = {
  cause: string;
  amount: string;
  currency?: string;
  lang?: Lang | string;
};

const _HTMLElement: typeof HTMLElement =
  typeof HTMLElement !== "undefined"
    ? HTMLElement
    : (class {} as unknown as typeof HTMLElement);

/**
 * Embeddable &lt;clarity-why-card&gt; custom element.
 * Attributes: cause, amount, currency, lang
 */
export class ClarityWhyCard extends _HTMLElement {
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
          border: 1px solid #ebebef;
          border-radius: 20px;
          padding: 18px;
          background: #fff;
          color: #1a1a1a;
          max-width: 100%;
          box-shadow: 0 1px 2px rgba(0,0,0,.04), 0 8px 24px rgba(0,0,0,.06);
        }
        .heading { font-size: 13px; color: #6b6b6b; margin: 0 0 6px; }
        .cause { font-size: 15px; font-weight: 650; margin: 0 0 4px; }
        .amount { font-size: 26px; font-weight: 800; margin: 0 0 14px; letter-spacing: -.02em; }
        button {
          background: #f26226;
          color: #fff;
          border: 0;
          border-radius: 999px;
          padding: 10px 20px;
          font-size: 15px;
          font-weight: 650;
          cursor: pointer;
        }
        button:hover { filter: brightness(.97); }
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
