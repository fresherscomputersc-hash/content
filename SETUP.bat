@echo off
rem ============================================================
rem  Flow Labs Content Factory - one-time setup
rem  Double-click this ONCE after cloning/downloading the repo.
rem  After it finishes, use GENERATE.bat every time.
rem ============================================================
setlocal EnableDelayedExpansion
cd /d "%~dp0"

echo.
echo  ================= FLOW LABS CONTENT FACTORY ================
echo   SETUP - run this once. GENERATE.bat - run this daily.
echo  ============================================================
echo.

rem ------------------------------------------------ python ----
where python >nul 2>nul
if errorlevel 1 (
  echo [X] Python not found.
  echo.
  echo     1. Download Python 3.11+ : https://www.python.org/downloads/
  echo     2. In the installer, tick "Add python.exe to PATH"
  echo     3. Open a NEW window and run SETUP.bat again.
  echo.
  pause
  exit /b 1
)
for /f "delims=" %%v in ('python --version 2^>^&1') do echo [OK] %%v

rem ------------------------------------------------ ffmpeg ----
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo [ ] ffmpeg not found. Trying automatic install via winget...
  echo.
  winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
  if errorlevel 1 (
    echo.
    echo [X] Automatic install failed. Do it manually:
    echo     - winget install Gyan.FFmpeg   ^(in any terminal^)
    echo     - or download from https://www.gyan.dev/ffmpeg/builds/
    echo       and add its "bin" folder to your PATH.
    echo     Then open a NEW window and run SETUP.bat again.
    echo.
    pause
    exit /b 1
  )
  rem winget adds ffmpeg to PATH, but this window was started before.
  where ffmpeg >nul 2>nul
  if errorlevel 1 (
    echo.
    echo [OK] ffmpeg installed. Close this window, open a NEW one,
    echo      and run SETUP.bat once more to finish.
    echo.
    pause
    exit /b 0
  )
)
for /f "delims=" %%v in ('ffmpeg -version 2^>^&1') do (
  echo [OK] ffmpeg - %%v
  goto ffmpeg_done
)
:ffmpeg_done

rem ------------------------------------------- python deps ----
echo.
echo Installing python packages (edge-tts, Pillow)...
python -m pip install -r "tools\content-factory\requirements.txt"
if errorlevel 1 (
  echo [X] pip install failed. Check your internet connection and re-run SETUP.bat.
  pause
  exit /b 1
)

rem ------------------------------------------------ done ------
echo.
echo  ============================================================
echo   SETUP COMPLETE.
echo.
echo   Next: double-click GENERATE.bat
echo   - 3 reels + captions + carousels + posting plan,
echo     land in content\YYYY-MM-DD\
echo.
echo   Optional: hear the voices first -
echo     python tools\content-factory\voice-test.py
echo   Then: AUTOPSY.bat --url https://any-website.com
echo  ============================================================
echo.
pause
