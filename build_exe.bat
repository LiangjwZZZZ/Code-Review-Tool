@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul

echo ============================================
echo   Code Review Tool - Windows EXE Builder
echo ============================================
echo.

REM ---- 1. Check prerequisites ----
where python >nul 2>&1 || (echo [ERROR] Python not found. Please install Python 3.12+ && pause && exit /b 1)
where node   >nul 2>&1 || (echo [ERROR] Node.js not found. Please install Node.js 18+  && pause && exit /b 1)
where npm    >nul 2>&1 || (echo [ERROR] npm not found && pause && exit /b 1)

for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PY_VER=%%v
echo [OK] !PY_VER!

REM ---- 2. Install Python deps ----
echo.
echo [Step 1/4] Installing Python dependencies...
python -m pip install -e . --quiet || (echo [ERROR] pip install failed && pause && exit /b 1)
python -m pip install pyinstaller --quiet || (echo [ERROR] pyinstaller install failed && pause && exit /b 1)
echo [OK] Python dependencies installed

REM ---- 3. Build frontend ----
echo.
echo [Step 2/4] Building frontend (npm)...
pushd web-ui
call npm install --silent || (echo [ERROR] npm install failed && popd && pause && exit /b 1)
call npm run build        || (echo [ERROR] npm build failed  && popd && pause && exit /b 1)
popd
echo [OK] Frontend built to review\web\static\

REM ---- 4. Run PyInstaller ----
echo.
echo [Step 3/4] Packaging with PyInstaller (this may take a few minutes)...
python -m PyInstaller code_review.spec --noconfirm || (echo [ERROR] PyInstaller failed && pause && exit /b 1)
echo [OK] PyInstaller done

REM ---- 5. Result ----
echo.
echo [Step 4/4] Build complete!
echo.
echo Output folder: dist\CodeReview\
echo Executable:    dist\CodeReview\CodeReview.exe
echo.
echo You can zip the entire dist\CodeReview\ folder and distribute it.
echo (The EXE depends on files in the same folder, do NOT move it alone)
echo.
pause
