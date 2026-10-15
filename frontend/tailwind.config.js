/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        spandan: {
          50: '#eef8f3',
          100: '#dcefe4',
          200: '#b9dfcc',
          300: '#8cc7ab',
          400: '#54a980',
          500: '#28865f',
          600: '#14734f',
          700: '#0c5d40',
          800: '#104a36',
          900: '#123e30',
          950: '#092b21',
        },
        slateDark: {
          800: '#1e293b',
          900: '#0f172a',
          950: '#020617',
        }
      },
      fontFamily: { sans: ['"Segoe UI"', '"Noto Sans Bengali"', 'Arial', 'sans-serif'] },
      boxShadow: {
        'glass': '0 8px 32px 0 rgba(31, 38, 135, 0.07)',
        'glass-lg': '0 8px 32px 0 rgba(31, 38, 135, 0.15)',
      }
    },
  },
  plugins: [],
}
