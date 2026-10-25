import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        void: "#000000",
        graphite: "#292d30",
        bone: "#f0f0f0",
        ash: "#a1a4a5",
        smoke: "#abafb4",
        iron: "#6e727a",
        charcoal: "#464a4d",
        iris: {
          DEFAULT: "#9281f7",
          glow: "#baa7ff",
        },
        signal: "#3b9eff",
        sky: {
          accent: "#70b8ff",
        },
        pulse: "#3ad389",
        alarm: "#ff9592",
        crimson: "#ff6465",
        amber: {
          accent: "#ffca16",
          glow: "#ffd60a",
        },
        surface: {
          lift: "#0b0e14",
        },
        ink: {
          950: "#000000",
          900: "#0b0e14",
          850: "#14181f",
          800: "#292d30",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          "sans-serif",
        ],
        mono: [
          '"Commit Mono"',
          '"JetBrains Mono"',
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
        domaine: ["Domaine", "Playfair Display", "Georgia", "serif"],
        favorit: ['"aBC Favorit"', "Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      borderRadius: {
        btn: "6px",
        badge: "6px",
        input: "6px",
        card: "16px",
        panel: "24px",
      },
      boxShadow: {
        none: "none",
        subtle: "rgba(176, 199, 217, 0.145) 0px 0px 0px 1px",
      },
    },
  },
  plugins: [],
};

export default config;
