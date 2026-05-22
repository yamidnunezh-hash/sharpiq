# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from telegram_alertas import procesar_updates_bot
    procesar_updates_bot()
except Exception as e:
    print(f"referidos error: {e}")
