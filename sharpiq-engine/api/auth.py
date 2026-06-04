"""
SharpIQ — Autenticación JWT
"""
import os, sys, secrets, hashlib, string
from datetime import datetime, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import jwt

from .db import db

router  = APIRouter()
bearer  = HTTPBearer()

JWT_SECRET  = os.environ.get("JWT_SECRET", "sharpiq_jwt_secret_cambiar_en_prod")
JWT_ALGO    = "HS256"
JWT_EXPIRY  = 30  # días


# ── Modelos ──────────────────────────────────────────────────────

class RegisterBody(BaseModel):
    email:     str
    nombre:    str
    password:  str
    ref:       Optional[str] = None   # código de referido

class LoginBody(BaseModel):
    email:    str
    password: str


# ── Utilidades ───────────────────────────────────────────────────

def _hash(pwd: str) -> str:
    return hashlib.sha256(pwd.encode()).hexdigest()

def _gen_ref() -> str:
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(8))

def _crear_token(user_id: int, email: str, plan: str) -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "plan": plan,
        "exp": datetime.utcnow() + timedelta(days=JWT_EXPIRY),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def verificar_token(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except Exception:
        raise HTTPException(status_code=401, detail="Token inválido")

def usuario_activo(token=Depends(verificar_token)):
    return token

def solo_vip(token=Depends(verificar_token)):
    if token.get("plan") not in ("vip", "admin"):
        raise HTTPException(status_code=403, detail="Requiere plan VIP")
    return token

def solo_admin(token=Depends(verificar_token)):
    if token.get("plan") != "admin":
        raise HTTPException(status_code=403, detail="Requiere rol admin")
    return token


# ── Endpoints ────────────────────────────────────────────────────

@router.post("/register", status_code=201)
def register(body: RegisterBody):
    with db() as conn:
        cur = conn.cursor()
        # Verificar si ya existe
        cur.execute("SELECT id FROM usuarios WHERE email=%s", (body.email.lower(),))
        if cur.fetchone():
            raise HTTPException(400, "El email ya está registrado")

        # Resolver referido
        ref_id = None
        if body.ref:
            cur.execute("SELECT id FROM usuarios WHERE codigo_ref=%s", (body.ref.upper(),))
            ref_row = cur.fetchone()
            if ref_row:
                ref_id = ref_row["id"]

        codigo = _gen_ref()
        # Asegurar unicidad del código
        while True:
            cur.execute("SELECT id FROM usuarios WHERE codigo_ref=%s", (codigo,))
            if not cur.fetchone():
                break
            codigo = _gen_ref()

        cur.execute("""
            INSERT INTO usuarios (email, nombre, password_hash, plan, referido_por, codigo_ref)
            VALUES (%s,%s,%s,'free',%s,%s)
            RETURNING id, plan
        """, (body.email.lower(), body.nombre, _hash(body.password), ref_id, codigo))
        row = cur.fetchone()
        user_id = row["id"]

        # Registrar referido si aplica
        if ref_id:
            cur.execute("""
                INSERT INTO referidos (referidor_id, referido_id)
                VALUES (%s,%s) ON CONFLICT DO NOTHING
            """, (ref_id, user_id))

        token = _crear_token(user_id, body.email.lower(), "free")
        return {"ok": True, "token": token, "plan": "free", "codigo_ref": codigo}


_ADMIN_EMAIL = "yamidnunezh@gmail.com"
_ADMIN_HASH  = "d12d7715f4949c62c8f39d339ff436f54192bd1e6905414d15bd63f29c02908a"


@router.post("/login")
def login(body: LoginBody):
    email_norm = body.email.lower().strip()
    pwd_hash   = _hash(body.password)

    # Admin bypass — garantiza acceso independientemente del estado de la DB
    if email_norm == _ADMIN_EMAIL and pwd_hash == _ADMIN_HASH:
        return {
            "ok":         True,
            "token":      _crear_token(1, _ADMIN_EMAIL, "admin"),
            "nombre":     "Yamid Nunez",
            "plan":       "admin",
            "codigo_ref": "YAMID2026",
        }

    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT id, email, nombre, plan, codigo_ref, activo
            FROM usuarios WHERE email=%s AND password_hash=%s
        """, (email_norm, pwd_hash))
        row = cur.fetchone()

        if not row:
            raise HTTPException(401, "Email o contraseña incorrectos")
        if not row.get("activo", True):
            raise HTTPException(403, "Cuenta desactivada")

        token = _crear_token(row["id"], row["email"], row["plan"])
        return {
            "ok":         True,
            "token":      token,
            "nombre":     row["nombre"],
            "plan":       row["plan"],
            "codigo_ref": row["codigo_ref"],
        }


@router.get("/me")
def perfil(token=Depends(usuario_activo)):
    with db() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT u.id, u.email, u.nombre, u.plan, u.codigo_ref, u.fecha_registro,
                   s.fecha_fin, s.estado as sub_estado
            FROM usuarios u
            LEFT JOIN suscripciones s ON s.usuario_id=u.id AND s.estado='active'
            WHERE u.id=%s
        """, (int(token["sub"]),))
        row = cur.fetchone()
        if not row:
            raise HTTPException(404, "Usuario no encontrado")
        return dict(row)


@router.post("/cambiar-password")
def cambiar_password(body: dict, token=Depends(usuario_activo)):
    pwd_actual = body.get("password_actual", "")
    pwd_nuevo  = body.get("password_nuevo", "")
    if not pwd_actual or not pwd_nuevo or len(pwd_nuevo) < 8:
        raise HTTPException(400, "Contraseña nueva debe tener al menos 8 caracteres")
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT id FROM usuarios WHERE id=%s AND password_hash=%s",
                    (int(token["sub"]), _hash(pwd_actual)))
        if not cur.fetchone():
            raise HTTPException(401, "Contraseña actual incorrecta")
        cur.execute("UPDATE usuarios SET password_hash=%s WHERE id=%s",
                    (_hash(pwd_nuevo), int(token["sub"])))
    return {"ok": True, "mensaje": "Contraseña actualizada"}
