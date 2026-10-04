/** @type {import('tailwindcss').Config} */
module.exports = {
  presets: [require("@clarity/ui/tailwind-preset")],
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "./components/**/*.{js,ts,jsx,tsx}",
    "../../packages/ui/src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        hutch: {
          50: "rgb(var(--c-primary-soft) / <alpha-value>)",
          500: "rgb(var(--c-brand) / <alpha-value>)",
          600: "rgb(var(--c-primary) / <alpha-value>)",
          700: "rgb(var(--c-primary-hover) / <alpha-value>)",
        },
      },
      borderRadius: {
        "2xl": "20px",
        "3xl": "24px",
      },
    },
  },
  plugins: [],
};
