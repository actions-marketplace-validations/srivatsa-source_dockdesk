/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', '"Courier New"', 'monospace'],
      },
      colors: {
        surface: {
          DEFAULT: '#1a1a2e',
          50: '#f0f0f5',
          100: '#e1e1eb',
          200: '#c3c3d7',
          300: '#16213e',
          400: '#0f3460',
          500: '#1a1a2e',
          600: '#141428',
          700: '#0e0e20',
          800: '#0a0a18',
          900: '#060610',
        },
        accent: {
          DEFAULT: '#e94560',
          light: '#ff6b81',
          dark: '#c23152',
          muted: 'rgba(233, 69, 96, 0.15)',
        },
        success: {
          DEFAULT: '#10b981',
          muted: 'rgba(16, 185, 129, 0.15)',
        },
        warning: {
          DEFAULT: '#f59e0b',
          muted: 'rgba(245, 158, 11, 0.15)',
        },
        danger: {
          DEFAULT: '#ef4444',
          muted: 'rgba(239, 68, 68, 0.15)',
        },
        info: {
          DEFAULT: '#6366f1',
          muted: 'rgba(99, 102, 241, 0.15)',
        },
        muted: '#64748b',
      },
      boxShadow: {
        'card': '0 1px 3px rgba(0, 0, 0, 0.3), 0 1px 2px rgba(0, 0, 0, 0.2)',
        'card-hover': '0 4px 12px rgba(0, 0, 0, 0.4), 0 2px 4px rgba(0, 0, 0, 0.3)',
        'glow': '0 0 20px rgba(233, 69, 96, 0.15)',
      },
    },
  },
  plugins: [],
}
