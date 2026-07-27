@echo off
setlocal
cd /d "%~dp0\.."
set PYTHONPATH=%cd%\src
set ROM=C:\code\gba\localization\ruby-jp-chs\baserom.gba
if not exist "%ROM%" (
  echo ERROR: baserom missing: %ROM%
  exit /b 1
)

echo === 1) Extract JP texts ===
python -m meowth extract "%ROM%" -o work\texts.json --source ja --target zh-Hans
if errorlevel 1 exit /b 1

echo === 2) Seed translate (offline) ===
python -m meowth seed-translate work\texts.json -o work\texts_translated.json --only-seeded
if errorlevel 1 exit /b 1

echo === 3) Build ROM (font patch + inject) ===
python -m meowth build "%ROM%" --translations work\texts_translated.json -o outputs\axvj_zh_demo.gba --source ja --target zh-Hans
if errorlevel 1 exit /b 1

echo.
echo OK: outputs\axvj_zh_demo.gba
echo Open with mGBA yourself to check main-menu Chinese seeds.
exit /b 0
