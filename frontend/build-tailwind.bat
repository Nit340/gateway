@echo off
echo ========================================
echo   Tailwind CSS Build Script
echo   Univa Gateway Frontend
echo ========================================
echo.

cd /d D:\Work\gateway\frontend

echo [1/4] Checking Node and npm...
node -v
npm -v
echo.

echo [2/4] Installing Tailwind CSS...
call npm install -D tailwindcss
echo.

echo [3/4] Creating config and input CSS...

:: Create tailwind.config.js
(
echo /** @type {import('tailwindcss').Config} */
echo module.exports = {
echo   content: [
echo     "./*.html",
echo     "./pages/**/*.html",
echo     "./pages/**/*.js",
echo   ],
echo   theme: {
echo     extend: {
echo       colors: {
echo         primary: '#2563EB',
echo         primaryHover: '#1D4ED8',
echo       },
echo       fontFamily: {
echo         sans: ['Inter', 'sans-serif'],
echo       }
echo     }
echo   },
echo   plugins: [],
echo }
) > tailwind.config.js

:: Create input CSS
(
echo @tailwind base;
echo @tailwind components;
echo @tailwind utilities;
) > assets\css\tailwind-input.css

echo.
echo [4/4] Compiling Tailwind CSS...
call npx tailwindcss -i ./assets/css/tailwind-input.css -o ./assets/css/tailwind.css --minify

echo.
if exist assets\css\tailwind.css (
    echo ========================================
    echo   SUCCESS! Output: assets/css/tailwind.css
    echo ========================================
    echo.
    echo Next step: Replace in your HTML files:
    echo   REMOVE:  ^<script src="assets/js/tailwindcdn.js"^>^</script^>
    echo   ADD:     ^<link href="assets/css/tailwind.css" rel="stylesheet"^>
    echo.
) else (
    echo ========================================
    echo   ERROR! Build failed. Check output above.
    echo ========================================
)

pause
