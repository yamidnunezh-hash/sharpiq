---
name: project-cripto-pago-automatico-resuelto-2026-07-03
description: RESUELTO 2026-07-03. El pago cripto YA activa el VIP automáticamente. La causa era que listar pagos en NOWPayments exige JWT (POST /v1/auth), no solo la API key. Reconciliación por API, sin depender del webhook.
metadata:
  type: project
---

# Pago cripto AUTOMÁTICO — RESUELTO (2026-07-03)

Cierra el pendiente de [[project-cripto-nowpayments-shipped-2026-07-02]] y
[[project-cripto-landing-jwt-2026-07-03]]. El pago cripto YA activa el VIP solo. Comprobado con
el pago real de tatan (order_id 22, 'finished').

## Causa raíz (por qué el VIP no se activaba)
El pago llegaba a NOWPayments (custody) pero SharpIQ nunca lo procesaba. NO era el webhook/IPN:
el problema es que el endpoint **GET /v1/payment/ (listar pagos) EXIGE un JWT** (Authorization:
Bearer), la **API key sola da 401** ("Bearer JWTtoken is required"). El JWT se saca con
**POST /v1/auth {email, password}** de la cuenta NOWPayments. (El 2FA del dashboard NO bloquea /v1/auth.)

## La solución (enfoque RECONCILIACIÓN por API, sin webhook)
En sharpiq-engine/api/pagos.py:
- `_np_token()`: login POST /v1/auth (email+password) -> JWT, cacheado ~4 min en `_NP_JWT`.
- `_np_listar_pagos()`: GET /v1/payment/ con `Authorization: Bearer <jwt>` + x-api-key.
- `_reconciliar_cripto(user_id)`: recorre los pagos, matchea `order_id == user_id` y
  `payment_status == 'finished'`, y llama `_registrar_pago_cripto` (idempotente) -> activa VIP.
- Endpoints: `POST /pagos/cripto/verificar` (auth, el propio usuario) y
  `POST /pagos/admin/reconciliar-cripto` (solo_admin, por email — herramienta de soporte).
- NUEVAS env vars en Railway (web): **NOWPAYMENTS_EMAIL** = yamidnunezh@gmail.com,
  **NOWPAYMENTS_PASSWORD** = clave del dashboard NOWPayments.

## Dónde se dispara (por eso es AUTOMÁTICO)
- **bienvenido.html** (success_url del pago): en el polling llama POST /pagos/cripto/verificar
  cada 3s -> activa el VIP solo cuando NOWPayments confirma. Sirve para cripto Y MercadoPago.
- **cuenta.html**: botón "¿Ya pagaste con cripto? Verificar mi pago ✓" (respaldo manual).
- **admin.html** (Config): tarjeta "🪙 Reconciliar pago cripto de un cliente" por email (soporte).

## También arreglado hoy (bugs relacionados)
- `_registrar_pago_cripto`: activa VIP al llegar a 'finished' aunque un IPN previo no-finished ya
  hubiera creado la fila (antes el ON CONFLICT lo saltaba). Idempotente con `ya_finished`.
- Mako `_estado`: lee el plan REAL de la base (no del token viejo) -> VIP se reconoce sin re-login.
  EXCEPCIÓN: el admin (bypass hardcoded) NUNCA se degrada y tiene acceso ILIMITADO (999).
- tatan (tatanhuege@gmail.com, id 22) quedó VIP (activado manual + reconciliado). VIP no exige
  correo verificado, así que ya usa Mako.

## Limpieza hecha
Se borró el endpoint temporal `GET /pagos/cripto/diag` y el recuadro DEBUG del panel admin.
SW en v103. Todo compila y desplegado en main.

## Pendiente menor
- El webhook `/pagos/cripto/webhook` (IPN) sigue existiendo pero NO es el camino principal (la
  reconciliación por API lo reemplaza). Si algún día se quiere, hay que sincronizar el IPN secret.
- Retirar los ~15 USDT de custody de NOWPayments a la MetaMask cuando Yamid quiera (Custody->Withdraw).
- Rotar la contraseña de NOWPayments algún día NO conviene sin actualizar NOWPAYMENTS_PASSWORD en Railway.
