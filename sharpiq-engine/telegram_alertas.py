# -*- coding: utf-8 -*-
"""
SharpIQ — Alertas Telegram
Envia notificaciones cuando el motor detecta value bets
"""
import requests
import json
import os
import sys
sys.path.insert(0, os.path.dirname(__file__))
from config import TELEGRAM_TOKEN
try:
    from config import TELEGRAM_YAMID_ID
except ImportError:
    TELEGRAM_YAMID_ID = None
try:
    from config import TELEGRAM_FREE_ID
except ImportError:
    TELEGRAM_FREE_ID = None

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.py")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# GIFs enviados al canal FREE — puedes reemplazar las URLs por las que prefieras
GIFS_WIN = [
    "https://media.giphy.com/media/26u4lOMA8JKSnL9Uk/giphy.gif",
    "https://media.giphy.com/media/3o7TKMt1VVNkHV2PaE/giphy.gif",
    "https://media.giphy.com/media/l0HlRnAWXxn0MhKLK/giphy.gif",
]
GIFS_MANANA = [
    "https://media.giphy.com/media/077i6AULCXc0FKTj9s/giphy.gif",
    "https://media.giphy.com/media/l0HlMZrXA0mL9OHLU/giphy.gif",
    "https://media.giphy.com/media/WoD6JZnwap6s8/giphy.gif",
]


def get_chat_id():
    """Lee el chat_id guardado en config.py"""
    from config import TELEGRAM_CHAT_ID
    return TELEGRAM_CHAT_ID


def guardar_chat_id(chat_id):
    """Guarda el chat_id en config.py"""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        contenido = f.read()
    nuevo = contenido.replace(
        'TELEGRAM_CHAT_ID  = ""',
        f'TELEGRAM_CHAT_ID  = "{chat_id}"'
    ).replace(
        f'TELEGRAM_CHAT_ID  = "{chat_id}"',  # evitar doble reemplazo
        f'TELEGRAM_CHAT_ID  = "{chat_id}"'
    )
    # Reemplazo mas robusto
    import re
    nuevo = re.sub(r'TELEGRAM_CHAT_ID\s*=\s*"[^"]*"',
                   f'TELEGRAM_CHAT_ID  = "{chat_id}"', contenido)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        f.write(nuevo)
    print(f"  Chat ID guardado: {chat_id}")


def obtener_mi_chat_id():
    """Obtiene el chat_id del ultimo mensaje enviado al bot"""
    r = requests.get(f"{TELEGRAM_API}/getUpdates", timeout=10)
    data = r.json()
    updates = data.get("result", [])
    if not updates:
        return None
    ultimo = updates[-1]
    msg = ultimo.get("message") or ultimo.get("channel_post")
    if msg:
        return str(msg["chat"]["id"])
    return None


def enviar_mensaje(texto, chat_id=None):
    if not chat_id:
        chat_id = get_chat_id()
    if not chat_id:
        print("  Sin chat_id — ejecuta: py telegram_alertas.py setup")
        return False
    r = requests.post(f"{TELEGRAM_API}/sendMessage", json={
        "chat_id": chat_id,
        "text": texto,
        "parse_mode": "HTML"
    }, timeout=10)
    return r.status_code == 200


def _enviar_gif(chat_id, gif_url, caption=""):
    """Base: envia un GIF a cualquier chat_id. Falla silenciosamente."""
    if not chat_id:
        return False
    try:
        payload = {"chat_id": chat_id, "animation": gif_url}
        if caption:
            payload["caption"] = caption
            payload["parse_mode"] = "HTML"
        r = requests.post(f"{TELEGRAM_API}/sendAnimation", json=payload, timeout=15)
        return r.status_code == 200
    except Exception:
        return False


def enviar_gif_free(gif_url, caption=""):
    """Envia un GIF al canal free."""
    return _enviar_gif(TELEGRAM_FREE_ID, gif_url, caption)


def enviar_gif_vip(gif_url, caption=""):
    """Envia un GIF al canal VIP."""
    return _enviar_gif(get_chat_id(), gif_url, caption)


def enviar_alerta_value_bet(pred, mercado, vb):
    emoji = "🔥" if vb["clasificacion"] == "ALTO VALOR" else "💰"

    nombres_mercado = {
        "victoria_local":  "Victoria Local (1)",
        "empate":          "Empate (X)",
        "victoria_visita": "Victoria Visitante (2)",
        "over15":          "Over 1.5 Goles",
        "under15":         "Under 1.5 Goles",
        "over25":          "Over 2.5 Goles",
        "under25":         "Under 2.5 Goles",
        "over35":          "Over 3.5 Goles",
        "under35":         "Under 3.5 Goles",
        "btts_si":         "Ambos Marcan — Sí",
        "btts_no":         "Ambos Marcan — No",
        "doble_1x":        "Doble Oportunidad 1X",
        "doble_x2":        "Doble Oportunidad X2",
        "doble_12":        "Doble Oportunidad 12",
        "dnb_local":       "Draw No Bet — Local",
        "dnb_visita":      "Draw No Bet — Visitante",
    }
    cuota_key_map = {
        "victoria_local":  "1",
        "empate":          "X",
        "victoria_visita": "2",
        "over15":          "over15",
        "under15":         "under15",
        "over25":          "over25",
        "under25":         "under25",
        "over35":          "over35",
        "under35":         "under35",
        "btts_si":         "btts_si",
        "btts_no":         "btts_no",
        "doble_1x":        "doble_1x",
        "doble_x2":        "doble_x2",
        "doble_12":        "doble_12",
        "dnb_local":       "dnb_local",
        "dnb_visita":      "dnb_visita",
    }
    prob_key_map = {
        "victoria_local":  "victoria_local",
        "empate":          "empate",
        "victoria_visita": "victoria_visita",
        "over25":          "over25",
        "under25":         "under25",
        "btts_si":         "btts_si",
        "btts_no":         "btts_no",
    }

    ck    = cuota_key_map.get(mercado, "1")
    cuota = pred["cuotas"].get(ck, "?")
    casa  = pred["cuotas"].get(ck + "_casa", "")
    prob  = pred["probabilidades"].get(prob_key_map.get(mercado, "victoria_local"), 0)

    h, m2 = pred.get("hora", "00:00").split(":")
    hora_cot = f"{str((int(h)-5+24)%24).zfill(2)}:{m2} COT"

    casa_linea = f"\n🏠 <b>Casa recomendada:</b> {casa}" if casa else ""

    texto = f"""{emoji} <b>SharpIQ — {vb['clasificacion']}</b>

⚽ <b>{pred['local']} vs {pred['visitante']}</b>
🏆 {pred.get('liga', '')} | {hora_cot}

📊 <b>Mercado:</b> {nombres_mercado.get(mercado, mercado)}
📈 <b>Probabilidad modelo:</b> {prob}%
💵 <b>Cuota:</b> {cuota}{casa_linea}
✅ <b>Valor esperado:</b> +{vb['ev_porcentaje']}%

<i>SharpIQ Engine — La ventaja inteligente</i>"""

    return enviar_mensaje(texto)


def enviar_resumen_dia(reporte):
    total = reporte["total_partidos"]
    preds = reporte["predicciones"]
    value_bets = sum(1 for p in preds for v in p["value_bets"].values() if v["tiene_valor"])
    alto_valor = sum(1 for p in preds for v in p["value_bets"].values() if v["clasificacion"] == "ALTO VALOR")

    texto = f"""📋 <b>SharpIQ — Resumen del dia</b>
📅 {reporte['fecha']}

⚽ Partidos analizados: {total}
💰 Value Bets detectados: {value_bets}
🔥 Alto Valor: {alto_valor}

"""
    nombres = {
        "victoria_local":"Local (1)","empate":"Empate (X)","victoria_visita":"Visitante (2)",
        "over25":"Over 2.5","under25":"Under 2.5","btts_si":"BTTS Sí","btts_no":"BTTS No",
    }
    cuota_map = {
        "victoria_local":"1","empate":"X","victoria_visita":"2",
        "over25":"over25","under25":"under25","btts_si":"btts_si","btts_no":"btts_no",
    }
    for pred in preds:
        tiene_vb = any(v["tiene_valor"] for v in pred["value_bets"].values() if v)
        if tiene_vb:
            texto += f"• {pred['local']} vs {pred['visitante']}\n"
            for m, vb in pred["value_bets"].items():
                if vb and vb["tiene_valor"]:
                    ck   = cuota_map.get(m, "1")
                    cuota = pred["cuotas"].get(ck, "")
                    casa  = pred["cuotas"].get(ck + "_casa", "")
                    casa_str = f" [{casa}]" if casa else ""
                    texto += f"  → {nombres.get(m,m)} @ {cuota}{casa_str}: EV +{vb['ev_porcentaje']}%\n"

    texto += "\n<i>sharpiq.co — La ventaja inteligente</i>"
    enviar_mensaje(texto, chat_id=TELEGRAM_YAMID_ID)

    # Enviar predicciones completas al canal VIP
    cuota_map_vip = {
        "victoria_local":"1","empate":"X","victoria_visita":"2",
        "over25":"over25","under25":"under25","btts_si":"btts_si","btts_no":"btts_no",
        "over15":"over15","over35":"over35",
    }
    nombres_vip = {
        "victoria_local":"Local (1)","empate":"Empate (X)","victoria_visita":"Visitante (2)",
        "over25":"Over 2.5","under25":"Under 2.5","btts_si":"BTTS Si","btts_no":"BTTS No",
        "over15":"Over 1.5","over35":"Over 3.5",
    }
    vip_texto = f"📊 <b>SharpIQ — Predicciones del dia</b>\n📅 {reporte['fecha']}\n\n"
    for pred in preds:
        hora_utc = pred.get("hora", "00:00")
        h, m2 = hora_utc.split(":")
        hora_cot = f"{str((int(h)-5+24)%24).zfill(2)}:{m2} COT"
        probs = pred["probabilidades"]
        pred_p = pred["prediccion_principal"]

        mejor_vb = None
        mejor_ev = -999
        for mk, vb in pred["value_bets"].items():
            if vb and vb.get("ev_porcentaje", -999) > mejor_ev:
                mejor_ev = vb["ev_porcentaje"]
                mejor_vb = (mk, vb)

        vip_texto += f"⚽ <b>{pred['local']} vs {pred['visitante']}</b>\n"
        vip_texto += f"🏆 {pred.get('liga','')} | {hora_cot}\n"
        vip_texto += f"📈 1:{probs['victoria_local']}% X:{probs['empate']}% 2:{probs['victoria_visita']}%\n"
        vip_texto += f"🎯 <b>{pred_p['mercado']}</b> ({pred_p['prob']}%)\n"
        if mejor_vb:
            mk, vb = mejor_vb
            ck = cuota_map_vip.get(mk, "1")
            cuota = pred["cuotas"].get(ck, "")
            ev = vb["ev_porcentaje"]
            emoji = "🔥" if vb["clasificacion"] == "ALTO VALOR" else ("💰" if ev > 0 else "📊")
            vip_texto += f"{emoji} {nombres_vip.get(mk, mk)} @ {cuota} | EV: {('+' if ev>=0 else '')}{ev}%\n"
        vip_texto += "\n"

    vip_texto += "<i>SharpIQ — La ventaja inteligente · sharpiq.co</i>"
    from config import TELEGRAM_CHAT_ID
    return enviar_mensaje(vip_texto, chat_id=TELEGRAM_CHAT_ID)


def enviar_aviso_yamid(texto):
    """Mensaje privado a Yamid — alertas del motor, auto-publicaciones, errores."""
    return enviar_mensaje(texto, chat_id=TELEGRAM_YAMID_ID)


def enviar_canal_free(partido, liga, hora):
    """Publica un teaser en el canal público — mercado oculto para generar curiosidad."""
    texto = (
        f"⚽ <b>{partido}</b>\n"
        f"🏆 {liga} | {hora}\n\n"
        f"📊 <b>Predicción:</b> 🔒 Solo VIP\n"
        f"💵 <b>Cuota:</b> 🔒 Solo VIP\n\n"
        f"🔥 <b>¿Quieres la predicción completa?</b>\n"
        f"Únete al canal VIP → https://t.me/sharpiq_alertas_bot\n\n"
        f"<i>SharpIQ — La ventaja inteligente · sharpiq.co</i>"
    )
    return enviar_mensaje(texto, chat_id=TELEGRAM_FREE_ID)


def enviar_autopublicacion(partido, liga, mercado, cuota, hora, ev):
    """Avisa a Yamid cuando el motor auto-publicó una predicción."""
    texto = (
        f"🤖 <b>SharpIQ — Auto-publicado</b>\n\n"
        f"⚽ <b>{partido}</b>\n"
        f"🏆 {liga} | {hora}\n"
        f"📊 <b>Mercado:</b> {mercado}\n"
        f"💵 <b>Cuota:</b> {cuota}\n"
        f"⚡ <b>EV:</b> +{ev}%\n\n"
        f"✅ Publicado en sharpiq.co y enviado al canal VIP\n"
        f"<i>Revisa cuando puedas — puedes corregir desde el panel</i>"
    )
    return enviar_aviso_yamid(texto)


def notificar_referido(codigo_ref, telegram_usuario="desconocido"):
    """Avisa a Yamid cuando alguien registra un referido vía /referido CODIGO."""
    texto = (
        f"🎁 <b>SharpIQ — Nuevo Referido</b>\n\n"
        f"👤 <b>Nuevo suscriptor:</b> @{telegram_usuario}\n"
        f"🔗 <b>Código referidor:</b> <code>{codigo_ref}</code>\n\n"
        f"✅ Acción: dar <b>7 días extra</b> al suscriptor con código {codigo_ref}\n"
        f"<i>Verifica el pago en MercadoPago antes de aplicar el beneficio</i>"
    )
    return enviar_aviso_yamid(texto)


def procesar_updates_bot():
    """
    Procesa mensajes nuevos al bot. Maneja /referido CODIGO.
    Llama desde un cron o manualmente para procesar la cola.
    """
    r = requests.get(f"{TELEGRAM_API}/getUpdates", timeout=10)
    if r.status_code != 200:
        return
    updates = r.json().get("result", [])
    ultimo_id = None

    for upd in updates:
        ultimo_id = upd["update_id"]
        msg = upd.get("message", {})
        texto = msg.get("text", "")
        usuario = msg.get("from", {}).get("username", "desconocido")
        chat_id_usuario = str(msg.get("chat", {}).get("id", ""))

        if texto.startswith("/referido"):
            partes = texto.split()
            if len(partes) >= 2:
                codigo = partes[1].strip().upper()
                notificar_referido(codigo, usuario)
                # Confirmar al usuario que registró
                enviar_mensaje(
                    f"✅ Referido registrado correctamente.\n"
                    f"Código: <code>{codigo}</code>\n\n"
                    f"Tu amigo recibirá 7 días extra en su suscripción. "
                    f"¡Gracias por hacer crecer la comunidad SharpIQ! 🔥",
                    chat_id=chat_id_usuario
                )
            else:
                enviar_mensaje(
                    "Uso: <code>/referido CODIGO</code>\nEjemplo: /referido ABC123",
                    chat_id=chat_id_usuario
                )

    # Marcar updates como leídos
    if ultimo_id is not None:
        requests.get(f"{TELEGRAM_API}/getUpdates",
                     params={"offset": ultimo_id + 1}, timeout=10)


def enviar_saludo_manana_free(partidos_hoy):
    """
    Saludo matutino al canal free — estilo dinámico CampeonesColombia.
    partidos_hoy: lista de dicts con claves 'local', 'visitante', 'liga', 'hora'
    """
    from datetime import date
    import random

    # GIF de análisis antes del texto
    enviar_gif_free(random.choice(GIFS_MANANA))

    dias = {0:"Lunes",1:"Martes",2:"Miércoles",3:"Jueves",4:"Viernes",5:"Sábado",6:"Domingo"}
    meses = {1:"enero",2:"febrero",3:"marzo",4:"abril",5:"mayo",6:"junio",
             7:"julio",8:"agosto",9:"septiembre",10:"octubre",11:"noviembre",12:"diciembre"}
    hoy = date.today()
    dia_nombre = dias[hoy.weekday()]
    mes_nombre = meses[hoy.month]

    saludos = [
        "¡Buenos días comunidad! ☀️",
        "¡Arriba la comunidad SharpIQ! 🔥",
        "¡Feliz día a todos! Aquí empieza la jornada ⚡",
        "¡Buenos días! El fútbol no para y nosotros tampoco 💪",
    ]
    saludo = random.choice(saludos)

    texto = (
        f"{saludo}\n\n"
        f"📅 <b>{dia_nombre} {hoy.day} de {mes_nombre}</b>\n\n"
        f"⚽ <b>Partidos de hoy:</b>\n"
    )

    if partidos_hoy:
        for p in partidos_hoy[:6]:  # máximo 6 partidos
            texto += f"• {p['local']} vs {p['visitante']} — {p.get('hora','')}\n"
            if p.get('liga'):
                texto += f"  🏆 {p['liga']}\n"
    else:
        texto += "• Jornada tranquila hoy — analizando opciones\n"

    texto += (
        f"\n🔒 <b>Las predicciones VIP ya están listas</b>\n"
        f"¿Quieres las cuotas y mercados exactos?\n"
        f"👉 Únete al canal VIP → https://t.me/sharpiq_alertas_bot\n\n"
        f"<i>SharpIQ — La ventaja inteligente · sharpiq.co</i>"
    )
    return enviar_mensaje(texto, chat_id=TELEGRAM_FREE_ID)


def enviar_resultado_free(partido, resultado_texto, emoji_resultado):
    """
    Publica el resultado de una predicción en el canal free.
    resultado_texto: 'WIN ✅' o 'LOSS ❌'
    emoji_resultado: '✅' o '❌'
    """
    import random
    wins = [
        "¡La IA no falla! 🤖🔥",
        "¡Eso es análisis de datos! 📊💪",
        "¡SharpIQ suma otro acierto! ⚡",
    ]
    losses = [
        "El fútbol siempre sorprende. Seguimos analizando 📊",
        "No todas entran, pero el EV positivo es clave a largo plazo 💡",
        "Pérdida asumida — el modelo aprende 🤖",
    ]
    es_win = emoji_resultado == "✅"
    comentario = random.choice(wins if es_win else losses)

    # GIF celebratorio solo en WIN
    if es_win:
        enviar_gif_free(random.choice(GIFS_WIN))

    texto = (
        f"{emoji_resultado} <b>Resultado — {partido}</b>\n\n"
        f"<b>{resultado_texto}</b>\n\n"
        f"{comentario}\n\n"
        f"🔒 Ver predicciones de mañana → https://t.me/sharpiq_alertas_bot\n"
        f"<i>SharpIQ — La ventaja inteligente</i>"
    )
    return enviar_mensaje(texto, chat_id=TELEGRAM_FREE_ID)


def _construir_narrativa(pred, mercado, vb, canal):
    """
    Genera texto de análisis narrativo a partir de los datos de la predicción.
    canal: 'free' (incluye CTA a VIP) | 'vip' (más detallado, sin CTA)
    """
    local     = pred["local"]
    visitante = pred["visitante"]
    probs     = pred.get("probabilidades", {})
    cuotas    = pred.get("cuotas", {})
    forma_l   = pred.get("forma_local")  or {}
    forma_v   = pred.get("forma_visita") or {}
    h2h       = pred.get("h2h")          or {}

    ev        = vb.get("ev_porcentaje", 0)
    prob_raw  = 0.0
    cuota_api = 0.0
    cuota_justa_str = ""

    # Mapeo mercado → clave de probabilidad y cuota
    prob_map = {
        "victoria_local":  ("victoria_local",  "1"),
        "empate":          ("empate",           "X"),
        "victoria_visita": ("victoria_visita",  "2"),
        "over25":          ("over25",           "over25"),
        "under25":         ("under25",          "under25"),
        "over15":          ("over15",           "over15"),
        "under15":         ("under15",          "under15"),
        "over35":          ("over35",           "over35"),
        "btts_si":         ("btts_si",          "btts_si"),
        "btts_no":         ("btts_no",          "btts_no"),
    }
    mercado_nombres = {
        "victoria_local":  "Victoria Local",
        "empate":          "Empate",
        "victoria_visita": "Victoria Visitante",
        "over25":          "Over 2.5 Goles",
        "under25":         "Under 2.5 Goles",
        "over15":          "Over 1.5 Goles",
        "under15":         "Under 1.5 Goles",
        "over35":          "Over 3.5 Goles",
        "btts_si":         "Ambos Marcan — Sí",
        "btts_no":         "Ambos Marcan — No",
    }

    prob_key, cuota_key = prob_map.get(mercado, ("victoria_local", "1"))
    prob_raw  = probs.get(prob_key, 0)
    cuota_api = cuotas.get(cuota_key, 0)
    nombre_mercado = mercado_nombres.get(mercado, mercado)

    if prob_raw and prob_raw > 0:
        cuota_justa = round(100 / prob_raw, 2)
        cuota_justa_str = str(cuota_justa)

    goles_esp  = probs.get("total_goles_esperados", 0)
    goles_l    = probs.get("goles_esperados_local", 0)
    goles_v    = probs.get("goles_esperados_visita", 0)

    # ── Bloque de forma ──
    linea_forma = ""
    if forma_l.get("ataque_reciente") and forma_v.get("ataque_reciente"):
        atq_l = forma_l["ataque_reciente"]
        def_l = forma_l.get("defensa_reciente", 0)
        atq_v = forma_v["ataque_reciente"]
        def_v = forma_v.get("defensa_reciente", 0)
        linea_forma = (
            f"📋 <b>Forma reciente (últimos 5 partidos):</b>\n"
            f"• {local}: {atq_l} goles/p anotados, {def_l} recibidos\n"
            f"• {visitante}: {atq_v} goles/p anotados, {def_v} recibidos\n"
        )

    # ── Bloque H2H ──
    linea_h2h = ""
    if h2h.get("partidos"):
        n = h2h["partidos"]
        gpp = h2h.get("goles_por_partido", 0)
        vl  = round(h2h.get("victorias_local", 0)  * n)
        ve  = round(h2h.get("empates", 0)           * n)
        vv  = round(h2h.get("victorias_visita", 0)  * n)
        linea_h2h = (
            f"🔁 <b>Últimos {n} enfrentamientos:</b> "
            f"{vl}V {ve}E {vv}D — {gpp} goles/partido en promedio\n"
        )

    # ── Bloque de goles esperados ──
    linea_goles = (
        f"⚽ <b>Goles esperados:</b> {local} {goles_l} — {goles_v} {visitante} "
        f"(total ~{goles_esp})\n"
    ) if goles_esp else ""

    # ── Bloque EV — solo si EV es positivo ──
    tiene_valor = ev > 0 and cuota_api and cuota_justa_str and float(cuota_api) > float(cuota_justa_str)
    if tiene_valor:
        linea_ev = (
            f"📈 <b>El valor matemático:</b>\n"
            f"• Probabilidad del modelo: <b>{prob_raw}%</b> para {nombre_mercado}\n"
            f"• Cuota justa: <b>{cuota_justa_str}</b> — la casa ofrece <b>{cuota_api}</b>\n"
            f"• Ventaja a tu favor: <b>EV +{ev}%</b>\n"
        )
        pie_vip  = "<i>EV positivo confirmado — apuesta con criterio matemático.</i>"
        pie_free = (
            f"📊 Probabilidad SharpIQ: <b>{prob_raw}%</b> | Cuota justa: <b>{cuota_justa_str}</b>\n"
            f"La casa paga <b>{cuota_api}</b> — ventaja del <b>+{ev}%</b> a tu favor.\n\n"
            f"🔒 <b>¿Quieres la predicción completa?</b> 👉 https://t.me/sharpiq_alertas_bot\n\n"
            f"<i>SharpIQ — La ventaja inteligente · sharpiq.co</i>"
        )
        intro_free = "El modelo detecta que la casa <b>subestima</b> la probabilidad real de este resultado.\n\n"
    else:
        linea_ev = (
            f"📊 <b>Análisis del modelo:</b>\n"
            f"• Probabilidad estimada: <b>{prob_raw}%</b> para {nombre_mercado}\n"
            f"• Cuota disponible: <b>{cuota_api}</b>\n"
            f"⚠️ <i>Sin ventaja matemática detectada — partido para observar, no apostar.</i>\n"
        )
        pie_vip  = "<i>Este análisis es informativo. Hoy no hay apuesta con valor matemático confirmado.</i>"
        pie_free = (
            f"🔍 Partido interesante para seguir hoy.\n\n"
            f"🔒 Predicciones con valor confirmado → https://t.me/sharpiq_alertas_bot\n\n"
            f"<i>SharpIQ — La ventaja inteligente · sharpiq.co</i>"
        )
        intro_free = ""

    if canal == "vip":
        texto = (
            f"🔬 <b>Análisis completo — SharpIQ Engine</b>\n\n"
            f"{linea_goles}"
            f"{linea_forma}"
            f"{linea_h2h}\n"
            f"{linea_ev}\n"
            f"{pie_vip}"
        )
    else:  # free
        texto = (
            f"🔍 <b>{'¿Por qué esta predicción?' if tiene_valor else 'Partido del día'}</b>\n\n"
            f"{linea_goles}"
            f"{linea_h2h}\n"
            f"{intro_free}"
            f"{pie_free}"
        )

    return texto.strip()


def enviar_narrativa(pred, mercado, vb):
    """Envía el análisis narrativo al canal free y al canal VIP."""
    try:
        texto_free = _construir_narrativa(pred, mercado, vb, canal="free")
        texto_vip  = _construir_narrativa(pred, mercado, vb, canal="vip")
        enviar_mensaje(texto_free, chat_id=TELEGRAM_FREE_ID)
        enviar_mensaje(texto_vip,  chat_id=get_chat_id())
    except Exception as e:
        print(f"  Narrativa error: {e}")


def enviar_mercados_ext_vip(pred):
    """
    Envía al canal VIP el análisis de corners, tarjetas y handicap asiático.
    Se llama después del mensaje principal de la predicción.
    """
    ext = pred.get("mercados_ext", {})
    if not ext:
        return False

    local    = pred["local"]
    visitante = pred["visitante"]
    corners  = ext.get("corners",  {})
    tarjetas = ext.get("tarjetas", {})
    handicap = ext.get("handicap", {})

    # ── Corners ──────────────────────────────────────────────────
    c_esp = corners.get("corners_esperados", "?")
    lineas_c = [f"• Esperados: <b>{c_esp}</b> totales en el partido"]
    for k, label in [("10", "Over/Under 9.5"), ("11", "Over/Under 10.5"), ("12", "Over/Under 11.5")]:
        ov = corners.get(f"corners_over{k}")
        un = corners.get(f"corners_under{k}")
        if ov is not None:
            cj_ov = round(100 / ov, 2) if ov > 0 else "—"
            cj_un = round(100 / un, 2) if un and un > 0 else "—"
            lim = int(k) - 0.5
            lineas_c.append(
                f"• O/U {lim}: Over {ov}% (justa {cj_ov}) | Under {un}% (justa {cj_un})"
            )

    # ── Tarjetas ─────────────────────────────────────────────────
    t_esp = tarjetas.get("tarjetas_esperadas", "?")
    lineas_t = [f"• Esperadas: <b>{t_esp}</b> tarjetas en el partido"]
    for k, label in [("3", "2.5"), ("4", "3.5"), ("5", "4.5")]:
        ov = tarjetas.get(f"tarjetas_over{k}")
        un = tarjetas.get(f"tarjetas_under{k}")
        if ov is not None:
            cj_ov = round(100 / ov, 2) if ov > 0 else "—"
            cj_un = round(100 / un, 2) if un and un > 0 else "—"
            lim = int(k) - 0.5
            lineas_t.append(
                f"• O/U {lim}: Over {ov}% (justa {cj_ov}) | Under {un}% (justa {cj_un})"
            )

    # ── Handicap Asiático ─────────────────────────────────────────
    lineas_ah = []
    ah_map = [
        ("ah_local_menos05",  f"{local} -0.5"),
        ("ah_visita_mas05",   f"{visitante} +0.5"),
        ("ah_local_menos1",   f"{local} -1"),
        ("ah_visita_mas1",    f"{visitante} +1"),
        ("ah_local_menos15",  f"{local} -1.5"),
        ("ah_visita_mas15",   f"{visitante} +1.5"),
    ]
    for key, nombre in ah_map:
        prob = handicap.get(key)
        if prob is not None:
            cj = round(100 / prob, 2) if prob > 0 else "—"
            lineas_ah.append(f"• {nombre}: {prob}% → cuota justa <b>{cj}</b>")

    texto = (
        f"📊 <b>Análisis Extendido — SharpIQ</b>\n\n"
        f"⚽ <b>{local} vs {visitante}</b>\n\n"
        f"🚩 <b>CORNERS</b>\n"
        + "\n".join(lineas_c) + "\n\n"
        f"🟨 <b>TARJETAS</b>\n"
        + "\n".join(lineas_t) + "\n\n"
        f"🔢 <b>HANDICAP ASIÁTICO</b>\n"
        + "\n".join(lineas_ah) + "\n\n"
        f"💡 <i>Si encuentras una cuota mayor a la justa → tienes ventaja matemática</i>\n\n"
        f"<i>SharpIQ — La ventaja inteligente</i>"
    )
    return enviar_mensaje(texto, chat_id=get_chat_id())


def enviar_tiers_vip(seguro, principal, alto_valor):
    """
    Mensaje único al canal VIP con los 3 picks del día en formato de tiers.
    Formato: 🛡️ SEGURO / ⭐ PICK PRINCIPAL / 🔥 ALTO VALOR
    """
    from config import TELEGRAM_CHAT_ID

    def _hcot(pred):
        h, m = pred.get("hora", "00:00").split(":")
        return f"{str((int(h)-5+24)%24).zfill(2)}:{m} COT"

    def _bloque(tier, emoji, label):
        if not tier:
            return None
        p  = tier["pred"]
        es_prop = p.get("es_player_prop", False)

        if es_prop:
            # Player prop: mostrar jugador + partido de contexto
            jugador  = p.get("prop_jugador", p["local"])
            partido  = p.get("partido", p["visitante"])
            ev_extra = ""
            if label == "ALTO VALOR":
                ev = round(tier.get("ev_pinn", tier.get("ev", 0)) or 0)
                ev_extra = f" — EV +{ev}%"
            prob_label = "Prob modelo"
            return (
                f"{emoji} <b>{label}</b>\n"
                f"🏀 <b>{jugador}</b>\n"
                f"📌 {partido}\n"
                f"🏆 {p.get('liga','')} | {_hcot(p)}\n"
                f"{tier['mercado_nombre']} | @{tier['cuota']}{ev_extra}\n"
                f"<i>{prob_label}: {round(tier['prob'])}%</i>"
            )
        else:
            # Partido normal (fútbol u otro deporte de equipo)
            ev_extra = ""
            if label == "ALTO VALOR":
                ev = round(tier.get("ev_pinn", tier.get("ev", 0)) or 0)
                ev_extra = f" — EV +{ev}%"
            prob_label = "Prob DNB" if "dnb" in tier.get("mercado", "") else "Prob modelo"
            return (
                f"{emoji} <b>{label}</b>\n"
                f"⚽ <b>{p['local']} vs {p['visitante']}</b>\n"
                f"🏆 {p.get('liga','')} | {_hcot(p)}\n"
                f"{tier['mercado_nombre']} | @{tier['cuota']}{ev_extra}\n"
                f"<i>{prob_label}: {round(tier['prob'])}%</i>"
            )

    bloques = [b for b in [
        _bloque(seguro,      "🛡️", "SEGURO"),
        _bloque(principal,   "⭐", "PICK PRINCIPAL"),
        _bloque(alto_valor,  "🔥", "ALTO VALOR"),
    ] if b]

    if not bloques:
        return False

    sep = "\n" + "─" * 30 + "\n\n"
    texto = (
        f"📊 <b>SharpIQ — Picks del Día</b>\n"
        f"{'─' * 30}\n\n"
        + sep.join(bloques)
        + "\n\n<i>SharpIQ — La ventaja inteligente · sharpiq.co</i>"
    )
    return enviar_mensaje(texto, chat_id=TELEGRAM_CHAT_ID)


def enviar_resultado_vip(partido, resultado_texto, emoji_resultado):
    """
    Publica el resultado de una predicción en el canal VIP con GIF celebratorio en WIN.
    """
    import random
    es_win = emoji_resultado == "✅"

    if es_win:
        enviar_gif_vip(random.choice(GIFS_WIN))

    wins_vip = [
        "¡Predicción acertada! 🤖🔥 Así se trabaja con datos.",
        "¡EV positivo convertido en ganancia! 📊💪",
        "¡Otro acierto SharpIQ! ⚡ La ventaja inteligente.",
    ]
    losses_vip = [
        "Resultado adverso — el modelo sigue aprendiendo 📊",
        "No todas entran. El largo plazo nos da la razón 💡",
        "Pérdida registrada. Bankroll y disciplina son clave 🤖",
    ]
    comentario = random.choice(wins_vip if es_win else losses_vip)

    texto = (
        f"{emoji_resultado} <b>Resultado VIP — {partido}</b>\n\n"
        f"<b>{resultado_texto}</b>\n\n"
        f"{comentario}\n\n"
        f"<i>SharpIQ — La ventaja inteligente · sharpiq.co</i>"
    )
    return enviar_mensaje(texto, chat_id=get_chat_id())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        print("\nSetup SharpIQ Alertas Telegram")
        print("="*40)
        print("1. Abre Telegram")
        print("2. Busca @sharpiq_alertas_bot")
        print("3. Envia /start")
        input("4. Presiona Enter cuando hayas enviado /start...")

        chat_id = obtener_mi_chat_id()
        if chat_id:
            guardar_chat_id(chat_id)
            enviar_mensaje(f"SharpIQ Alertas activado!\nRecibiras notificaciones de value bets aqui.", chat_id)
            print(f"\nListo! Alertas configuradas para chat: {chat_id}")
        else:
            print("No se encontro mensaje. Asegurate de enviar /start al bot primero.")
    else:
        print("Uso: py telegram_alertas.py setup")
