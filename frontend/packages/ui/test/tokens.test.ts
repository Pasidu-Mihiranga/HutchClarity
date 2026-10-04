import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(__dirname, "../src/tokens.css"), "utf8");

/** Pull `--c-*: r g b;` pairs out of one rule block. */
function palette(selector: string): Record<string, [number, number, number]> {
  const start = css.indexOf(selector);
  const open = css.indexOf("{", start);
  const close = css.indexOf("}", open);
  const out: Record<string, [number, number, number]> = {};
  for (const m of css.slice(open, close).matchAll(/--c-([a-z0-9-]+):\s*(\d+)\s+(\d+)\s+(\d+);/g)) {
    out[m[1]] = [Number(m[2]), Number(m[3]), Number(m[4])];
  }
  return out;
}

function luminance([r, g, b]: [number, number, number]): number {
  const lin = [r, g, b].map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2];
}

function contrast(a: [number, number, number], b: [number, number, number]): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

const themes = { light: palette(":root {"), dark: palette(':root[data-theme="dark"]') };

// Every text-on-surface pairing the components use must clear WCAG AA (4.5:1).
//
// `fg-subtle` is deliberately absent: at 3.99:1 on white it is a token for
// decoration (an `aria-hidden` glyph, a placeholder, a disabled icon) and not
// for text. E2 used it for three small labels in the console and the axe run
// in CI caught all three, which is the pairing this list is here to prevent.
const pairs: Array<[string, string]> = [
  ["fg", "bg"],
  ["fg", "surface"],
  ["fg", "surface-2"],
  ["fg-muted", "surface"],
  ["fg-muted", "surface-2"],
  ["primary", "surface"],
  ["primary", "primary-soft"],
  ["on-primary", "primary"],
  ["success", "success-soft"],
  ["warning", "warning-soft"],
  ["danger", "danger-soft"],
  ["info", "info-soft"],
  ["danger", "surface"],
];

describe("design tokens", () => {
  for (const [theme, colours] of Object.entries(themes)) {
    describe(theme, () => {
      it("defines every token the other theme defines", () => {
        expect(Object.keys(colours).sort()).toEqual(Object.keys(themes.light).sort());
      });
      for (const [fg, bg] of pairs) {
        it(`${fg} on ${bg} reaches 4.5:1`, () => {
          expect(contrast(colours[fg], colours[bg])).toBeGreaterThanOrEqual(4.5);
        });
      }
    });
  }

  it("the system-dark block mirrors the explicit dark theme", () => {
    const system = palette(":root:not([data-theme])");
    expect(system).toEqual(themes.dark);
  });
});
