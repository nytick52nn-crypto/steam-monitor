/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        panel: {
          bg: "#0f1419",
          card: "#1a2332",
          border: "#2d3a4f",
          accent: "#3b82f6",
          success: "#22c55e",
          warn: "#eab308",
          danger: "#ef4444",
        },
      },
    },
  },
  plugins: [],
};
