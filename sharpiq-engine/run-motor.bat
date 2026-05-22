@echo off
cd /d "%~dp0"
if not exist logs mkdir logs

echo [%DATE% %TIME%] ===== SharpIQ Motor arrancando ===== >> logs\motor.log 2>&1

REM 1. Procesar referidos del bot (no-blocking, max 30s)
echo [%DATE% %TIME%] Paso 1: referidos bot >> logs\motor.log 2>&1
python -X utf8 -c "import sys,os,signal; sys.path.insert(0,os.getcwd()); [__import__('telegram_alertas').procesar_updates_bot() if True else None for _ in [1]]" >> logs\referidos.log 2>&1
echo [%DATE% %TIME%] Paso 1 OK (exit %ERRORLEVEL%) >> logs\motor.log 2>&1

REM 2. Auto resultados partidos de ayer
echo [%DATE% %TIME%] Paso 2: auto_resultados >> logs\motor.log 2>&1
python -X utf8 auto_resultados.py >> logs\resultados.log 2>&1
echo [%DATE% %TIME%] Paso 2 OK (exit %ERRORLEVEL%) >> logs\motor.log 2>&1

REM 3. Recolector
echo [%DATE% %TIME%] Paso 3: recolector >> logs\motor.log 2>&1
python -X utf8 recolector.py ayer >> logs\recolector.log 2>&1
echo [%DATE% %TIME%] Paso 3 OK (exit %ERRORLEVEL%) >> logs\motor.log 2>&1

REM 4. Motor principal — CRITICO
echo [%DATE% %TIME%] Paso 4: motor.py >> logs\motor.log 2>&1
python -X utf8 motor.py >> logs\motor.log 2>&1
echo [%DATE% %TIME%] Paso 4 OK (exit %ERRORLEVEL%) >> logs\motor.log 2>&1

REM 5. Auto publicar
echo [%DATE% %TIME%] Paso 5: auto_publicar >> logs\motor.log 2>&1
python -X utf8 auto_publicar.py >> logs\auto_publicar.log 2>&1
echo [%DATE% %TIME%] Paso 5 OK (exit %ERRORLEVEL%) >> logs\motor.log 2>&1

echo [%DATE% %TIME%] ===== SharpIQ Motor COMPLETADO ===== >> logs\motor.log 2>&1
