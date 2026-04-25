import type { Config } from "tailwindcss";

/**
 * Tailwind drives layout; the CSS variables in `theme.css` drive surface
 * tokens. Existing utility classes (`bg-canvas`, `bg-card`, `bg-rail`,
 * `text-railText`, `bg-accent`) keep working — they now resolve to the
 * variables `usePrefs` mutates on <html>, so swapping themes flips the
 * whole UI without re-rendering.
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        canvas: "var(--rp-canvas)",
        card: "var(--rp-card)",
        cardAlt: "var(--rp-card-2)",
        ink: "var(--rp-ink)",
        ink2: "var(--rp-ink-2)",
        ink3: "var(--rp-ink-3)",
        line: "var(--rp-line)",
        rail: "var(--rp-rail)",
        railText: "var(--rp-rail-ink)",
        railTextDim: "var(--rp-rail-ink-2)",
        railLine: "var(--rp-rail-line)",
        accent: "var(--rp-accent)",
        recent: "var(--rp-recent)",
      },
      fontFamily: {
        sans: ["Inter Tight", "ui-sans-serif", "system-ui", "Inter", "sans-serif"],
        serif: ["Newsreader", "Iowan Old Style", "Georgia", "serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SF Mono", "Menlo", "monospace"],
      },
    },
  },
  plugins: [],
} satisfies Config;
