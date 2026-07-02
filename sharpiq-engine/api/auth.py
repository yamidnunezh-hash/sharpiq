"""
SharpIQ — Autenticación JWT
"""
import os, sys, secrets, hashlib, string
from datetime import datetime, timedelta
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
import jwt

from .db import db

router  = APIRouter()
bearer  = HTTPBearer()

JWT_SECRET  = os.environ.get("JWT_SECRET")
if not JWT_SECRET or len(JWT_SECRET) < 16:
    # NUNCA usar una clave por defecto insegura: sin un JWT_SECRET real (largo) el
    # sistema NO arranca. Con la clave por defecto cualquiera podría forjar tokens admin.
    raise RuntimeError(
        "JWT_SECRET no está configurado o es muy corto (<16). Ponlo como variable de "
        "entorno en Railway con una clave larga y aleatoria antes de arrancar."
    )
JWT_ALGO    = "HS256"
JWT_EXPIRY  = 30  # días

# ── SMTP (verificación de correo vía Zoho) ───────────────────────
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.zoho.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
try:
    from config import SMTP_USER, SMTP_PASS
except Exception:
    SMTP_USER = os.environ.get("SMTP_USER", "info@sharpiq.co")
    SMTP_PASS = os.environ.get("SMTP_PASS", "")
BASE_API = os.environ.get("BASE_API", "https://api.sharpiq.co")


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


# ── Verificación de correo ───────────────────────────────────────

def _enviar_verificacion(email: str, nombre: str, token: str) -> bool:
    """Envía el correo de verificación por SMTP (Zoho). True si se envió."""
    if not SMTP_PASS:
        return False
    import smtplib, ssl
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    link = f"{BASE_API}/auth/verificar?token={token}"
    html = f"""<div style="font-family:Arial,sans-serif;background:#0a0e1a;color:#eef3fb;padding:32px;border-radius:12px;max-width:480px;margin:auto">
      <div style="font-size:26px">🦈 <b>SharpIQ</b></div>
      <h2 style="color:#00C8FF">Confirma tu correo</h2>
      <p>Hola {nombre}, gracias por unirte a SharpIQ. Confirma tu correo para activar tu cuenta y usar a <b>Mako</b> gratis 🦈.</p>
      <p style="text-align:center;margin:28px 0">
        <a href="{link}" style="background:linear-gradient(135deg,#00C8FF,#7B5CF0);color:#fff;text-decoration:none;padding:14px 30px;border-radius:10px;font-weight:bold">Verificar mi correo</a>
      </p>
      <p style="font-size:12px;color:#97a6bd">Si el botón no abre, copia este enlace:<br>{link}</p>
      <p style="font-size:12px;color:#97a6bd">Si no creaste esta cuenta, ignora este mensaje.</p>
    </div>"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = "Verifica tu correo — SharpIQ 🦈"
    msg["From"]    = f"SharpIQ <{SMTP_USER}>"
    msg["To"]      = email
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=20) as s:
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_USER, [email], msg.as_string())
        return True
    except Exception as e:
        print("[verificacion] error enviando:", e)
        return False


def _pagina_verificado(ok: bool) -> str:
    if ok:
        titulo, msg, color = "✅ ¡Correo verificado!", "Tu cuenta quedó activa. Ya puedes usar a Mako 🦈.", "#22c55e"
    else:
        titulo, msg, color = "Enlace inválido o vencido", "Vuelve a solicitar el correo de verificación desde tu cuenta.", "#ef4444"
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>SharpIQ</title></head>
    <body style="font-family:Arial,sans-serif;background:#0a0e1a;color:#eef3fb;display:flex;align-items:center;justify-content:center;min-height:100vh;margin:0">
      <div style="text-align:center;max-width:420px;padding:32px">
        <div style="font-size:40px">🦈</div>
        <h1 style="color:{color}">{titulo}</h1>
        <p style="color:#97a6bd">{msg}</p>
        <a href="https://sharpiq.co/login.html" style="display:inline-block;margin-top:18px;background:linear-gradient(135deg,#00C8FF,#7B5CF0);color:#fff;text-decoration:none;padding:13px 28px;border-radius:10px;font-weight:bold">Ir a SharpIQ</a>
      </div>
    </body></html>"""


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

        # Verificación de correo: con SMTP activo el usuario nace SIN verificar y debe
        # confirmar; sin SMTP nace verificado (no bloqueamos el trial de Mako).
        token_verif = secrets.token_urlsafe(32) if SMTP_PASS else None
        email_verif = not bool(SMTP_PASS)

        cur.execute("""
            INSERT INTO usuarios (email, nombre, password_hash, plan, referido_por, codigo_ref,
                                  email_verificado, token_verificacion)
            VALUES (%s,%s,%s,'free',%s,%s,%s,%s)
            RETURNING id, plan
        """, (body.email.lower(), body.nombre, _hash(body.password), ref_id, codigo,
              email_verif, token_verif))
        row = cur.fetchone()
        user_id = row["id"]

        # Registrar referido si aplica
        if ref_id:
            cur.execute("""
                INSERT INTO referidos (referidor_id, referido_id)
                VALUES (%s,%s) ON CONFLICT DO NOTHING
            """, (ref_id, user_id))

    # Fuera de la transacción: enviar el correo de verificación (si aplica).
    if token_verif:
        _enviar_verificacion(body.email.lower(), body.nombre, token_verif)

    token = _crear_token(user_id, body.email.lower(), "free")
    return {"ok": True, "token": token, "plan": "free", "codigo_ref": codigo,
            "verificar_correo": bool(token_verif)}


@router.get("/verificar")
def verificar_correo(token: str):
    """Enlace del correo: marca el correo como verificado. Devuelve una página."""
    ok = False
    if token:
        with db() as conn:
            cur = conn.cursor()
            cur.execute("""UPDATE usuarios SET email_verificado=TRUE, token_verificacion=NULL
                           WHERE token_verificacion=%s RETURNING id""", (token,))
            ok = cur.fetchone() is not None
    return HTMLResponse(content=_pagina_verificado(ok))


@router.post("/reenviar-verificacion")
def reenviar_verificacion(token=Depends(usuario_activo)):
    """Reenvía el correo de verificación al usuario logueado."""
    user_id = int(token["sub"])
    nuevo = secrets.token_urlsafe(32)
    with db() as conn:
        cur = conn.cursor()
        cur.execute("SELECT email, nombre, email_verificado FROM usuarios WHERE id=%s", (user_id,))
        u = cur.fetchone()
        if not u:
            raise HTTPException(404, "Usuario no encontrado")
        if u.get("email_verificado"):
            return {"ok": True, "ya_verificado": True}
        cur.execute("UPDATE usuarios SET token_verificacion=%s WHERE id=%s", (nuevo, user_id))
    enviado = _enviar_verificacion(u["email"], u["nombre"], nuevo)
    return {"ok": enviado, "email": u["email"]}


@router.get("/diag-smtp")
def diag_smtp(clave: str = "", to: str = ""):
    """TEMPORAL: diagnóstico del login/envío SMTP. Borrar tras diagnosticar."""
    if clave != "sqdiag2026":
        raise HTTPException(403, "no")
    out = {"host": SMTP_HOST, "port": SMTP_PORT, "user": SMTP_USER, "pass_set": bool(SMTP_PASS)}
    import smtplib, ssl
    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, context=ctx, timeout=15) as s:
            s.login(SMTP_USER, SMTP_PASS or "")
            out["login"] = "OK"
        if to:
            out["send"] = "OK" if _enviar_verificacion(to, "Prueba SharpIQ", "diag-token-123") else "FALLO"
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


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
