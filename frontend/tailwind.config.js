/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: { ink: "#101828", muted: "#667085", line: "#E4E7EC", canvas: "#F5F7FA", accent: "#F04438", teal: "#039855" },
      boxShadow: { soft: "0 2px 10px rgba(16,24,40,.05)" },
    },
  },
  plugins: [],
};
