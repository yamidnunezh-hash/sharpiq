@echo off
cd /d "%~dp0"
python -X utf8 recolector.py ayer >> logs\recolector.log 2>&1
python -X utf8 motor.py >> logs\motor.log 2>&1
