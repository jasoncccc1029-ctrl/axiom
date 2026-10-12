import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          50: "#f6f7f9",
          100: "#eceef2",
          200: "#d5dae3",
          300: "#b0b9c9",
          400: "#8592a8",
          500: "#66758f",
          600: "#515e76",
          700: "#434d60",
          800: "#3a4251",
          900: "#333946",
          950: "#22262f",
        },
        accent: {
          50: "#eefbf8",
          100: "#d5f5ed",
          200: "#aeebd9",
          300: "#79d9c4",
          400: "#43c0a8",
          500: "#29a48e",
          600: "#1e8473",
          700: "#1b6a5d",
          800: "#1a554c",
          900: "#194740",
        },
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "var(--font-sans)", "system-ui", "sans-serif"],
      },
      boxShadow: {
        soft: "0 1px 2px rgba(34, 38, 47, 0.04), 0 8px 24px rgba(34, 38, 47, 0.06)",
        panel: "0 0 0 1px rgba(34, 38, 47, 0.06), 0 12px 40px rgba(34, 38, 47, 0.08)",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        fadeOut: {
          "0%": { opacity: "1", transform: "translateY(0)" },
          "100%": { opacity: "0", transform: "translateY(-4px)" },
        },
        pulseSoft: {
          "0%, 100%": { opacity: "0.55" },
          "50%": { opacity: "1" },
        },
        typingDot: {
          "0%, 60%, 100%": { opacity: "0.35", transform: "translateY(0)" },
          "30%": { opacity: "1", transform: "translateY(-3px)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      animation: {
        fadeUp: "fadeUp 0.45s ease-out both",
        fadeOut: "fadeOut 0.5s ease-in forwards",
        pulseSoft: "pulseSoft 1.6s ease-in-out infinite",
        typingDot: "typingDot 1.05s ease-in-out infinite",
        shimmer: "shimmer 1.4s linear infinite",
      },
    },
  },
  plugins: [],
};

export default config;
