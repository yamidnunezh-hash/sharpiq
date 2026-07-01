---
name: project-validacion-motor-2026-07-01
description: 2026-07-01 Validación del motor con picks reales (calibración+ROI) + compuerta de valor aplicada a clasificar_tiers según los hallazgos.
metadata:
  type: project
---

# Validación del motor SharpIQ — HECHO (2026-07-01)

Yamid pidió "validar que el motor gana" antes de agregar features. Construí
**sharpiq-engine/validar_motor.py**: lee los picks YA resueltos de
PREDICCIONES_HISTORIAL (datos.js) — no inventa nada — y saca calibración + ROI +
valor por rango de cuota. Correr con `python validar_motor.py` (o `--json`).

## Hallazgos con 74 picks reales resueltos (indicativo, muestra chica)
- **El motor SÍ gana**: 45W-25L (64.3%), ROI **+0.43%**. Ventaja real pero fina.
- **Banda 70-80% PERFECTAMENTE calibrada** (dice 73.4%, acierta 73.5%, 34 picks) →
  argumento de venta fuerte: cuando el motor está confiado, su número es honesto.
- **Favoritos <1.50 PIERDEN plata**: ROI -5.19% (36 picks). El mercado los tasa bien.
- **El edge vive en cuotas 1.50-3.00**: ROI +6.5% y +5.9%.
- **Banda 60-70% sobreconfía**: dice 65%, acierta 50% (solo 16 picks → señal débil).

## Compuerta de valor aplicada (motor.py, clasificar_tiers, filtro CENTRAL)
Justo tras el `_EV_TOPE_PUB`, filtro tunable y reversible que NO toca el Poisson:
- **#1 PISO_CUOTA=1.50**: no publica favoritos <1.50 (aplica también a la excepción
  Mundial, cuyo piso subió de 1.40 → 1.50). ⚠️ En días de puros favoritos el VIP
  puede quedar más delgado — es el trade correcto (menos volumen, más rentable).
  Si Yamid quiere más volumen, bajar la constante (ej. 1.45).
- **#2 ZONA_VALOR (1.50-3.00) +10% al score**: prioriza el sweet spot al elegir el pick.
- **#3 banda 60-70% exige EV>=4** (BANDA_RIESGO_MIN_EV), pero **exenta los picks
  alta_confianza (Mundial)** porque la evidencia es de solo 16 picks. Guardia conservadora.

Aplica en la próxima corrida del motor (GitHub Actions 11am/3pm/7pm COT); Railway no
corre el motor. Ver [[project-motor-estado]] y [[project-sharpscore-shipped]].

## Pendiente de validación (fase 2)
- **CLV** (¿los picks le ganan a la línea de cierre de Pinnacle?) — el estándar de oro
  del edge. Requiere datos apertura/cierre (db_clv.py PostgreSQL / database.py SQLite);
  no construido aún porque no verifiqué que esté poblado. Siguiente paso natural.
- Re-correr validar_motor.py cuando haya más picks (74 es muestra chica) para confirmar
  la banda 60-70% y afinar las constantes de la compuerta con datos, no intuición.
