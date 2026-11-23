"""Verificación de ubicación: distancia al campo registrado y tipo de zona (rural/urbana).

La distancia se calcula siempre (sin Internet). El tipo de zona usa el servicio gratuito
Nominatim de OpenStreetMap en modo "mejor esfuerzo": si no hay conexión, se omite sin error.
"""
import json
import math
import urllib.parse
import urllib.request

_USO_RURAL = {"farmland", "meadow", "orchard", "vineyard", "farmyard", "grass", "forest", "greenhouse_horticulture", "plant_nursery"}
_CATEGORIAS_URBANAS = {"highway", "building", "amenity", "shop", "office", "tourism", "railway", "healthcare", "craft"}
_CLAVES_URBANAS = ("suburb", "neighbourhood", "quarter", "city_block", "residential")


def distancia_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def consultar_zona(lat, lng, timeout=4):
    """Devuelve {'lugar': str, 'urbana': bool|None} o None si no se pudo consultar."""
    url = "https://nominatim.openstreetmap.org/reverse?" + urllib.parse.urlencode(
        {"lat": lat, "lon": lng, "format": "jsonv2", "zoom": 18, "accept-language": "es"})
    req = urllib.request.Request(url, headers={"User-Agent": "AgroPlagaIA/1.0 (proyecto educativo)"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
    except Exception:
        return None
    if "error" in d:
        return None
    cat, tipo, dire = d.get("category", ""), d.get("type", ""), d.get("address", {}) or {}
    if cat == "landuse" and tipo in _USO_RURAL:
        urbana = False
    elif cat in _CATEGORIAS_URBANAS or any(k in dire for k in _CLAVES_URBANAS):
        urbana = True
    else:
        urbana = None
    partes = [dire.get(k) for k in ("road", "suburb", "village", "town", "city", "state") if dire.get(k)]
    return {"lugar": ", ".join(partes[:3]) or d.get("display_name", "")[:80], "urbana": urbana}


def evaluar(lat, lng, campo_lat=None, campo_lng=None, campo_nombre="", superficie_ha=None):
    """Devuelve una lista de alertas (texto) sobre la ubicación marcada."""
    alertas = []
    if lat is None or lng is None:
        return ["No se marcó una ubicación para este análisis."]
    if campo_lat is not None and campo_lng is not None:
        km = distancia_km(lat, lng, campo_lat, campo_lng)
        radio = math.sqrt(max(superficie_ha or 0, 0) * 0.01 / math.pi)     # radio de un círculo equivalente
        limite = max(3.0, radio * 3)
        if km > limite:
            alertas.append(f"La ubicación marcada está a {km:.1f} km de la ubicación registrada del campo «{campo_nombre}». Verificá que sea el lugar correcto.")
    z = consultar_zona(lat, lng)
    if z and z["urbana"]:
        alertas.append(f"El punto marcado parece una zona urbana o una calle ({z['lugar']}), no un lote agrícola. Revisá la ubicación.")
    return alertas
