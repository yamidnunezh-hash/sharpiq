# -*- coding: utf-8 -*-
"""
SharpIQ — Envío manual de picks (Coritiba + Botafogo SP)
FREE: pick Coritiba visible + Botafogo tapado + CTA VIP
VIP:  ambos picks completos con EV y análisis
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_alertas import (
    enviar_mensaje, _enviar_gif,
    TELEGRAM_FREE_ID, get_chat_id
)

# ── GIFs ────────────────────────────────────────────────────────────────────
GIF_FUEGO   = "https://media.giphy.com/media/077i6AULCXc0FKTj9s/giphy.gif"
GIF_PREMIUM = "https://media.giphy.com/media/l0HlMZrXA0mL9OHLU/giphy.gif"
GIF_DINERO  = "https://media.giphy.com/media/3o7TKMt1VVNkHV2PaE/giphy.gif"

VIP_CHAT_ID = get_chat_id()


def enviar_free():
    # ── GIF atractivo ────────────────────────────────────────────────────────
    _enviar_gif(TELEGRAM_FREE_ID, GIF_FUEGO)

    texto = (
        "🔥 <b>SharpIQ — PICKS DEL DÍA</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "⚽ <b>PICK FREE — VISIBLE</b>\n\n"
        "🇧🇷 <b>Coritiba vs Bahia</b>\n"
        "🏆 Brasil · Serie A Betano\n"
        "🕕 18:00 COT · Couto Pereira\n\n"
        "📊 <b>Pick:</b> Gana Coritiba\n"
        "💵 <b>Cuota:</b> ~2.74\n"
        "📈 <b>Análisis:</b> Bahia lleva <b>0 victorias en sus últimos 5 partidos</b> "
        "y juega de visitante. El modelo le da a Coritiba un 42% real de ganar "
        "vs el 36% que descuenta el mercado. Esa brecha = ventaja.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "🔒 <b>PICK VIP — BLOQUEADO</b>\n\n"
        "🇧🇷 Partido del Brasileirão Serie B\n"
        "🕕 17:00 COT — hoy\n\n"
        "📊 El motor detectó <b>EV +14%</b> en este partido.\n"
        "💡 Es el tipo de pick de alto valor que solo publicamos en el canal VIP.\n\n"
        "⬇️ ⬇️ ⬇️\n"
        "🚀 <b>¿Quieres ver este pick completo?</b>\n"
        "Con cuota exacta, probabilidades del modelo y análisis completo.\n\n"
        "👉 <b>Únete al canal VIP por solo $15 USD/mes:</b>\n"
        "🔗 https://sharpiq.co\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "<i>SharpIQ — La ventaja inteligente · sharpiq.co</i>"
    )
    ok = enviar_mensaje(texto, chat_id=TELEGRAM_FREE_ID)
    print(f"  FREE enviado: {ok}")
    return ok


def enviar_vip():
    # ── GIF premium ──────────────────────────────────────────────────────────
    _enviar_gif(VIP_CHAT_ID, GIF_PREMIUM)

    texto = (
        "📊 <b>SharpIQ — PICKS DEL DÍA · VIP</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "⭐ <b>PICK PRINCIPAL</b>\n\n"
        "🇧🇷 <b>Coritiba vs Bahia</b>\n"
        "🏆 Brasil · Serie A Betano\n"
        "🕕 18:00 COT · Couto Pereira\n\n"
        "📊 <b>Pick:</b> Gana Coritiba\n"
        "💵 <b>Cuota:</b> 2.74\n"
        "✅ <b>EV:</b> +15%\n\n"
        "🔍 <b>Análisis:</b>\n"
        "• Coritiba: 42% prob real (modelo) vs 36.5% mercado\n"
        "• Bahia: 0 victorias en los últimos 5 partidos\n"
        "• Bahia juega de visitante, llega de E 1-1, D 2-1, D 2-1\n"
        "• Coritiba local en forma: ganó 3-0 vs Santos última fecha\n"
        "• Ineficiencia del mercado: la casa sobrestima a Bahia por nombre\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"

        "🔥 <b>ALTO VALOR</b>\n\n"
        "🇧🇷 <b>Botafogo SP vs Athletic Club</b>\n"
        "🏆 Brasil · Brasileirão Serie B\n"
        "🕕 17:00 COT · Est. Santa Cruz, Ribeirão Preto\n\n"
        "📊 <b>Pick:</b> Victoria Visitante (Athletic Club)\n"
        "💵 <b>Cuota:</b> 3.80\n"
        "✅ <b>EV:</b> +14%\n\n"
        "🔍 <b>Análisis:</b>\n"
        "• Botafogo SP: 17° en tabla, <b>7 partidos sin ganar</b>\n"
        "• Athletic Club: 14°, viene de empate 1-1, más estable\n"
        "• El mercado da 50% a Botafogo como local — inflado para un equipo sin ganar en 7\n"
        "• Athletic a 3.80 tiene valor matemático claro (+14% EV)\n"
        "⚠️ <i>Pick de alto valor = cuota alta + mayor varianza. Stake recomendado: 1-2% del bankroll</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📌 <b>Resumen picks de hoy:</b>\n"
        "1️⃣ Gana Coritiba @2.74 — EV +15%\n"
        "2️⃣ Victoria Visitante Athletic Club @3.80 — EV +14%\n\n"
        "<i>SharpIQ — La ventaja inteligente · sharpiq.co</i>"
    )
    ok = enviar_mensaje(texto, chat_id=VIP_CHAT_ID)
    print(f"  VIP enviado: {ok}")
    return ok


if __name__ == "__main__":
    print("\n SharpIQ — Envío manual de picks\n")
    enviar_free()
    enviar_vip()
    print("\n Listo — revisa ambos canales en Telegram")
