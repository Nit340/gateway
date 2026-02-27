/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./*.html",
    "./pages/**/*.html",
    "./pages/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        primary: '#2563EB',
        primaryHover: '#1D4ED8',
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      }
    }
  },
  plugins: [],
}