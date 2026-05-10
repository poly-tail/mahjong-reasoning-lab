/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      boxShadow: {
        canvas: "0 1px 2px rgb(28 25 23 / 0.08)",
      },
    },
  },
  plugins: [],
};
