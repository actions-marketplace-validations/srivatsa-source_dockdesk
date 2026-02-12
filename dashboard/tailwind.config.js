/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        mono: ['"JetBrains Mono"', '"Courier New"', 'monospace'],
      },
      colors: {
        'mono-bg': '#000000',
        'mono-card': '#0a0a0a',
        'mono-border': '#333333',
        'mono-text': '#d4d4d4',
        'mono-dim': '#666666',
        'mono-accent': '#ffffff',
      }
    },
  },
  plugins: [],
}
