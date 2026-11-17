#!/usr/bin/env bash
# Genera dist/SimuladorLogistico (Linux/macOS). Antes: pip install -r requirements.txt
pyinstaller --noconfirm --onefile --windowed --name SimuladorLogistico \
  --add-data "escenarios:escenarios" \
  --collect-all moderngl --collect-all glcontext \
  main.py
echo "Listo: dist/SimuladorLogistico"
