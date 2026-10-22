@echo off
rem Builds dist\layoutfix.exe - a single file that needs no Python installed.
rem
rem --noupx matters: UPX-packed executables trip far more antivirus heuristics,
rem and this tool already looks suspicious to them (it sends keystrokes and
rem reads the clipboard). The few MB saved are not worth the false positives.

set "PY=%LOCALAPPDATA%\Python\bin\python.exe"
if not exist "%PY%" set "PY=python"

"%PY%" make_icon.py
"%PY%" -m PyInstaller ^
    --onefile ^
    --noconsole ^
    --noupx ^
    --clean ^
    --name layoutfix ^
    --icon layoutfix.ico ^
    --version-file version.txt ^
    layoutfix.py

echo.
echo Built: dist\layoutfix.exe
