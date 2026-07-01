---
name: project-pago-vip-register-first-2026-06-29
description: 2026-06-29 BUG CRITICO de cobro arreglado — el boton Unete VIP usaba checkout-publico anonimo (sin external_reference) => el cliente pagaba pero el VIP NUNCA se activaba. Fix register-first + endpoint admin activar-vip por email.
metadata:
  type: project
---

# Pago VIP roto y arreglado: register-first (2026-06-29)

## El bug (un cliente pago y no pudo entrar al VIP)
El boton "Unete VIP" (`irAPago` en index.html) llamaba a `POST /pagos/checkout-publico`,
que crea un checkout MercadoPago **ANONIMO** (sin `external_reference` ni payer). El cliente
pagaba, pero el webhook (`/pagos/webhook`, rama `type==payment`) hace
`user_ref = pago.get("external_reference"); if user_ref: _registrar_pago(...)` — como el pago
anonimo NO trae external_reference, **no activaba nada**. Luego lo mandaba a "crear cuenta",
pero registrarse tampoco vinculaba el pago => VIP jamas se activaba. Sintoma: "le pide correo
y contrasena, no la deja entrar".

El backend YA estaba bien para el flujo autenticado: `suscribir/{plan}` SI pone
`external_reference=user_id`, y `_registrar_pago` (pagos.py ~316) ya llama `_activar_vip`
cuando el pago aprueba. El unico roto era el FRONTEND (usaba el checkout anonimo).

## El fix (commits fa5a6a5, 11fb56b, ee5b66e) — SOLO frontend + 1 endpoint admin
1. **index.html `irAPago`**: sin sesion -> `registro.html?plan=vip&next=pago`; con sesion ->
   `POST /pagos/suscribir/vip` (Bearer) -> checkout AMARRADO -> webhook activa VIP solo. 401 -> login.
2. **registro.html**: al crear cuenta con plan vip, hace `POST /pagos/suscribir/vip` con el token
   nuevo y redirige al checkout (antes iba a cuenta.html?upgrade=1 sin pagar). Arreglados 2 bugs
   que rompian la pagina con `?plan=vip`: `getElementById('refBadge')` y `querySelector('.box')`
   no existian (es `.card`).
3. **bienvenido.html**: reintenta `GET /pagos/mi-suscripcion` hasta 8 veces (~24s) para confirmar
   la activacion (el webhook de MP puede tardar unos segundos).
4. **NUEVO endpoint** `POST /pagos/admin/activar-vip` (solo_admin, body {email, meses?}): activa VIP
   por email para pagos Nequi/transferencia o pagos web sin amarrar. Verificado vivo (HTTP 401 sin
   token => Railway SI auto-despliega el API). Boton en admin.html pestana Config ("Activar VIP de
   un cliente"): lee `sharpiq_token` (JWT admin de login.html); si 401/403 pide reloguear.

SW v76->v78. Flujo correcto ahora: entrar a sharpiq.co -> Unete VIP -> crear cuenta (gratis) ->
pagar (PSE recomendado) -> VIP automatico. Ver [[project-odds-api-renovada-2026-06-28]].

## Cliente VIP no veia los picks bien (commit 50afcc6)
La cuenta VIP (cuenta.html -> `GET /picks/hoy`) leia `predicciones.json` filtrando
`ev_pinn>=5` => mostraba 2 picks con nombres CRUDOS (ej `cards_under_3_5`), distintos a
los 6 bonitos de la web. Fix: `_leer_proximos()` en picks.py parsea `PROXIMOS_EVENTOS`
de datos.js (misma fuente que la web) y el VIP ve EXACTAMENTE esos picks publicados,
desbloqueados (local/visitante, prediccion, cuota, tier). Free = 2 del mismo set, bloqueados.
predicciones.json queda solo como respaldo si datos.js viene vacio. cuenta.html ahora pinta
cuota @x.xx + tier. Una sola fuente de verdad para los picks del dia.

## Panel de clientes (commit 50afcc6)
NUEVO `GET /members/admin/clientes` (solo_admin): total registrados, VIP activos, free, y
lista (email/nombre/plan/fecha_registro/vence). UI: admin.html pestana "👥 Clientes" (resumen
+ tabla). Lee `sharpiq_token` (JWT admin). Aqui ve Yamid quien se registra y quien es VIP.

## Telegram VIP automatico (commit 9374984) — gap CERRADO
Antes el pago web activaba el VIP en la web pero NO metia al cliente al canal de Telegram.
Ahora: `GET /members/telegram-vip` (solo_vip) usa el bot para `createChatInviteLink`
(member_limit=1) en el canal VIP `-1003833982154` y devuelve un enlace UNICO de 1 uso.
- cuenta.html: boton "📲 Entrar al canal VIP de Telegram" (solo VIP/admin, revela en cargarPicks).
- bienvenido.html: tras confirmar el pago genera y muestra el boton automaticamente.
- members.py `_tg_config()`: TELEGRAM_TOKEN de env (o config local); canal de TELEGRAM_CHAT_ID env
  o default `-1003833982154`. VERIFICADO local: el bot ES admin y crea el invite OK.
- Railway RESUELTO (2026-06-29): Yamid agrego `TELEGRAM_TOKEN` y `TELEGRAM_CHAT_ID=-1003833982154`
  en el env del servicio **web** (api.sharpiq.co) del proyecto Railway **delightful-adaptation**
  (3 servicios: Postgres + web=API + worker redundante). Verificado: `GET /members/telegram-status`
  -> {configured:true, bot_ok:true}. El boton de Telegram ya funciona end-to-end. Diagnostico
  `/members/telegram-status` (sin secretos) queda para debug futuro. SW v79->v82.

## OJO pendiente / gap conocido
- **Cliente que ya pago por el flujo viejo (Alexandra)**: debe crear cuenta gratis en sharpiq.co y
  Yamid la activa con el boton "Activar VIP" (admin > Config). Su pago viejo fue anonimo, no se
  auto-activa. Operacion pendiente 166310427622; rechazada 165287448955 (banco del comprador).
