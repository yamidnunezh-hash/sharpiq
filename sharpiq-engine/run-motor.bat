@echo off
cd /d "%~dp0"
if not exist logs mkdir logs

python -X utf8 procesar_referidos.py >> logs\referidos.log 2>&1
python -X utf8 auto_resultados.py >> logs\resultados.log 2>&1
python -X utf8 recolector.py ayer >> logs\recolector.log 2>&1
python -X utf8 motor.py >> logs\motor.log 2>&1
python -X utf8 auto_publicar.py >> logs\auto_publicar.log 2>&1