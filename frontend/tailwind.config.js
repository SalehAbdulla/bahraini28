/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        /*
         * Bahraini 28 brand green — sampled directly from the official logo
         * mark in `docs/Bahraini 28 3.pdf` (pages 3-5 and 8-9 all resolve to
         * exactly #6db193). `brand-500` is the untouched brand value; the
         * neighbouring steps are tonal extensions of the same hue.
         */
        brand: {
          50: "#f2f8f5",
          100: "#e3f1ea",
          200: "#c6e3d5",
          300: "#a3d2be",
          400: "#86c1a6",
          500: "#6db193", // exact brand green (logo mark)
          600: "#559a7c",
          700: "#447f66", // AA-compliant on white (4.7:1) — solid buttons
          800: "#356450",
          900: "#2a503f",
        },
        /*
         * Warm paper tones from the watercolour backgrounds in the identity
         * deck (pages 4/8, plus the "Hello" script on page 6).
         */
        cream: {
          50: "#fffdf6",
          100: "#fff8e4", // page 4/8 background
          200: "#fdf0cd",
          300: "#f4e5c2", // page 6 "Hello" script
          400: "#e8d5a4",
        },
        // Charcoal "ink" — the dark brand canvas (pages 1, 5, 6 and 10).
        ink: {
          700: "#3a3b3b",
          800: "#252626",
          900: "#1a1a1a",
        },
        // Neutral grey of the brush-swipe underline and the badge ring.
        brush: "#878787",
      },
      fontFamily: {
        /*
         * The brand script face (HOOKER) is self-hosted from docs/Fonts.zip and
         * declared in index.css. Accent typography only — never body copy.
         */
        script: ['"Bahraini Script"', "cursive"],
      },
      backgroundImage: {
        // Logo-free bands cut from the brand deck's watercolour pages.
        "texture-mint": "url('/brand/texture-mint.jpg')",
        "texture-cream": "url('/brand/texture-cream.jpg')",
        "texture-ink": "url('/brand/texture-ink.jpg')",
      },
    },
  },
  plugins: [],
};