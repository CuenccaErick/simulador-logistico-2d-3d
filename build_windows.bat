@echo off
REM Genera dist\SimuladorLogistico.exe  (antes: pip install -r requirements.txt)
pyinstaller --noconfirm --onefile --windowed --name SimuladorLogistico ^
  --add-data "escenarios;escenarios" ^
  --collect-all moderngl --collect-all glcontext ^
  main.py
echo.
echo Listo: dist\SimuladorLogistico.exe
pause
