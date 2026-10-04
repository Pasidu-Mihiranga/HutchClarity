/** @type {import('tailwindcss').Config} */
module.exports = {
  presets: [require("@clarity/ui/tailwind-preset")],
  content: [
    "./app/**/*.{js,ts,jsx,tsx}",
    "../../packages/ui/src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: { extend: {} },
  plugins: [],
};
