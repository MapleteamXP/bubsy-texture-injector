@echo off
REM ============================================================
REM  Bubsy 3D Texture Injector — Windows Setup Script
REM ============================================================

setlocal EnableDelayedExpansion

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
echo.
echo  ===========================================
echo   Bubsy 3D Texture Injector - Setup
echo  ===========================================
echo.
echo  ERROR: Python is not installed or not in PATH.
echo.
echo  Please install Python 3.10+ from https://python.org
echo  Make sure to check "Add Python to PATH" during installation.
echo.
pause
exit /b 1

:found_python
echo.
echo  ===========================================
echo   Bubsy 3D Texture Injector - Setup
echo  ===========================================
echo.
echo  Found Python: !PYTHON_CMD!
!PYTHON_CMD! --version
echo.

REM --- Step 1: Install dependencies ---
echo [1/5] Installing Python dependencies...
!PYTHON_CMD! -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  ERROR: Failed to install dependencies.
    echo  Try: !PYTHON_CMD! -m pip install --upgrade pip
    pause
    exit /b 1
)
echo  Dependencies installed successfully!
echo.

REM --- Step 2: Check for textures ---
echo [2/5] Checking texture packs...
set TEXTURE_DIR=packs\tiny_texture_pack_2\textures
if not exist "%TEXTURE_DIR%\*.png" (
    echo.
    echo  TEXTURES NOT FOUND!
    echo.
    echo  You need to download Tiny Texture Pack 2 from itch.io:
    echo    https://screamingbrainstudios.itch.io/tiny-texture-pack-2
    echo.
    echo  Instructions:
    echo    1. Visit the link above
    echo    2. Click "Download Now" (it's FREE, CC0 license)
    echo    3. Extract the ZIP file
    echo    4. Copy PNG files to: %TEXTURE_DIR%\
    echo.
    echo  Press any key to open the download page in your browser...
    pause >nul
    start https://screamingbrainstudios.itch.io/tiny-texture-pack-2
    echo.
    echo  After downloading, place textures in %TEXTURE_DIR%\ and re-run this script.
    echo.
    pause
    exit /b 1
)
set texture_count=0
for %%f in (%TEXTURE_DIR%\*.png) do set /a texture_count+=1
echo  Found %texture_count% textures in %TEXTURE_DIR%
echo.

REM --- Step 3: Clean old builds ---
echo [3/5] Cleaning old builds...
if exist "dist" rmdir /s /q "dist"
if exist "build" rmdir /s /q "build"
echo  Cleaned.
echo.

REM --- Step 4: Build the .exe ---
echo [4/5] Building Bubsy3D_TextureInjector.exe...
echo  This may take 2-3 minutes...
echo.

!PYTHON_CMD! -m PyInstaller --noconfirm --onefile --windowed ^
    --name "Bubsy3D_TextureInjector" ^
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
    echo.
    echo  ERROR: Build failed.
    echo  Check the error messages above.
    pause
    exit /b 1
)

REM --- Success! ---
echo.
echo  ===========================================
echo   BUILD SUCCESS! ✅
echo  ===========================================
echo.
echo  Your .exe is ready:
echo    dist\Bubsy3D_TextureInjector.exe
echo.
echo  To use:
echo    1. Double-click Bubsy3D_TextureInjector.exe
echo    2. Load your Bubsy 3D ROM (.iso, .bin, .cue)
echo    3. Select a texture pack
echo    4. Click INJECT TEXTURES!
echo.

choice /C YN /M "Launch the injector now"
if errorlevel 2 goto :end
if errorlevel 1 start dist\Bubsy3D_TextureInjector.exe

:end
pause
