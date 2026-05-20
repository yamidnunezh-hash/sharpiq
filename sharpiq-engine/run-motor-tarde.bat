@echo off
cd /d "%~dp0"
python -X utf8 motor.py >> logs\motor-tarde.log 2>&1
