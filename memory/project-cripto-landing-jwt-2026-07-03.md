---
name: project-cripto-landing-jwt-2026-07-03
description: 2026-07-03 Cripto en la portada (botón + notita de red), JWT_SECRET rotado/blindado, y fix de Mako (no sumar props de jugador como total). PENDIENTE para mañana: prueba real del pago cripto a $15.
metadata:
  type: project
---

# Cripto en portada + JWT blindado + fix Mako (2026-07-03)

Sigue de [[project-cripto-nowpayments-shipped-2026-07-02]] y [[project-verificacion-correo-brevo-2026-07-03]].

## Desplegado hoy (SW v99)
- **Cripto en la PORTADA (index.html)**: botón "🪙 O paga con cripto (USDT/USDC)" en el hero →
  `irAPagoCripto()`: sin sesión manda a `registro.html?plan=vip&next=cripto` (register-first),
  con sesión hace POST `/pagos/cripto/checkout` y redirige a `d.url`. registro.html ahora lee
  `next=cripto` y tras crear cuenta llama al checkout cripto en vez de MercadoPago.
- **Notita de red** bajo el botón (portada y cuenta.html): "Recomendado USDT en Tron (TRC-20)
  o BSC — las más baratas. Evita Ethereum (comisiones altas)". Porque el selector de NOWPayments
  muestra muchas redes y confunde al cliente. NOWPayments AUTO-CONVIERTE, así que la red que elija
  el cliente no afecta lo que recibe Yamid.
- **JWT_SECRET ROTADO** (Yamid dijo que el viejo era adivinable): generó 48 bytes aleatorios en
  PowerShell (`New-Object byte[] 48; (New-Object System.Security.Cryptography.RNGCryptoServiceProvider).GetBytes($b); [Convert]::ToBase64String($b)`)
  y lo pegó en Railway → Variables (servicio **web**). VERIFICADO end-to-end: register da token,
  endpoint protegido con token=200, sin token=401. (El one-liner con RandomNumberGenerator.GetBytes
  NO sirve en PowerShell 5.1; usar RNGCryptoServiceProvider.)
- **Mako fix (mako.py)**: regla nueva en `_SYSTEM` — los props POR JUGADOR (faltas/remates/tarjetas/
  asistencias/quites) NO se suman para dar el TOTAL del partido. Un partido tiene ~20-26 faltas
  totales; la casa pone la línea en ~24-28. Antes Mako sumó 6 jugadores y dijo "~8.8 confirmadas"
  cuando la línea real era 28.5. Catch de Yamid usando la app como cliente.

## Prueba del pago cripto — Fase A OK, Fase B PENDIENTE
- **Fase A (verificada hoy)**: el botón abre la página real de NOWPayments (nowpayments.io/payment?iid=...)
  con el monto correcto (~$15) y selector de moneda/red. La integración crea la factura bien.
- **Fase B (MAÑANA, con $15 reales)**: pagar de verdad y confirmar que el webhook activa el VIP solo.
  Yamid NO quiso bajar `PRECIO_VIP_USD` a 1 — prueba directo con 15. Su MetaMask es EVM → pagar con
  USDT-BSC o USDT-Polygon (fees de centavos). Monitorear: webhook recibido → pago registrado
  (idempotente nowp_) → `_activar_vip`. Para verificar, usar una cuenta con clave conocida
  (ej. testcripto1@gmail.com / Prueba1234) y chequear su plan por API antes/después.
- **TODO de Yamid en NOWPayments**: dejar activadas SOLO las monedas buenas (USDT-TRC20, USDT-BSC,
  USDC-BSC) para quitar Ethereum/Solana del selector.

## Contexto emocional
Hoy Yamid ganó 2 triples reales armadas CON MAKO (una $106.200). Está muy motivado. También
DECIDIÓ NO hacer el multinivel de 6 niveles por riesgo legal en Colombia (Ley 1700/2013, pirámide
= delito). Se queda el motor de Partners de UN nivel (comisión sobre pagos reales) que ya existe.
Ver [[project-cripto-nowpayments-shipped-2026-07-02]].