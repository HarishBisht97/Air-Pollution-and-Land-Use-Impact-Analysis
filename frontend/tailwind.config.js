/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#1c1917",
        paper: "#f6f3ee",
        moss: "#3f6b4a",
        clay: "#b45309",
        haze: "#7c2d12",
        water: "#1d4e89",
      },
      fontFamily: {
        sans: ["Source Sans 3", "ui-sans-serif", "system-ui"],
        display: ["Fraunces", "ui-serif", "Georgia"],
      },
    },
  },
  plugins: [],
};
