@echo off
REM Meowth-AXVJ — JP ROM binary inject (primary product path)
cd /d "%~dp0"

if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

set PYTHONPATH=%cd%\src

python -c "import customtkinter" 2>nul
if errorlevel 1 (
    echo Missing GUI deps. Run:
    echo   pip install -e ".[gui]"
    pause
    exit /b 1
)

python -m meowth.gui.app
if errorlevel 1 (
    echo.
    echo GUI exited with an error.
    pause
)
