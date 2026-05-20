@echo off
cd /d "%~dp0"
python -X utf8 -c "import sys,os;sys.path.insert(0,os.getcwd());from telegram_alertas import procesar_updates_bot;procesar_updates_bot()" >> logs\referidos.log 2>&1
python -X utf8 auto_resultados.py >> logs\resultados.log 2>&1
python -X utf8 recolector.py ayer >> logs\recolector.log 2>&1
python -X utf8 motor.py >> logs\motor.log 2>&1
python -X utf8 auto_publicar.py >> logs\auto_publicar.log 2>&1

REM Segunda pasada a las 16:00 — detecta movimiento de línea
REM (Programar en Tareas de Windows: run-motor-tarde.bat a las 16:00)
