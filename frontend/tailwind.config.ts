import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: "#0a0b10",
        surface: "#141620",
        surface2: "#1c1f2e",
        border: "#2e324a",
        accent: "#5b8dee",
        "accent-glow": "rgba(91,141,238,0.3)",
        success: "#34d399",
        error: "#f87171",
        warn: "#fbbf24",
        text: "#eef2f8",
        muted: "#8b9bb4",
      },
    },
  },
  plugins: [],
};

export default config;
