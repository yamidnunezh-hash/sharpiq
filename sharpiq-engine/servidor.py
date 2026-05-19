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
WEB_DIR = os.path.join(BASE_DIR, "..")
DATOS_JS = os.path.join(WEB_DIR, "datos.js")

class SharpIQHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, format, *args):
        # Solo mostrar errores, no cada request
        if args[1] not in ('200', '304'):
            print(f"  [{args[1]}] {args[0]}")

    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    def do_POST(self):
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
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path.startswith("/api/"):
            self.send_response(404)
            self.end_headers()
            return
        super().do_GET()

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
    return {"ok": True, "mensaje": f"Publicado: {partido}", "git": git_ok}


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
