@echo off
chcp 65001 >nul
cd /d "C:\Users\INGENIERO\Documents\Documentos Yamid Nuñez 2026\Divisual Project\10 SKILLS ADRI Y JUANPE\10 SKILLS ADRI Y JUANPE\kit-web-scrolling"

echo [%date% %time%] Iniciando motor SharpIQ... >> sharpiq-engine\motor_log.txt
py sharpiq-engine/motor.py >> sharpiq-engine\motor_log.txt 2>&1
echo [%date% %time%] Motor finalizado. >> sharpiq-engine\motor_log.txt
