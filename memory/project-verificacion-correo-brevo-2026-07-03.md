---
name: project-verificacion-correo-brevo-2026-07-03
description: 2026-07-03 Verificación de correo EN VIVO vía Brevo (dominio sharpiq.co autentificado en Cloudflare). Cierra el anti-abuso del trial free de Mako. Confirmado: correo llega a la bandeja.
metadata:
  type: project
---

# Verificación de correo — EN VIVO vía Brevo (2026-07-03)

Anti-abuso del trial free de Mako: sin esto la gente creaba correos "a la loca" para
usar el free infinito. Ver [[project-mako-pulido-2026-07-01]].

## Cómo quedó (desplegado, SW v97)
- **Envío por Brevo API HTTP** (POST api.brevo.com/v3/smtp/email, header `api-key: xkeysib-...`,
  puerto 443). Railway BLOQUEA SMTP (465/587) → por eso NO se usa Zoho SMTP; Brevo por HTTP sí pasa.
  `BREVO_API_KEY` ya en Railway. Sender = **info@sharpiq.co** (empresa, vive en Zoho).
  SMTP queda solo como respaldo muerto en el código.
- **Dominio sharpiq.co AUTENTIFICADO en Brevo** (clave para que llegue a la BANDEJA, no spam):
  el DNS vive en **Cloudflare** → Brevo lo autenticó automático (opción "Autenticar el dominio
  automáticamente" → Authorize) agregando TXT brevo-code, TXT _dmarc y 2 CNAME brevoN._domainkey (DKIM).
  Estado en Brevo: "Autentificado" (punto verde). CONFIRMADO: correo de prueba llegó a la bandeja de Zoho.
- **Backend** (sharpiq-engine/api/auth.py): `_enviar_verificacion` (Brevo 1º, SMTP respaldo);
  register crea al free SIN verificar (`email_verificado=FALSE`, `token_verificacion`) SOLO si
  `_EMAIL_ACTIVO` (hay BREVO_API_KEY o SMTP_PASS); default de la columna es TRUE (grandfather).
  `GET /auth/verificar?token=` marca verificado + muestra HTML; `POST /auth/reenviar-verificacion` (auth).
  El endpoint temporal `/auth/diag-smtp` YA SE BORRÓ.
- **Gate en Mako** (api/mako.py `_estado`): free sin verificar → `puede=False, tipo="verificar",
  verificar=True`. `preguntar` bloqueado ahora también devuelve `tipo`/`verificar`.
- **Frontend**: mako.html tiene `verificaBox()` (📧 + botón "REENVIAR CORREO DE VERIFICACIÓN" →
  POST /auth/reenviar-verificacion); registro.html avisa "revisa tu correo" si `verificar_correo`.

## Nota
- El correo de prueba mostró "Cancelar suscripción" en Zoho (footer que mete Brevo). Los de
  verificación son transaccionales; si molesta, se puede quitar el footer en Brevo. Menor.

## HITO del mismo día (validación del producto)
Yamid ganó una **TRIPLE @5.30 real ($20.000 → $106.000)** armada **CON MAKO**: Mako le dio remate
de Bruno Fernandes +0.5, faltas de Budimir +1.5 y ambos marcan — los mercados de JUGADOR que
construimos. Prueba viva de que Mako convierte el motor en jugadas que pagan. Es la experiencia
exacta que se le vende al cliente VIP.
