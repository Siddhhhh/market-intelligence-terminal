/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        terminal: {
          bg: "#0d0b08",
          panel: "#161210",
          border: "#2e2720",
          surface: "#1e1a15",
          accent: "#d4a843",
          green: "#4ade80",
          red: "#f87171",
          amber: "#d4a843",
          muted: "#6b5c42",
          text: "#e8dcc8",
          dim: "#a69070",
        },
      },
      fontFamily: {
        mono: ['"JetBrains Mono"', '"Fira Code"', "monospace"],
        display: ['"Playfair Display"', '"DM Sans"', "serif"],
      },
    },
  },
  plugins: [],
};
