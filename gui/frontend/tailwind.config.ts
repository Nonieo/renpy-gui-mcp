import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "#fafaf9",
        card: "#ffffff",
        rail: "#1c1917",
        railText: "#fafaf9",
        accent: "#6366f1",
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "Inter", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
