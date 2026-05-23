"""
SharpIQ — Backend API
FastAPI + PostgreSQL (Railway) + MercadoPago + JWT
"""
import os, sys, json, re, base64, requests as _req
from datetime import datetime, timedelta, date
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Depends, HTTPException, status, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .auth    import router as auth_router, solo_admin, verificar_token
from .members import router as members_router
from .pagos   import router as pagos_router
from .picks   import router as picks_router
from .referidos import router as referidos_router
from .db      import inicializar_db

app = FastAPI(
    title="SharpIQ API",
    version="1.0.0",
    docs_url=None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://sharpiq.co", "https://www.sharpiq.co",
                   "http://localhost:3000", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    inicializar_db()

@app.get("/")
def health():
    return {"status": "ok", "version": "1.0.0", "servicio": "SharpIQ API"}


# ── Admin: Publicar pick → actualiza datos.js en GitHub ──────────

GH_REPO  = "yamidnunezh-hash/sharpiq"
GH_FILE  = "datos.js"
GH_TOKEN = os.environ.get("GH_TOKEN", "")

class PickBody(BaseModel):
    partido:    str
    prediccion: str
    cuota:      str
    hora:       str
    liga:       str = ""
    emoji:      str = ""
    status:     str = "vip"
    ev:         float = 0.0

@app.post("/admin/publicar-pick")
def publicar_pick(body: PickBody, token=Depends(solo_admin)):
    if not GH_TOKEN:
        raise HTTPException(500, "GH_TOKEN no configurado en Railway")

    api_url = f"https://api.github.com/repos/{GH_REPO}/contents/{GH_FILE}"
    headers = {"Authorization": f"token {GH_TOKEN}", "Accept": "application/vnd.github.v3+json"}

    r = _req.get(api_url, headers=headers, timeout=10)
    if not r.ok:
        raise HTTPException(502, f"No se pudo leer datos.js: {r.status_code}")

    file_data = r.json()
    contenido = base64.b64decode(file_data["content"].replace("\n","")).decode("utf-8")

    hoy = date.today().strftime("%d/%m/%y")
    ev_tag = f" — EV +{round(body.ev)}%" if body.ev >= 1 else ""
    nueva = (
        f'\n  {{\n'
        f'    fecha:      "{hoy}",\n'
        f'    partido:    "{body.partido}",\n'
        f'    liga:       "{body.liga}",\n'
        f'    prediccion: "{body.prediccion}{ev_tag}",\n'
        f'    cuota:      "{body.cuota}",\n'
        f'    hora:       "{body.hora}",\n'
        f'    status:     "{body.status}",\n'
        f'    resultado:  "pendiente"\n'
        f'  }},'
    )

    # Verificar si el partido ya está publicado
    partido_norm = body.partido.lower()[:30]
    if partido_norm in contenido.lower():
        raise HTTPException(409, f"El partido '{body.partido}' ya está publicado en datos.js")

    nuevo = re.sub(
        r'(const\s+PROXIMOS_EVENTOS\s*=\s*\[)',
        r'\1' + nueva,
        contenido
    )
    if nuevo == contenido:
        raise HTTPException(500, "No se encontró PROXIMOS_EVENTOS en datos.js")

    nuevo_b64 = base64.b64encode(nuevo.encode("utf-8")).decode("ascii")
    wr = _req.put(api_url, headers=headers, timeout=10, json={
        "message": f"pick: {body.partido} — {body.prediccion}",
        "content": nuevo_b64,
        "sha":     file_data["sha"]
    })
    if not wr.ok:
        raise HTTPException(502, f"GitHub error: {wr.json().get('message','')}")

    return {"ok": True, "partido": body.partido, "prediccion": body.prediccion}


app.include_router(auth_router,      prefix="/auth",      tags=["auth"])
app.include_router(members_router,   prefix="/members",   tags=["members"])
app.include_router(pagos_router,     prefix="/pagos",     tags=["pagos"])
app.include_router(picks_router,     prefix="/picks",     tags=["picks"])
app.include_router(referidos_router, prefix="/referidos", tags=["referidos"])
