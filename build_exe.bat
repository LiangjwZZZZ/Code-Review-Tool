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
echo [Step 1/5] Installing Python dependencies...
python -m pip install -e . --quiet || (echo [ERROR] pip install failed && pause && exit /b 1)
python -m pip install pyinstaller --quiet || (echo [ERROR] pyinstaller install failed && pause && exit /b 1)
echo [OK] Python dependencies installed

REM ---- 3. Build frontend ----
echo.
echo [Step 2/5] Building frontend (npm)...
pushd web-ui
call npm install --silent || (echo [ERROR] npm install failed && popd && pause && exit /b 1)
call npm run build        || (echo [ERROR] npm build failed  && popd && pause && exit /b 1)
popd
echo [OK] Frontend built to review\web\static\

REM ---- 4. Package gitnexus as standalone exe ----
echo.
echo [Step 3/5] Packaging gitnexus (symbol analysis tool)...
set "GITNEXUS_EXE=bundled_gitnexus.exe"

REM Try pkg (better native addon support than nexe)
npm install pkg --save-dev --silent 2>nul
if exist node_modules\.bin\pkg.exe (
    echo [..] Using pkg to build gitnexus standalone exe...
    call npx pkg node_modules\gitnexus --targets node20-win-x64 --output "%GITNEXUS_EXE%" 2>nul
    if exist "%GITNEXUS_EXE%" (
        echo [OK] gitnexus packaged via pkg
        goto :gitnexus_done
    )
    echo [WARN] pkg failed (likely native addon issue with tree-sitter)
)

REM Fallback: try nexe
echo [..] Trying nexe as fallback...
npm install nexe --save-dev --silent 2>nul
call npx nexe node_modules\gitnexus -o "%GITNEXUS_EXE%" -t windows-x64-20.11.0 2>nul
if exist "%GITNEXUS_EXE%" (
    echo [OK] gitnexus packaged via nexe
    goto :gitnexus_done
)

REM Both failed - document the limitation
echo.
echo [INFO] Could not build standalone gitnexus.exe (tree-sitter native addon issue).
echo [INFO] gitnexus will NOT be bundled. The tool will fall back to:
echo [INFO]   1. npx gitnexus (requires Node.js on user machine)
echo [INFO]   2. gitnexus in PATH (if user installed it globally)
echo [INFO] Symbol-level impact analysis will work if Node.js is available.
set "GITNEXUS_EXE="

:gitnexus_done

REM ---- 5. Run PyInstaller ----
echo.
echo [Step 4/5] Packaging with PyInstaller (this may take a few minutes)...
python -m PyInstaller code_review.spec --noconfirm || (echo [ERROR] PyInstaller failed && pause && exit /b 1)
echo [OK] PyInstaller done

REM ---- 6. Copy gitnexus.exe to dist (if built successfully) ----
echo.
echo [Step 5/5] Finalizing build...
if defined GITNEXUS_EXE (
    if exist "%GITNEXUS_EXE%" (
        copy "%GITNEXUS_EXE%" dist\CodeReview\ >nul 2>&1
        echo [OK] gitnexus.exe copied to dist\CodeReview\
        del "%GITNEXUS_EXE%" 2>nul
    )
)

REM ---- 7. Result ----
echo.
echo Build complete!
echo.
echo Output folder: dist\CodeReview\
echo Executable:    dist\CodeReview\CodeReview.exe
echo.
if exist dist\CodeReview\gitnexus.exe (
    echo [OK] gitnexus.exe is bundled for symbol-level impact analysis.
) else (
    echo [NOTE] gitnexus.exe is NOT bundled. Install Node.js 18+ for full functionality.
    echo        Run: npm install -g gitnexus   (or it will auto-download via npx)
)
echo.
echo You can zip the entire dist\CodeReview\ folder and distribute it.
echo (The EXE depends on files in the same folder, do NOT move it alone)
echo.
pause
