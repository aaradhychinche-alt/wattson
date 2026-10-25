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
        ink: {
          950: "#070b14",
          900: "#0b1220",
          850: "#0f1728",
          800: "#142036",
        },
      },
      boxShadow: {
        card: "0 18px 50px -30px rgba(56, 189, 248, 0.35)",
      },
    },
  },
  plugins: [],
};

export default config;
