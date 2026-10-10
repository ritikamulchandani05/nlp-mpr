/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      animation: { bounce_dot: "bounce_dot 1.2s infinite ease-in-out" },
      keyframes: {
        bounce_dot: { "0%,80%,100%": { transform: "scale(0.6)", opacity: 0.4 }, "40%": { transform: "scale(1)", opacity: 1 } },
      },
    },
  },
  plugins: [],
};
