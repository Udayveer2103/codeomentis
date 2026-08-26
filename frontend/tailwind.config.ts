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
        display: ['"Geist Variable"', ...defaultTheme.fontFamily.sans],
      },
      colors: {
        // RepoMind's brand color is blue (#1683FF, hue ~211.9° at 100%
        // saturation, ~54.3% lightness). brand-500 is an exact match for
        // that hex; the rest of the ramp holds the same hue/saturation and
        // varies only lightness.
        brand: {
          50: "hsl(211.9 100% 97%)",
          100: "hsl(211.9 100% 93%)",
          200: "hsl(211.9 100% 86%)",
          300: "hsl(211.9 100% 76%)",
          400: "hsl(211.9 100% 65%)",
          500: "hsl(211.9 100% 54.31%)",
          600: "hsl(211.9 100% 45%)",
          700: "hsl(211.9 100% 37%)",
          800: "hsl(211.9 100% 29%)",
          900: "hsl(211.9 100% 22%)",
          950: "hsl(211.9 100% 13%)",
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