import type { Config } from "tailwindcss"
import defaultTheme from "tailwindcss/defaultTheme";
import typography from "@tailwindcss/typography";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
    "./src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        // Restores the `font-display` utility used throughout the app for
        // headings. Geist Variable is already loaded via
        // `@import "@fontsource-variable/geist"` in src/index.css but was
        // never wired into Tailwind's theme, so `font-display` was a no-op.
        display: ['"Geist Variable"', ...defaultTheme.fontFamily.sans],
      },
      colors: {
        // Restores the `brand-*` color utilities used throughout the app
        // (buttons, active nav state, links, icon accents). This scale is
        // derived directly from the existing RepoMind favicon/logo purple
        // (#863bff / #7e14ff, hue ~263° at full saturation) rather than a
        // new palette — brand-500/600 line up with those exact logo colors.
        brand: {
          50: "hsl(263 100% 97%)",
          100: "hsl(263 100% 94%)",
          200: "hsl(263 100% 88%)",
          300: "hsl(263 100% 79%)",
          400: "hsl(263 100% 69%)",
          500: "hsl(263 100% 62%)",
          600: "hsl(263 100% 54%)",
          700: "hsl(263 91% 46%)",
          800: "hsl(263 86% 38%)",
          900: "hsl(263 80% 30%)",
          950: "hsl(263 75% 18%)",
        },
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
    },
  },
  plugins: [
    typography,
  ],
};

export default config