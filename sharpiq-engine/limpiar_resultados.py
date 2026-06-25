# -*- coding: utf-8 -*-
"""Limpieza de INTEGRIDAD del track record (datos.js + index.html inline).

Arregla el dano que dejo el bug del writer (Caso B insertaba un 'resultado'
duplicado al re-resolver una entrada ya marcada -> la web tomaba el ultimo y
mostraba ACIERTO/fallo equivocado):

  1) DEDUPLICA claves 'resultado' repetidas en cada entrada (deja una).
  2) RE-EVALUA cada pick de FUTBOL ya resuelto contra el marcador REAL de
     API-Football y corrige marcas erroneas (reusa _auto_verificar_resueltos).
  3) Sincroniza el bloque inline de index.html (lo que ve la home).

Seguro: solo corrige futbol con match unico de alta similitud (>=0.8) + fecha;
nunca inventa ni danha una marca correcta. Uso puntual (one-shot).
"""
import re
import auto_resultados as ar
from motor import _apifb


def dedupe_resultado(texto):
    """Colapsa 'resultado:"A", resultado:"B", ...' -> deja solo el PRIMERO."""
    pat = re.compile(r'(resultado:\s*"[^"]*")(?:\s*,\s*resultado:\s*"[^"]*")+')
    total = [0]
    def _c(m):
        total[0] += len(re.findall(r'resultado:\s*"[^"]*"', m.group(0))) - 1
        return m.group(1)
    return pat.sub(_c, texto), total[0]


def fixtures_finalizados(texto):
    """Junta los fixtures FT de las fechas presentes en datos.js (pocas llamadas)."""
    fechas = set()
    for m in re.finditer(r'fecha:\s*"(\d{2}/\d{2}/\d{2})"', texto):
        iso = ar._fecha_pick_iso(m.group(1))
        if iso:
            fechas.add(iso)
    fts = []
    for d in sorted(fechas):
        r = _apifb('fixtures', {'date': d})
        for f in (r.get('response') or []):
            if f['fixture']['status']['short'] in ('FT', 'AET', 'PEN'):
                fts.append(f)
    return fts


def main():
    texto = ar.leer_datos()
    texto, n_dup = dedupe_resultado(texto)
    print(f"1) Duplicados de 'resultado' eliminados: {n_dup}")

    fts = fixtures_finalizados(texto)
    print(f"2) Fixtures FT recopilados de API-Football: {len(fts)}")

    texto, n_corr, detalles = ar._auto_verificar_resueltos(texto, fts)
    print(f"3) Marcas corregidas vs resultado REAL: {n_corr}")
    for d in detalles:
        print("     -", d)

    ar.escribir_datos(texto)
    ok = ar.sincronizar_index_html(texto)
    print(f"4) index.html sincronizado: {ok}")
    print("LISTO.")


if __name__ == '__main__':
    main()
