---
name: project-cripto-nowpayments-shipped-2026-07-02
description: 2026-07-02 Pagos cripto con NOWPayments CONSTRUIDOS y desplegados (checkout + webhook + botón web + tablas del motor de Partners). Falta probar el flujo y construir la LÓGICA de Partners.
metadata:
  type: project
---

# Pagos cripto NOWPayments — construido y en vivo (2026-07-02)

Sigue de [[project-cripto-pasarela-2026-07-01]] (plan/research). HOY se implementó todo el
COBRO cripto de punta a punta, en PARALELO a MercadoPago (sin tocarlo).

## Cuenta NOWPayments (montada por Yamid con guía)
- Registro con correo login = yamidnunezh@gmail.com; **corporate email = info@sharpiq.co**
  (correo de empresa, vive en **Zoho** → mail.zoho.com).
- Business type: **SaaS and Web Services** (NO Gambling, a propósito).
- **Verified** (KYC con cédula colombiana — Yamid vive/declara en Colombia).
- **2FA activado** (Google Authenticator). OJO SEGURIDAD: durante el setup se vieron en capturas
  el backup code y la 2FA key -> conviene REGENERAR el 2FA en privado cuando esté en calma.
- **Custody enabled** + promo: 0 fee de red USDT TRC-20 por 60 días.

## Decisiones (LOCKED)
- **Wallet: MetaMask** (la que Yamid domina) + **auto-conversión** de NOWPayments = listo para LatAm
  (el cliente paga en Tron/lo que tenga, se convierte y llega a la wallet EVM). Simple + control.
- **Redes: BSC (BEP-20) + Polygon** (fees de centavos). BSC=BEP-20 (misma cosa).
- **Dirección de recepción (pública, EVM, misma para BSC/Polygon):**
  `0x6642aEE035F36cB90565C6D3118C7658C1AEb023` — whitelisteada en NOWPayments (status "Requested",
  se auto-aprueba en ~24-48h). La wallet TAMBIÉN tiene Tron nativo (TFMy94j...) para sumar después.
- **Non-custodial + payouts con aprobación por lote** = control absoluto (la seed NUNCA se comparte).
- NOWPayments tiene **Payment Markup nativo (hasta 10%)** para monetizar el fee de transacción.

## Backend (Railway, desplegado) — sharpiq-engine/api/pagos.py
- `POST /pagos/cripto/checkout` (auth): crea **invoice** NOWPayments (order_id=user_id), devuelve
  `invoice_url`. Cobra `PRECIO_VIP_USD` (env, default **15**; ~60.000 COP; ajustable en Railway).
- `POST /pagos/cripto/webhook`: verifica **firma HMAC-SHA512** del IPN (fail-closed), **re-confirma**
  el estado con la API (`GET /v1/payment/{id}`), y si `payment_status=='finished'` -> registra pago
  (idempotente: reusa `mp_payment_id` con prefijo **`nowp_`**) y llama al MISMO `_activar_vip()`.
- Config: `NOWPAYMENTS_API_KEY` + `NOWPAYMENTS_IPN_SECRET` **ya en Railway (web service)**.
  IPN URL en NOWPayments = `https://api.sharpiq.co/pagos/cripto/webhook`.
- Verificado en vivo: checkout->401 sin auth (existe), webhook->401 "Firma IPN inválida" sin firma
  (seguridad OK, el IPN secret funciona).

## Base de datos (db.py inicializar_db) — 3 tablas del motor de Partners
- `partners` (usuario_id UNIQUE, es_partner, pct_comision default 25, crypto_red, crypto_address,
  min_payout_usd default 20). `comisiones` (partner_id, cliente_id, **pago_id UNIQUE**, periodo,
  monto_usd, estado). `payouts` (partner_id, periodo, **UNIQUE(partner_id,periodo)**, txid, estado).
  Idempotencia dura porque los payouts cripto son irreversibles. Aditivo, no toca lo existente.

## Frontend — cuenta.html (SW v96)
- Botón **"🪙 Pagar con cripto (USDT / USDC)"** debajo del de MercadoPago -> `pagarCripto()` ->
  `/pagos/cripto/checkout` -> redirige al invoice de NOWPayments.

## PENDIENTE (lo próximo, en orden)
1. **PROBAR el flujo**: (a) dar al botón y ver que carga la página de NOWPayments (sin pagar);
   (b) prueba real con pago pequeño (la plata va a la wallet de Yamid, solo cuesta fee) -> ver que
   el VIP se activa solo. Se puede bajar `PRECIO_VIP_USD=1` en Railway para la prueba.
2. **LÓGICA del motor de Partners** (las tablas existen, la lógica NO): hook de devengo de comisión
   RECURRENTE en `_activar_vip`/`_registrar_pago` (por cada renovación, `ON CONFLICT(pago_id)`);
   router **api/partners.py** (dashboard + wallet); **job de payout** idempotente (fila-lote ANTES
   de llamar la API + aprobación manual sobre umbral). Ver la auditoría en [[AUDITORIA]] y
   [[project-modelo-financiero-2026-07-01]] (recalcular % con precio real 60.000 COP antes de fijar).
3. **Seguridad** (auditoría): rotar JWT_SECRET (puede ser adivinable — Yamid lo dijo), regenerar los
   secretos de NOWPayments que se vieron en fotos, y seguir con firma webhook MP / rate-limiting /
   bcrypt / pool Postgres. Ver [[project-mako-pulido-2026-07-01]] (JWT #1 ya blindado en código).

## Aparte hoy: Mako subió a "personalidad de IA de primer nivel"
`_SYSTEM` reescrito (cálido, con formato/negritas, se adapta) manteniendo el aterrizaje. Ver
[[project-mako-pulido-2026-07-01]].
