@echo off
echo Iniciando SharpIQ Panel...
cd /d "%~dp0"
start "" "http://localhost:8000/predicciones.html"
python -m http.server 8000
pause
