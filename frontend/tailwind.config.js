/** @type {import('tailwindcss').Config} */
// Mirrors the tokens on :root in src/index.css (.kiro/steering/style-guide.md).
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ground: "var(--ground)",
        card: "var(--card)",
        raised: "var(--raised)",
        ink: "var(--ink)",
        "ink-soft": "var(--ink-soft)",
        rule: "var(--rule)",
        "rule-soft": "var(--rule-soft)",
        brand: "var(--brand)",
        "brand-rule": "var(--brand-rule)",
        "brand-tint": "var(--brand-tint)",
        ok: "var(--ok)",
        warn: "var(--warn)",
      },
      fontFamily: {
        serif: ["Fraunces Variable", "Fraunces", "Georgia", "serif"],
        sans: ["IBM Plex Sans", "system-ui", "-apple-system", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
      borderRadius: {
        DEFAULT: "var(--radius)",
        token: "var(--radius)",
        pill: "999px",
      },
      transitionTimingFunction: {
        token: "var(--ease)",
      },
    },
  },
  plugins: [],
};
