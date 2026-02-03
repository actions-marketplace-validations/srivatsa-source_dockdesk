/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        'risk-high': '#ef4444',
        'risk-medium': '#eab308',
        'risk-low': '#22c55e',
      }
    },
  },
  plugins: [],
}
