@echo off
cd /d "%~dp0"
python -X utf8 auto_resultados.py >> logs\resultados.log 2>&1
python -X utf8 recolector.py ayer >> logs\recolector.log 2>&1
python -X utf8 motor.py >> logs\motor.log 2>&1

REM Segunda pasada a las 16:00 — detecta movimiento de línea
REM (Programar en Tareas de Windows: run-motor-tarde.bat a las 16:00)
