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
        // Unified Neon Cyber-Purple palette (matches TUI)
        surface: {
          DEFAULT: '#13132B',
          50: '#f0f0f5',
          100: '#e1e1eb',
          200: '#c3c3d7',
          300: '#1a1a3e',
          400: '#16163a',
          500: '#13132B',
          600: '#0f0f24',
          700: '#0B0B1A',
          800: '#080815',
          900: '#050510',
        },
        accent: {
          DEFAULT: '#8A2BE2',
          light: '#DA70D6',
          dark: '#4B0082',
          muted: 'rgba(138, 43, 226, 0.15)',
        },
        pink: {
          DEFAULT: '#FF1493',
          light: '#FF69B4',
          dark: '#C71585',
          muted: 'rgba(255, 20, 147, 0.15)',
        },
        neon: {
          DEFAULT: '#FF00FF',
          muted: 'rgba(255, 0, 255, 0.10)',
        },
        success: {
          DEFAULT: '#00FFFF',
          muted: 'rgba(0, 255, 255, 0.12)',
        },
        warning: {
          DEFAULT: '#FFD700',
          muted: 'rgba(255, 215, 0, 0.12)',
        },
        danger: {
          DEFAULT: '#FF1493',
          muted: 'rgba(255, 20, 147, 0.12)',
        },
        info: {
          DEFAULT: '#8A2BE2',
          muted: 'rgba(138, 43, 226, 0.12)',
        },
        muted: '#8B7EB8',
      },
      boxShadow: {
        'card': '0 1px 3px rgba(0, 0, 0, 0.4), 0 1px 2px rgba(75, 0, 130, 0.1)',
        'card-hover': '0 8px 25px rgba(138, 43, 226, 0.2), 0 4px 10px rgba(0, 0, 0, 0.3)',
        'glow-purple': '0 0 20px rgba(138, 43, 226, 0.3), 0 0 60px rgba(138, 43, 226, 0.1)',
        'glow-pink': '0 0 20px rgba(255, 20, 147, 0.3), 0 0 60px rgba(255, 20, 147, 0.1)',
        'glow-cyan': '0 0 20px rgba(0, 255, 255, 0.3), 0 0 60px rgba(0, 255, 255, 0.1)',
        'glass': 'inset 0 1px 0 rgba(255, 255, 255, 0.05)',
      },
      backdropBlur: {
        'glass': '12px',
      },
      animation: {
        'glow-pulse': 'glow-pulse 3s ease-in-out infinite',
        'float': 'float 6s ease-in-out infinite',
        'gradient-shift': 'gradient-shift 8s ease infinite',
      },
      keyframes: {
        'glow-pulse': {
          '0%, 100%': { boxShadow: '0 0 15px rgba(138, 43, 226, 0.2)' },
          '50%': { boxShadow: '0 0 30px rgba(138, 43, 226, 0.4), 0 0 60px rgba(255, 20, 147, 0.15)' },
        },
        'float': {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-4px)' },
        },
        'gradient-shift': {
          '0%': { backgroundPosition: '0% 50%' },
          '50%': { backgroundPosition: '100% 50%' },
          '100%': { backgroundPosition: '0% 50%' },
        },
      },
    },
  },
  plugins: [],
}
