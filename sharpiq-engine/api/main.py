"""
SharpIQ — Backend API
FastAPI + PostgreSQL (Railway) + MercadoPago + JWT
"""
import os, sys, json
from datetime import datetime, timedelta, date
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Depends, HTTPException, status, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .auth    import router as auth_router
from .members import router as members_router
from .pagos   import router as pagos_router
from .picks   import router as picks_router
from .referidos import router as referidos_router
from .db      import inicializar_db

app = FastAPI(
    title="SharpIQ API",
    version="1.0.0",
    docs_url=None,   # Ocultar docs en producción
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

app.include_router(auth_router,      prefix="/auth",      tags=["auth"])
app.include_router(members_router,   prefix="/members",   tags=["members"])
app.include_router(pagos_router,     prefix="/pagos",     tags=["pagos"])
app.include_router(picks_router,     prefix="/picks",     tags=["picks"])
app.include_router(referidos_router, prefix="/referidos", tags=["referidos"])
