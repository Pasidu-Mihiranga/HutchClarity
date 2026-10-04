"use client";

import * as React from "react";

export type ThemeChoice = "light" | "dark" | "system";

type ThemeApi = { theme: ThemeChoice; setTheme: (theme: ThemeChoice) => void };

const ThemeContext = React.createContext<ThemeApi | null>(null);

const STORAGE_KEY = "clarity.theme";

function apply(theme: ThemeChoice) {
  const root = document.documentElement;
  if (theme === "system") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);
}

function read(): ThemeChoice {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "light" || stored === "dark" || stored === "system") return stored;
  } catch {
    // Storage can be blocked; fall through to the default.
  }
  return "light";
}

/**
 * Applies the chosen theme to <html data-theme>. The default is light so
 * nothing changes for an app until it offers the switch.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = React.useState<ThemeChoice>("light");

  React.useEffect(() => {
    const stored = read();
    setThemeState(stored);
    apply(stored);
  }, []);

  const setTheme = React.useCallback((next: ThemeChoice) => {
    setThemeState(next);
    apply(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Not persisted; the choice still holds for this page view.
    }
  }, []);

  const api = React.useMemo(() => ({ theme, setTheme }), [theme, setTheme]);
  return <ThemeContext.Provider value={api}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeApi {
  const api = React.useContext(ThemeContext);
  if (!api) throw new Error("useTheme must be used inside <ThemeProvider>");
  return api;
}

/** Small select that sets the theme. Labels are passed in so the host app translates them. */
export function ThemeSwitcher({
  label,
  labels,
  className,
}: {
  label: string;
  labels: Record<ThemeChoice, string>;
  className?: string;
}) {
  const { theme, setTheme } = useTheme();
  return (
    <label className={className}>
      <span className="sr-only">{label}</span>
      <select
        value={theme}
        onChange={(event) => setTheme(event.target.value as ThemeChoice)}
        className="rounded-md border border-border-strong bg-surface px-2 py-1 text-xs text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
      >
        {(["light", "dark", "system"] as const).map((choice) => (
          <option key={choice} value={choice}>
            {labels[choice]}
          </option>
        ))}
      </select>
    </label>
  );
}
