"""Utilidades de geometría para la geocerca por sitio (feature 026).

Se resuelve en Python puro a propósito: la alternativa era PostGIS, que para
comparar un punto contra un círculo de un kilómetro es una dependencia de
infraestructura enorme a cambio de nada. La fórmula del haversine sobre una esfera
tiene un error de ~0,5 % contra el elipsoide WGS84 — cinco metros en un kilómetro,
irrelevante frente al ±20 m de precisión del propio fix.
"""

import math

# Radio medio de la Tierra (IUGG), en metros.
EARTH_RADIUS_M = 6371008.8


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distancia en metros entre dos puntos (grados decimales)."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    # asin sobre min(1, ...) por seguridad numérica: con puntos idénticos el
    # redondeo puede dejar `a` apenas por encima de 1 y math.asin explota.
    return 2 * EARTH_RADIUS_M * math.asin(min(1.0, math.sqrt(a)))
