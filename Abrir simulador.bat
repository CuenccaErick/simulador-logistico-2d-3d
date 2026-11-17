@echo off
REM Doble clic para abrir el menu del simulador
cd /d "%~dp0"
py main.py
if errorlevel 1 (
  echo.
  echo Algo salio mal. Revisa que Python este instalado: https://www.python.org
  pause
)
