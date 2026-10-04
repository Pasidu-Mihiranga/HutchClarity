/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
    "../../packages/ui/src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#171a1f",
        mute: "#626a76",
        line: "#e1e5e9",
        paper: "#f6f7f9",
        warm: "#fff8f3",
        accent: { DEFAULT: "#ff6601", deep: "#d94e00", soft: "#fff0e6" },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "Space Grotesk", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 10px 30px rgba(27, 33, 42, 0.06)",
      },
      borderRadius: {
        card: "20px",
      },
    },
  },
  plugins: [],
};
