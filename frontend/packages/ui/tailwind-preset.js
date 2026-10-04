/**
 * Tailwind preset shared by every Clarity app. Semantic colour names resolve
 * to the CSS variables in `src/tokens.css`, so one change there re-themes the
 * console, the customer app and the verify page together.
 *
 * The `slate` scale is remapped onto the same variables on purpose: console
 * pages written before the design system used raw slate classes, and this lets
 * them follow the theme (including dark) while they are migrated.
 */
const channel = (name) => `rgb(var(${name}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
module.exports = {
  theme: {
    extend: {
      colors: {
        bg: channel("--c-bg"),
        surface: { DEFAULT: channel("--c-surface"), 2: channel("--c-surface-2") },
        border: { DEFAULT: channel("--c-border"), strong: channel("--c-border-strong") },
        fg: {
          DEFAULT: channel("--c-fg"),
          muted: channel("--c-fg-muted"),
          subtle: channel("--c-fg-subtle"),
        },
        primary: {
          DEFAULT: channel("--c-primary"),
          hover: channel("--c-primary-hover"),
          soft: channel("--c-primary-soft"),
          on: channel("--c-on-primary"),
        },
        brand: channel("--c-brand"),
        success: { DEFAULT: channel("--c-success"), soft: channel("--c-success-soft") },
        warning: { DEFAULT: channel("--c-warning"), soft: channel("--c-warning-soft") },
        danger: { DEFAULT: channel("--c-danger"), soft: channel("--c-danger-soft") },
        info: { DEFAULT: channel("--c-info"), soft: channel("--c-info-soft") },
        focus: channel("--c-focus"),
        overlay: channel("--c-overlay"),
        // Legacy names used across the console, mapped onto tokens.
        ink: channel("--c-fg"),
        mute: channel("--c-fg-muted"),
        line: channel("--c-border"),
        paper: channel("--c-bg"),
        warm: channel("--c-primary-soft"),
        accent: {
          DEFAULT: channel("--c-primary"),
          deep: channel("--c-primary-hover"),
          soft: channel("--c-primary-soft"),
        },
        slate: {
          50: channel("--c-surface-2"),
          100: channel("--c-surface-2"),
          200: channel("--c-border"),
          300: channel("--c-border-strong"),
          400: channel("--c-fg-subtle"),
          500: channel("--c-fg-muted"),
          600: channel("--c-fg-muted"),
          700: channel("--c-fg"),
          800: channel("--c-fg"),
          900: channel("--c-fg"),
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        display: ["var(--font-display)"],
      },
      borderRadius: {
        sm: "var(--radius-sm)",
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
        card: "var(--radius-xl)",
      },
      boxShadow: {
        1: "var(--shadow-1)",
        2: "var(--shadow-2)",
        3: "var(--shadow-3)",
        card: "var(--shadow-2)",
      },
    },
  },
};
