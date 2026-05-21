/**
 * SharpIQ — Cloudflare Worker
 * Recibe webhooks de Mercado Pago y activa acceso VIP en Telegram.
 *
 * Variables de entorno (configurar en Cloudflare Workers → Settings → Variables):
 *   MP_ACCESS_TOKEN   — Token de Mercado Pago (Production)
 *   TELEGRAM_TOKEN    — Token del bot @sharpiq_alertas_bot
 *   TELEGRAM_VIP_ID   — ID del canal VIP (-1003833982154)
 *   TELEGRAM_YAMID_ID — ID privado de Yamid (8802028554)
 *   KV_NAMESPACE      — Binding de KV (nombre: SHARPIQ_KV)
 */

const MP_BASE = "https://api.mercadopago.com";
const TG_BASE = "https://api.telegram.org";

export default {
  async fetch(request, env) {
    if (request.method !== "POST") {
      return new Response("SharpIQ Webhook OK", { status: 200 });
    }

    let body;
    try {
      body = await request.json();
    } catch {
      return new Response("Bad JSON", { status: 400 });
    }

    // Solo procesar eventos de suscripción aprobados
    const tipo = body.type || body.action || "";
    const dataId = body.data?.id || body.id;

    if (!dataId) return new Response("OK", { status: 200 });

    // Manejar suscripciones (preapproval) o pagos de suscripción (subscription_authorized_payment)
    if (tipo.includes("subscription") || tipo.includes("preapproval") || tipo.includes("payment")) {
      await procesarPago(env, tipo, dataId);
    }

    return new Response("OK", { status: 200 });
  }
};

async function procesarPago(env, tipo, dataId) {
  try {
    let chatId = null;
    let emailPagador = null;
    let estado = null;

    if (tipo.includes("payment")) {
      const data = await mpGet(env, `/v1/payments/${dataId}`);
      estado = data?.status;
      emailPagador = data?.payer?.email;
      // external_reference trae el chat_id de Telegram
      chatId = data?.external_reference || null;
    } else {
      // preapproval / subscription
      const data = await mpGet(env, `/preapproval/${dataId}`);
      estado = data?.status;
      emailPagador = data?.payer_email;
      chatId = data?.external_reference || null;
    }

    if (estado !== "authorized" && estado !== "approved" && estado !== "active") {
      return; // pago pendiente o rechazado — no hacer nada
    }

    // Prioridad 1: usar external_reference (chat_id directo, sin email)
    if (!chatId && emailPagador) {
      // Fallback: buscar por email en KV (usuarios registrados con flujo antiguo)
      chatId = await env.SHARPIQ_KV.get(`email:${emailPagador.toLowerCase()}`);
    }

    if (!chatId) {
      await notificarYamid(env,
        `💰 Pago aprobado\n` +
        `✉️ ${emailPagador || "sin email"} | ID: ${dataId}\n` +
        `⚠️ No se pudo identificar al usuario Telegram. Activa manualmente con /activar.`
      );
      return;
    }

    // Generar link de invitación único (1 solo uso)
    const inviteLink = await crearLinkVip(env);
    if (!inviteLink) {
      await notificarYamid(env, `❌ Error generando link VIP para chat_id ${chatId}`);
      return;
    }

    // Enviar acceso al usuario
    await tgSend(env, chatId,
      `🎉 <b>¡Pago confirmado! Acceso VIP activado.</b>\n\n` +
      `Únete al canal SharpIQ VIP con este link exclusivo:\n${inviteLink}\n\n` +
      `✅ Picks diarios · Alertas en vivo · Análisis IA\n\n` +
      `<i>SharpIQ — La ventaja inteligente</i>`
    );

    // Marcar activado en KV
    await env.SHARPIQ_KV.put(`vip:${chatId}`, `active:${Date.now()}`);

    await notificarYamid(env,
      `💰 <b>NUEVO VIP activado automáticamente</b>\n` +
      `chat_id: ${chatId}\n` +
      (emailPagador ? `✉️ ${emailPagador}` : "")
    );

  } catch (err) {
    await notificarYamid(env, `❌ Error en webhook: ${err.message}`);
  }
}

async function mpGet(env, path) {
  const r = await fetch(`${MP_BASE}${path}`, {
    headers: { Authorization: `Bearer ${env.MP_ACCESS_TOKEN}` }
  });
  return r.json();
}

async function tgSend(env, chatId, text) {
  return fetch(`${TG_BASE}/bot${env.TELEGRAM_TOKEN}/sendMessage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ chat_id: chatId, text, parse_mode: "HTML" })
  });
}

async function crearLinkVip(env) {
  const r = await fetch(`${TG_BASE}/bot${env.TELEGRAM_TOKEN}/createChatInviteLink`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      chat_id: env.TELEGRAM_VIP_ID,
      member_limit: 1,
      name: `VIP-${Date.now()}`
    })
  });
  const data = await r.json();
  return data?.result?.invite_link || null;
}

async function notificarYamid(env, mensaje) {
  return tgSend(env, env.TELEGRAM_YAMID_ID, mensaje);
}
