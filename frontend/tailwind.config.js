/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: {
          50: "#F0F5FA",
          100: "#DCE7F2",
          200: "#B9CFE5",
          300: "#8FB0D3",
          400: "#5F8BBE",
          500: "#3D6DA3",
          600: "#2B5285",
          700: "#1F3E68",
          800: "#16304F",
          900: "#10233C",
          950: "#0A1626",
        },
        brand: {
          teal: "#0D9488",
          "teal-dark": "#0F766E",
          "teal-light": "#CCFBF1",
          amber: "#D97706",
          "amber-light": "#FEF3C7",
          ink: "#1F2937",
          paper: "#F8FAFC",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(16 35 60 / 0.05), 0 1px 3px 0 rgb(16 35 60 / 0.10)",
        "card-hover": "0 4px 6px -1px rgb(16 35 60 / 0.10), 0 2px 4px -2px rgb(16 35 60 / 0.06)",
      },
    },
  },
  plugins: [],
};
