@echo off
REM Build script for Bubsy 3D Texture Injector
REM Creates a standalone Windows .exe using PyInstaller

setlocal EnableDelayedExpansion

echo ==========================================
echo  Bubsy 3D Texture Injector - Build Script
echo ==========================================
echo.

REM --- Auto-detect Python (tries py first, then python) ---
set "PYTHON_CMD="
py --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=py"
    goto :found_python
)
python --version >nul 2>&1
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    goto :found_python
)

REM --- Neither found ---
echo ERROR: Python is not installed or not in PATH.
echo Please install Python 3.10+ from https://python.org
echo Make sure to check "Add Python to PATH" during installation.
pause
exit /b 1

:found_python
echo Found Python: !PYTHON_CMD!
!PYTHON_CMD! --version
echo.

REM --- Install dependencies ---
echo [1/4] Installing dependencies...
!PYTHON_CMD! -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies.
    pause
    exit /b 1
)

REM --- Clean old builds ---
echo [2/4] Cleaning old builds...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"

REM --- Build with PyInstaller ---
echo [3/4] Building executable with PyInstaller...
!PYTHON_CMD! -m PyInstaller --noconfirm --onefile --windowed ^
    --name "Bubsy3D_TextureInjector" ^
    --icon "assets\\bubsy_icon.ico" ^
    --add-data "assets;assets" ^
    --add-data "packs;packs" ^
    --add-data "docs;docs" ^
    --hidden-import extract_tim ^
    --hidden-import tmd_parser ^
    --hidden-import tim_handler ^
    --hidden-import color_mapper ^
    --hidden-import config ^
    --hidden-import rom_parser ^
    --hidden-import pack_manager ^
    --hidden-import injector ^
    main.py

if errorlevel 1 (
    echo ERROR: PyInstaller build failed.
    pause
    exit /b 1
)

REM --- Verify output ---
echo [4/4] Verifying output...
if exist "dist\Bubsy3D_TextureInjector.exe" (
    echo.
    echo ==========================================
    echo  BUILD SUCCESS! ✅
    echo ==========================================
    echo.
    echo Output: dist\Bubsy3D_TextureInjector.exe
    echo.
    echo To use:
    echo   1. Double-click the .exe
    echo   2. Load your Bubsy 3D ROM (.iso, .bin, .cue)
    echo   3. Select a texture pack from the list
    echo   4. Click INJECT TEXTURES!
    echo.
    echo NOTE: You need to download textures first!
    echo   Visit: https://screamingbrainstudios.itch.io/tiny-texture-pack-2
    echo   Place PNG files in: packs\tiny_texture_pack_2\textures\
    echo.
) else (
    echo ERROR: Build output not found.
    pause
    exit /b 1
)

pause
