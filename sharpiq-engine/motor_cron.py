"""
SharpIQ — Motor Cron para Railway
Corre el motor automáticamente:
  9:00 AM COT  = 14:00 UTC
  4:00 PM COT  = 21:00 UTC
  11:30 PM COT = 04:30 UTC (resultados automáticos)
No requiere Windows Task Scheduler ni PC encendido.
"""
import time
import subprocess
import sys
import os
from datetime import datetime, timezone, timedelta

COT = timezone(timedelta(hours=-5))

# Horarios en hora COT (hora, minuto)
HORARIOS = [
    (9,  0,  "motor"),       # 9:00 AM — barrido mañana
    (16, 0,  "motor"),       # 4:00 PM — barrido tarde
    (23, 30, "resultados"),  # 11:30 PM — cierre del día
]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_ejecutado_hoy = set()


def _clave(hora, minuto, tarea):
    hoy = datetime.now(COT).date().isoformat()
    return f"{hoy}_{hora}:{minuto}_{tarea}"


def ejecutar_motor():
    print(f"[CRON] Ejecutando motor — {datetime.now(COT).strftime('%Y-%m-%d %H:%M COT')}")
    try:
        resultado = subprocess.run(
            [sys.executable, os.path.join(BASE_DIR, "motor.py")],
            timeout=600,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        print(resultado.stdout[-3000:] if resultado.stdout else "(sin salida)")
        if resultado.returncode != 0:
            print(f"[CRON] Error motor: {resultado.stderr[-1000:]}")
    except subprocess.TimeoutExpired:
        print("[CRON] Motor timeout (10 min) — puede que la API esté lenta")
    except Exception as e:
        print(f"[CRON] Error inesperado: {e}")


def ejecutar_resultados():
    print(f"[CRON] Procesando resultados — {datetime.now(COT).strftime('%Y-%m-%d %H:%M COT')}")
    try:
        resultado = subprocess.run(
            [sys.executable, os.path.join(BASE_DIR, "auto_resultados.py")],
            timeout=120,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        print(resultado.stdout[-1000:] if resultado.stdout else "(sin salida)")
    except Exception as e:
        print(f"[CRON] Resultados error: {e}")


print("[CRON] SharpIQ Motor iniciado en Railway")
print(f"[CRON] Horarios COT: 9:00 AM (motor) | 4:00 PM (motor) | 11:30 PM (resultados)")
print(f"[CRON] Hora actual: {datetime.now(COT).strftime('%Y-%m-%d %H:%M %Z')}")

while True:
    ahora = datetime.now(COT)
    hora  = ahora.hour
    minuto = ahora.minute

    for h, m, tarea in HORARIOS:
        clave = _clave(h, m, tarea)
        if hora == h and minuto == m and clave not in _ejecutado_hoy:
            _ejecutado_hoy.add(clave)
            if tarea == "motor":
                ejecutar_motor()
            elif tarea == "resultados":
                ejecutar_resultados()

    # Limpiar registro al cambiar de día
    if hora == 0 and minuto == 1:
        _ejecutado_hoy.clear()

    time.sleep(45)  # revisar cada 45 segundos
