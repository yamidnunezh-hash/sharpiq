@echo off
chcp 65001 >nul
title SharpIQ Motor
cd /d "%~dp0"

echo.
echo  ================================
echo   SharpIQ - Generando predicciones
echo  ================================
echo.

py sharpiq-engine/motor.py

echo.
echo  Abriendo panel...
start http://localhost:8080/predicciones.html

echo  Servidor activo en localhost:8080
echo  (no cierres esta ventana)
echo.
py sharpiq-engine/servidor.py
