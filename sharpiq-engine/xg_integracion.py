# -*- coding: utf-8 -*-
"""
SharpIQ — xG Integration
Ajusta los lambdas de Poisson usando datos reales de disparos a puerta.
xG proxy = shots_on_target × 0.35 (ratio histórico internacional)
Blending: 60% modelo base + 40% xG proxy
"""

XG_CONV_RATE = 0.35   # ~35% de disparos a puerta terminan en gol
XG_BLEND     = 0.40   # peso del xG en el blend final


def ajustar_con_xg(local, visitante, liga_id, lambda_local, lambda_visita):
    """
    Recalcula lambdas integrando xG (shots on target × conversion_rate).
    Reutiliza el caché de stats_mercados — 0 llamadas extra a la API.
    Devuelve (lambda_local_ajustado, lambda_visita_ajustado).
    """
    try:
        from stats_mercados import obtener_stats_ext, _defaults

        sl = obtener_stats_ext(local,     liga_id) or _defaults(liga_id)
        sv = obtener_stats_ext(visitante, liga_id) or _defaults(liga_id)

        # disparos_contra = shots on target propios del equipo (campo de stats_mercados)
        sot_l = sl.get("disparos_contra", 0)
        sot_v = sv.get("disparos_contra", 0)

        if sot_l <= 0 or sot_v <= 0:
            return lambda_local, lambda_visita

        xg_local  = sot_l * XG_CONV_RATE
        xg_visita = sot_v * XG_CONV_RATE

        # Blend ponderado: modelo Poisson + xG proxy
        lam_l = round(lambda_local  * (1 - XG_BLEND) + xg_local  * XG_BLEND, 3)
        lam_v = round(lambda_visita * (1 - XG_BLEND) + xg_visita * XG_BLEND, 3)

        print(f"    xG {local[-14:]}: sot={sot_l:.1f} xG={xg_local:.2f} λ {lambda_local:.2f}→{lam_l:.2f}")
        print(f"    xG {visitante[-14:]}: sot={sot_v:.1f} xG={xg_visita:.2f} λ {lambda_visita:.2f}→{lam_v:.2f}")

        return lam_l, lam_v

    except Exception as e:
        print(f"    xG blend error: {e}")
        return lambda_local, lambda_visita


def xg_resumen(local, visitante, liga_id):
    """
    Devuelve dict con datos xG para incluir en la predicción publicada.
    """
    try:
        from stats_mercados import obtener_stats_ext, _defaults
        sl = obtener_stats_ext(local,     liga_id) or _defaults(liga_id)
        sv = obtener_stats_ext(visitante, liga_id) or _defaults(liga_id)
        return {
            "xg_local":   round(sl.get("disparos_contra", 0) * XG_CONV_RATE, 2),
            "xg_visita":  round(sv.get("disparos_contra", 0) * XG_CONV_RATE, 2),
            "sot_local":  sl.get("disparos_contra", 0),
            "sot_visita": sv.get("disparos_contra", 0),
        }
    except Exception:
        return {}
