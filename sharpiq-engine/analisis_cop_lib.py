# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
from scipy.stats import poisson

PROMEDIO = 1.35
RHO = -0.10
ESCALA_LIB = 0.95

def dc(i, j, mh, ma):
    if i == 0 and j == 0: return 1 - mh * ma * RHO
    elif i == 1 and j == 0: return 1 + ma * RHO
    elif i == 0 and j == 1: return 1 + mh * RHO
    elif i == 1 and j == 1: return 1 - RHO
    return 1.0

def modelo(sl, sv, ventaja=1.20, escala=ESCALA_LIB):
    atq_l, def_l, fl = sl
    atq_v, def_v, fv = sv
    mh = round((atq_l/PROMEDIO)*(def_v/PROMEDIO)*PROMEDIO*ventaja*fl*escala, 3)
    ma = round((atq_v/PROMEDIO)*(def_l/PROMEDIO)*PROMEDIO*fv*escala, 3)
    MAX = 8
    mat = {}
    tot = 0.0
    for i in range(MAX):
        for j in range(MAX):
            p = max(poisson.pmf(i, mh) * poisson.pmf(j, ma) * dc(i, j, mh, ma), 0.0)
            mat[(i, j)] = p
            tot += p
    mat = {k: v/tot for k, v in mat.items()}
    vl = ve = vv = o15 = o25 = o35 = btts = 0.0
    for (i, j), p in mat.items():
        if i > j:   vl += p
        elif i == j: ve += p
        else:        vv += p
        t = i + j
        if t > 1.5: o15 += p
        if t > 2.5: o25 += p
        if t > 3.5: o35 += p
        if i > 0 and j > 0: btts += p
    d12 = vl + vv
    top5 = sorted([(v, k) for k, v in mat.items()], reverse=True)[:5]
    return mh, ma, dict(vl=vl, ve=ve, vv=vv, o15=o15, o25=o25, o35=o35,
                        btts=btts,
                        dnb_l=vl/d12 if d12 > 0 else 0,
                        dnb_v=vv/d12 if d12 > 0 else 0,
                        top5=top5)

def ev(prob, c):
    if not c or c == '?': return None
    return round((prob * c - 1) * 100, 1)

def imp(c):
    return round(100/c, 1) if c and c != '?' else 0

def no_vig(co, cu):
    if not co or not cu: return 50.0, 50.0
    mg = 1/co + 1/cu
    return round((1/co)/mg*100, 1), round((1/cu)/mg*100, 1)

def analizar(nombre_l, nombre_v, sl, sv, c1, cx, c2, co, cu,
             ventaja=1.20, escala=ESCALA_LIB, nota=''):
    mh, ma, r = modelo(sl, sv, ventaja, escala)
    vl, ve, vv = r['vl'], r['ve'], r['vv']
    o25, o15, o35, btts = r['o25'], r['o15'], r['o35'], r['btts']
    dnb_l, dnb_v = r['dnb_l'], r['dnb_v']
    pinn_o, pinn_u = no_vig(co, cu)

    print(f"  Goles esperados: {nombre_l} {mh:.2f}g | {nombre_v} {ma:.2f}g | Total {mh+ma:.2f}g")
    if nota:
        print(f"  Contexto: {nota}")
    print()
    print(f"  {'RESULTADO':<24} {'MODELO%':>7}  {'PINN%':>6}  {'CUOTA':>6}  {'EV':>8}")
    print(f"  {'-'*56}")
    print(f"  {nombre_l[:24]:<24} {vl*100:>6.1f}%  {imp(c1):>5.1f}%  {c1:>6.2f}  {ev(vl,c1):>+7.1f}%")
    print(f"  {'Empate':<24} {ve*100:>6.1f}%  {imp(cx):>5.1f}%  {cx:>6.2f}  {ev(ve,cx):>+7.1f}%")
    print(f"  {nombre_v[:24]:<24} {vv*100:>6.1f}%  {imp(c2):>5.1f}%  {c2:>6.2f}  {ev(vv,c2):>+7.1f}%")
    print(f"  {'-'*56}")
    print(f"  {'Over 2.5':<24} {o25*100:>6.1f}%  {pinn_o:>5.1f}%  {co:>6.2f}  {ev(o25,co):>+7.1f}%")
    print(f"  {'Under 2.5':<24} {(1-o25)*100:>6.1f}%  {pinn_u:>5.1f}%  {cu:>6.2f}  {ev(1-o25,cu):>+7.1f}%")
    print(f"  {'Over 1.5':<24} {o15*100:>6.1f}%")
    print(f"  {'Over 3.5':<24} {o35*100:>6.1f}%")
    print(f"  {'BTTS Si':<24} {btts*100:>6.1f}%")
    print(f"  {'DNB {}'.format(nombre_l[:12]):<24} {dnb_l*100:>6.1f}%")
    print()
    print(f"  Marcadores mas probables:")
    for p, (i, j) in r['top5']:
        ganador = nombre_l[:14] if i > j else ('EMPATE' if i == j else nombre_v[:14])
        print(f"    {i}-{j}  ({p*100:.1f}%)  {ganador}")
    print()

    picks = []
    for lbl, prob, c in [
        (f"1 {nombre_l[:18]}", vl, c1),
        ("X Empate", ve, cx),
        (f"2 {nombre_v[:18]}", vv, c2),
        ("Over 2.5", o25, co),
        ("Under 2.5", 1-o25, cu),
    ]:
        e = ev(prob, c)
        if e and e > 0:
            picks.append((e, lbl, round(prob*100, 1), c))
    picks.sort(reverse=True)

    if picks:
        print(f"  PICKS EV POSITIVO vs Pinnacle:")
        for e_val, lbl, pct, c in picks:
            star = "  <-- MEJOR PICK" if e_val == picks[0][0] else ""
            print(f"    EV {e_val:+.1f}%  |  {lbl} @{c:.2f}  (modelo {pct}%){star}")
    else:
        print(f"  Sin EV positivo en este partido")
    print()


# ── STATS (ataque, defensa_recibida, forma) ──────────────────
S = {
    'IDV':          (1.50, 1.00, 0.74),
    'Rosario':      (1.40, 1.20, 0.68),
    'Libertad':     (1.30, 1.20, 0.64),
    'UCV':          (1.10, 1.40, 0.58),
    'Bolivar':      (1.60, 1.00, 0.72),
    'Rivadavia':    (1.20, 1.40, 0.58),
    'Corinthians':  (1.50, 1.20, 0.68),
    'Platense':     (1.20, 1.30, 0.62),
    'Fluminense':   (1.50, 1.10, 0.72),
    'La Guaira':    (1.00, 1.60, 0.50),
    'Penharol':     (1.50, 1.00, 0.75),
    'SantaFe':      (1.30, 1.20, 0.65),
    'CerroPno':     (1.50, 1.10, 0.70),
    'Cristal':      (1.20, 1.30, 0.61),
    'Palmeiras':    (1.80, 0.80, 0.82),
    'Junior':       (1.30, 1.20, 0.64),
    'Cruzeiro':     (1.60, 1.00, 0.74),
    'BarcelonaEC':  (1.40, 1.10, 0.70),
    'Boca':         (1.70, 1.00, 0.78),
    'UCChile':      (1.60, 1.00, 0.73),
}

SEP = "=" * 64

print()
print(SEP)
print("  COPA LIBERTADORES 2026 - ANALISIS PROFUNDO")
print("  Modelo Poisson + Dixon-Coles | Cuotas reales PINNACLE")
print("  Calibrado: Copa Lib promedio real 1.90g/partido (20 partidos)")
print(SEP)

# 27 mayo 22:00 UTC = 17:00 COT
print()
print("  MARTES 27/05  17:00 COT (22:00 UTC)")
print(SEP)

print()
print("  PARTIDO 1: Independiente del Valle vs Rosario Central")
print("  Ecuador vs Argentina | Grupo B")
analizar('IDV', 'Rosario Central',
         S['IDV'], S['Rosario'],
         1.91, 3.38, 4.09, 1.89, 1.91,
         ventaja=1.35,
         nota="IDV en Quito (2850m). Altitud = ventaja brutal. Equipos argentinos bajan rendimiento 15-20%.")

print()
print("  PARTIDO 2: Libertad Asuncion vs UCV FC")
print("  Paraguay vs Venezuela | Grupo C")
analizar('Libertad', 'UCV FC',
         S['Libertad'], S['UCV'],
         1.41, 4.70, 6.87, 1.88, 1.93,
         ventaja=1.22,
         nota="UCV es el equipo mas debil de su grupo. Libertad solido local en Asuncion.")

# 28 mayo 00:30 UTC = 19:30 COT del 27
print()
print("  MARTES 27/05  19:30 COT (28 mayo 00:30 UTC)")
print(SEP)

print()
print("  PARTIDO 3: Club Bolivar vs Independiente Rivadavia")
print("  Bolivia vs Argentina | Grupo H")
analizar('Club Bolivar', 'Ind. Rivadavia',
         S['Bolivar'], S['Rivadavia'],
         2.32, 3.48, 2.76, 1.92, 1.83,
         ventaja=1.40,
         nota="La Paz 3600m: uno de los estadios mas altos del mundo. Rivadavia (Mendoza, ArgB) debut Copa Lib.")

print()
print("  PARTIDO 4: Corinthians-SP vs Platense")
print("  Brasil vs Argentina | Grupo F")
analizar('Corinthians', 'Platense',
         S['Corinthians'], S['Platense'],
         1.69, 3.44, 5.64, 1.85, 1.96,
         ventaja=1.20,
         nota="Corinthians en Neo Quimica Arena (Sao Paulo). Platense primer Copa Lib en su historia.")

print()
print("  PARTIDO 5: Fluminense vs Deportivo La Guaira")
print("  Brasil vs Venezuela | Grupo D")
analizar('Fluminense', 'La Guaira',
         S['Fluminense'], S['La Guaira'],
         1.13, 8.61, 14.42, 1.98, 1.81,
         ventaja=1.20,
         nota="Fluminense campeon 2023. La Guaira primer Copa Lib. Pinnacle 88% Fluminense.")

print()
print("  PARTIDO 6: Penharol vs Independiente Santa Fe")
print("  Uruguay vs Colombia | Grupo E")
analizar('Penharol', 'Santa Fe',
         S['Penharol'], S['SantaFe'],
         1.88, 3.38, 4.59, 2.08, 1.79,
         ventaja=1.22,
         nota="Penharol local en Centenario (Montevideo). Santa Fe buena copa pero visitante largo.")

# 28 mayo 22:00 UTC = 17:00 COT
print()
print("  JUEVES 28/05  17:00 COT (22:00 UTC)")
print(SEP)

print()
print("  PARTIDO 7: Cerro Porteno vs Sporting Cristal")
print("  Paraguay vs Peru | Grupo G")
analizar('Cerro Porteno', 'Sporting Cristal',
         S['CerroPno'], S['Cristal'],
         1.60, 3.57, 5.91, 1.89, 1.89,
         ventaja=1.22,
         nota="Cerro Porteno solido local en Paraguay. Cristal (Lima) liga peruana mucho mas debil.")

print()
print("  PARTIDO 8: Palmeiras vs Junior FC")
print("  Brasil vs Colombia | Grupo A")
analizar('Palmeiras', 'Junior FC',
         S['Palmeiras'], S['Junior'],
         1.23, 5.64, 10.92, 1.85, 1.92,
         ventaja=1.20,
         nota="Palmeiras en Allianz Parque. Mejor equipo de LATAM 2025-26. Junior fuera de Colombia es debil.")

# 29 mayo 00:30 UTC = 19:30 COT del 28
print()
print("  JUEVES 28/05  19:30 COT (29 mayo 00:30 UTC)")
print(SEP)

print()
print("  PARTIDO 9: Cruzeiro vs Barcelona SC (Ecuador)")
print("  Brasil vs Ecuador | Grupo G")
analizar('Cruzeiro', 'Barcelona SC',
         S['Cruzeiro'], S['BarcelonaEC'],
         1.20, 5.60, 12.06, 1.85, 1.89,
         ventaja=1.20,
         nota="Cruzeiro en Mineirao (BH). Brasileirao es la liga mas fuerte de LATAM actualmente.")

print()
print("  PARTIDO 10: Boca Juniors vs Universidad Catolica (Chile)")
print("  Argentina vs Chile | Grupo H")
analizar('Boca Juniors', 'U. Catolica CHL',
         S['Boca'], S['UCChile'],
         1.40, 4.41, 8.03, 1.82, 2.01,
         ventaja=1.25,
         nota="La Bombonera es el estadio mas intimidador de LATAM. UC Chile buena temporada pero visitante.")

# RESUMEN FINAL
print(SEP)
print("  RANKING GLOBAL DE PICKS POR EV (todos los partidos)")
print(SEP)
