# -*- coding: utf-8 -*-
"""
SharpIQ — Servidor Local
Sirve archivos estaticos + endpoint para publicar predicciones a datos.js
"""
import os
import re
import json
import subprocess
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

import sys
sys.path.insert(0, BASE_DIR)
try:
    from telegram_alertas import enviar_mensaje as _tg_send
    _TELEGRAM_OK = True
except Exception:
    _TELEGRAM_OK = False
WEB_DIR = os.path.join(BASE_DIR, "..")
DATOS_JS = os.path.join(WEB_DIR, "datos.js")

try:
    from config import PANEL_TOKEN as _PANEL_TOKEN
except Exception:
    _PANEL_TOKEN = ""


class SharpIQHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, format, *args):
        if args[1] not in ('200', '304'):
            print(f"  [{args[1]}] {args[0]}")

    def _token_valido(self):
        auth = self.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            return auth[7:] == _PANEL_TOKEN
        return False

    def _sin_auth(self):
        self.send_response(401)
        self._cors()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ok": False, "error": "No autorizado"}).encode())

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_GET(self):
        if self.path == "/api/vapid-public-key":
            try:
                from config import VAPID_PUBLIC_KEY
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"key": VAPID_PUBLIC_KEY}).encode())
            except Exception as e:
                self.send_response(500)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return
        if self.path == "/api/pendientes":
            try:
                pendientes = leer_pendientes()
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(pendientes).encode())
            except Exception as e:
                self.send_response(500)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            return
        if self.path.startswith("/api/"):
            self.send_response(404)
            self.end_headers()
            return
        super().do_GET()

    def do_POST(self):
        if not self._token_valido():
            self._sin_auth()
            return
        if self.path == "/api/publicar":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                resultado = publicar_en_datos_js(data)
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(resultado).encode())
            except Exception as e:
                self.send_response(500)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())
        elif self.path == "/api/subscribe":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                sub = json.loads(body)
                from push_notifications import guardar_suscripcion
                nueva = guardar_suscripcion(sub)
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": True, "nueva": nueva}).encode())
            except Exception as e:
                self.send_response(500)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())
        elif self.path == "/api/resultado":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                data = json.loads(body)
                resultado = actualizar_resultado(data["partido"], data["resultado"])
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(resultado).encode())
            except Exception as e:
                self.send_response(500)
                self._cors()
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"ok": False, "error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")


def publicar_en_datos_js(pred):
    fecha = datetime.now().strftime("%d/%m/%y")
    partido = f"{pred['local']} vs {pred['visitante']}"
    liga = pred.get("liga", "")
    mercado = pred.get("mercado", pred["prediccion_principal"]["mercado"])
    cuota = str(pred.get("cuota_publicar", ""))
    hora = pred.get("hora_local", pred.get("hora", "") + " UTC")
    status = pred.get("status", "vip")

    nuevo = f"""  {{
    fecha:      "{fecha}",
    partido:    "{partido}",
    liga:       "{liga}",
    prediccion: "{mercado}",
    cuota:      "{cuota}",
    hora:       "{hora}",
    status:     "{status}"
  }},\n"""

    with open(DATOS_JS, "r", encoding="utf-8") as f:
        contenido = f.read()

    # Insertar al inicio de PROXIMOS_EVENTOS
    patron = r"(const PROXIMOS_EVENTOS\s*=\s*\[)"
    if not re.search(patron, contenido):
        return {"ok": False, "error": "No se encontro PROXIMOS_EVENTOS en datos.js"}

    nuevo_contenido = re.sub(patron, r"\1\n" + nuevo, contenido, count=1)

    with open(DATOS_JS, "w", encoding="utf-8") as f:
        f.write(nuevo_contenido)

    git_ok = git_push_auto(partido)
    _telegram_nueva_prediccion(partido, liga, mercado, cuota, hora, status)
    return {"ok": True, "mensaje": f"Publicado: {partido}", "git": git_ok}


def leer_pendientes():
    with open(DATOS_JS, "r", encoding="utf-8") as f:
        contenido = f.read()
    # Extraer bloque PREDICCIONES_HISTORIAL
    m = re.search(r"const PREDICCIONES_HISTORIAL\s*=\s*(\[.*?\]);", contenido, re.DOTALL)
    if not m:
        return []
    bloque = m.group(1)
    pendientes = []
    entradas = re.finditer(
        r'\{[^}]*partido\s*:\s*"([^"]+)"[^}]*prediccion\s*:\s*"([^"]+)"[^}]*cuota\s*:\s*"([^"]+)"[^}]*resultado\s*:\s*"(pending)"[^}]*\}',
        bloque, re.DOTALL
    )
    for e in entradas:
        pendientes.append({
            "partido": e.group(1),
            "prediccion": e.group(2),
            "cuota": e.group(3),
        })
    return pendientes


def actualizar_resultado(partido, resultado):
    with open(DATOS_JS, "r", encoding="utf-8") as f:
        contenido = f.read()

    # Reemplazar resultado: "pending" por win/loss solo para ese partido
    patron = r'(partido\s*:\s*"' + re.escape(partido) + r'".*?resultado\s*:\s*)"pending"'
    nuevo_contenido = re.sub(patron, r'\1"' + resultado + '"', contenido, count=1, flags=re.DOTALL)

    if nuevo_contenido == contenido:
        return {"ok": False, "error": "Partido no encontrado o ya actualizado"}

    with open(DATOS_JS, "w", encoding="utf-8") as f:
        f.write(nuevo_contenido)

    git_push_auto(f"Resultado: {partido} → {resultado}")
    return {"ok": True, "mensaje": f"{partido} → {resultado}"}


def _telegram_nueva_prediccion(partido, liga, mercado, cuota, hora, status):
    if not _TELEGRAM_OK:
        return
    try:
        emoji = "🔥" if "EV" in mercado else "⚽"
        texto = (
            f"{emoji} <b>SharpIQ — Nueva predicción VIP</b>\n\n"
            f"⚽ <b>{partido}</b>\n"
            f"🏆 {liga} | {hora}\n"
            f"📊 <b>Mercado:</b> {mercado}\n"
            f"💵 <b>Cuota:</b> {cuota}\n\n"
            f"<i>SharpIQ — La ventaja inteligente</i>"
        )
        ok = _tg_send(texto)
        print(f"  Telegram {'OK' if ok else 'ERROR'}: {partido}")
    except Exception as e:
        print(f"  Telegram error: {e}")


def git_push_auto(partido):
    try:
        cwd = WEB_DIR
        subprocess.run(["git", "add", "datos.js"], cwd=cwd, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", f"Prediccion: {partido}"], cwd=cwd, check=True, capture_output=True)
        subprocess.run(["git", "push"], cwd=cwd, check=True, capture_output=True)
        print(f"  git push OK: {partido}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  git push error: {e.stderr.decode() if e.stderr else e}")
        return False


if __name__ == "__main__":
    PORT = 8080
    print(f"\n  SharpIQ Servidor corriendo en http://localhost:{PORT}")
    print(f"  Panel: http://localhost:{PORT}/predicciones.html")
    print(f"  (no cierres esta ventana)\n")
    server = HTTPServer(("", PORT), SharpIQHandler)
    server.serve_forever()
