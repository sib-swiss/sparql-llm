/** @type {import('tailwindcss').Config} */
import tailwindTypography from "@tailwindcss/typography";

export default {
  darkMode: "selector",
  content: ["./index.html", "../src/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      // Remove backticks from inline code
      typography: {
        DEFAULT: {
          css: {
            // Fix <code> rendering
            "code::before": {
              content: '""',
            },
            "code::after": {
              content: '""',
            },
            code: {
              "border-radius": "0.375rem",
              padding: "0.35em",
              color: "var(--tw-prose-pre-code)",
              "background-color": "var(--tw-prose-pre-bg)",
              "font-weight": "normal",
            },
          },
        },
      },
    },
  },
  plugins: [tailwindTypography()],
};
