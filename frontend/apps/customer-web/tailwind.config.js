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
        hutch: {
          50:  "#fff1eb",
          100: "#fdd5c0",
          200: "#f8b39a",
          500: "#f26226",
          600: "#c2410c",
          700: "#9a3412",
        },
      },
      borderRadius: {
        "2xl": "20px",
        "3xl": "24px",
      },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,.04), 0 8px 24px rgba(0,0,0,.06)",
      },
    },
  },
  plugins: [],
};
