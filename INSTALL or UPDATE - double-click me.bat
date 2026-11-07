@echo off
title Deviant Forge installer
cd /d "%~dp0"
set "INST=%~dp0app\forge_install.py"
if not exist "%INST%" set "INST=%~dp0forge_install.py"
if not exist "%INST%" (
  echo.
  echo   The zip is not extracted yet.
  echo   Close this window, right-click the Deviant Forge zip and choose "Extract All...",
  echo   then open the extracted folder and double-click this file again.
  echo.
  pause
  exit /b 1
)
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)" >nul 2>&1 && set "PY=python"
if not defined PY (
  echo Deviant Forge needs Python 3.10 or newer, and it was not found.
  echo Opening the Python download page. During setup, tick "Add python.exe to PATH",
  echo then double-click this file again.
  start "" "https://www.python.org/downloads/windows/"
  pause
  exit /b 1
)
%PY% "%INST%"
echo.
pause
