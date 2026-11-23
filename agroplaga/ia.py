"""Módulo de Inteligencia Artificial de AgroPlaga IA.

Dos componentes:
1. Visión artificial con un modelo multimodal (Gemini) que recibe la foto y devuelve
   un diagnóstico estructurado en JSON.
2. Procesamiento de imagen propio (Pillow, espacio de color HSV) que calcula un
   "índice de daño visual": porcentaje de píxeles amarillentos/pardos sobre el
   total de tejido vegetal. Sirve de verificación independiente de la IA.

Si no hay GEMINI_API_KEY (o falla la red) el sistema NO se rompe: usa un modo DEMO
basado solo en el índice de daño y lo informa claramente en pantalla.
"""
import base64
import io
import json
import math
import os
import re
import time
import urllib.error
import urllib.request

from PIL import Image

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash-lite")
# Modelos alternativos válidos para reintentar si el configurado no está disponible.
MODELOS_RESPALDO = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.1-flash-lite", "gemini-2.5-flash"]
_modelo_ok = {"nombre": None}
_ndvi_fecha_cache = {"fecha": None, "vence": 0}
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

ADVERTENCIA = ("Resultado orientativo generado por IA a partir de una fotografía. No es un diagnóstico "
               "confirmado: validar con inspección a campo o consulta con un ingeniero agrónomo.")


def api_key():
    return os.environ.get("GEMINI_API_KEY", "").strip()


# --------------------------------------------------------------------------
# 1) Procesamiento de imagen propio
# --------------------------------------------------------------------------
def _abrir_imagen(origen):
    """Acepta una ruta de archivo o los bytes de la imagen (Vercel no guarda archivos)."""
    return Image.open(io.BytesIO(origen) if isinstance(origen, bytes) else origen)


def indice_dano(ruta):
    """Devuelve el % (0-100) de tejido vegetal con color amarillento/pardo/necrótico."""
    img = _abrir_imagen(ruta).convert("RGB")
    img.thumbnail((160, 160))
    hsv = img.convert("HSV")
    verde = danio = 0
    for h, s, v in hsv.getdata():
        if s < 60 or v < 40:          # fondo gris/blanco o sombra muy oscura
            continue
        if 25 <= h <= 65:             # verde (≈ 35°–90°)
            verde += 1
        elif 5 <= h < 25:             # amarillo / naranja / pardo (≈ 7°–35°)
            danio += 1
    total = verde + danio
    if total < 50:
        return None                   # casi no hay tejido vegetal detectable
    return round(100.0 * danio / total, 1)


def _tiles_xyz(lat, lng, zoom):
    lat = max(-85.05112878, min(85.05112878, lat))
    n = 2 ** zoom
    xtile = int((lng + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    return xtile, ytile


def obtener_mosaico_satelital(lat, lng, zoom=17, cantidad=5):
    """Descarga y une mosaicos del servidor satelital público de Esri/ArcGIS."""
    xtile, ytile = _tiles_xyz(lat, lng, zoom)
    radio = cantidad // 2
    n = 2 ** zoom
    mosaico = Image.new("RGB", (256 * cantidad, 256 * cantidad))
    try:
        for dy in range(-radio, radio + 1):
            for dx in range(-radio, radio + 1):
                tx = (xtile + dx) % n
                ty = ytile + dy
                if ty < 0 or ty >= n:
                    continue
                url = (f"https://server.arcgisonline.com/ArcGIS/rest/services/"
                       f"World_Imagery/MapServer/tile/{zoom}/{ty}/{tx}")
                req = urllib.request.Request(url, headers={"User-Agent": "AgroPlagaIA/1.0"})
                with urllib.request.urlopen(req, timeout=20) as respuesta:
                    tile = Image.open(io.BytesIO(respuesta.read())).convert("RGB")
                mosaico.paste(tile, ((dx + radio) * 256, (dy + radio) * 256))
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        raise ErrorIA(f"No se pudo obtener la imagen satelital: {e}")
    return mosaico


def fecha_ndvi_disponible():
    """Obtiene y cachea la fecha vigente publicada por el mosaico NDVI de NASA GIBS."""
    if _ndvi_fecha_cache["fecha"] and _ndvi_fecha_cache["vence"] > time.time():
        return _ndvi_fecha_cache["fecha"]
    url = "https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml"
    req = urllib.request.Request(url, headers={"User-Agent": "AgroPlagaIA/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as respuesta:
            capacidades = respuesta.read().decode("utf-8")
    except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
        raise ErrorIA(f"No se pudo consultar la fecha de la capa satelital de NASA: {e}")
    capas = re.findall(r"<Layer>(.*?)</Layer>", capacidades, flags=re.DOTALL)
    capa = next((c for c in capas if "<ows:Identifier>MODIS_Terra_NDVI_8Day</ows:Identifier>" in c), None)
    coincidencia = re.search(r"<Default>(\d{4}-\d{2}-\d{2})</Default>", capa or "")
    if not coincidencia:
        raise ErrorIA("NASA no publicó una fecha NDVI disponible para la capa seleccionada.")
    fecha = coincidencia.group(1)
    _ndvi_fecha_cache.update(fecha=fecha, vence=time.time() + 6 * 60 * 60)
    return fecha


def _preparar_imagen(ruta, lado=1024):
    """Reduce la foto para enviarla a la API (menos datos, más rápido)."""
    img = _abrir_imagen(ruta).convert("RGB")
    img.thumbnail((lado, lado))
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


# --------------------------------------------------------------------------
# 2) Llamada a Gemini
# --------------------------------------------------------------------------
class ErrorIA(Exception):
    """Error de la API con un mensaje entendible para el usuario."""


def _mensaje_http(e):
    try:
        detalle = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
    except Exception:
        detalle = ""
    if e.code in (400, 401, 403) and ("API key" in detalle or "api key" in detalle or e.code in (401, 403)):
        return f"La API key de Gemini fue rechazada (HTTP {e.code}). Revisá que esté bien copiada en .env. {detalle[:120]}"
    if e.code == 429:
        return "Se superó el límite gratuito de Gemini (HTTP 429). Esperá un minuto e intentá de nuevo."
    return f"Gemini respondió HTTP {e.code}. {detalle[:160]}"


def _gemini(partes, json_mode=True, timeout=60):
    cuerpo = {
        "contents": [{"parts": partes}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json" if json_mode else "text/plain",
        },
    }
    datos = json.dumps(cuerpo).encode("utf-8")
    candidatos = [_modelo_ok["nombre"]] if _modelo_ok["nombre"] else []
    for m in [GEMINI_MODEL] + MODELOS_RESPALDO:
        if m and m not in candidatos:
            candidatos.append(m)
    ultimo = "sin respuesta"
    for modelo in candidatos:
        req = urllib.request.Request(
            GEMINI_URL.format(modelo=modelo), data=datos,
            headers={"Content-Type": "application/json", "x-goog-api-key": api_key()})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:                      # modelo inexistente: probar el siguiente
                ultimo = f"el modelo {modelo} no existe"
                continue
            if e.code in (429, 500, 502, 503, 504):
                ultimo = _mensaje_http(e)
                continue
            raise ErrorIA(_mensaje_http(e))
        except urllib.error.URLError as e:
            raise ErrorIA(f"No hay conexión con Gemini ({e.reason}). Si estás en un hosting gratuito, verificá que googleapis.com esté permitido.")
        _modelo_ok["nombre"] = modelo
        try:
            partes_resp = data["candidates"][0]["content"]["parts"]
        except (KeyError, IndexError):
            raise ErrorIA("Gemini no devolvió contenido (la imagen pudo ser bloqueada por sus filtros).")
        return "".join(p.get("text", "") for p in partes_resp if not p.get("thought"))
    if any(f"HTTP {codigo}" in ultimo for codigo in (429, 500, 502, 503, 504)):
        raise ErrorIA(f"Gemini está temporalmente ocupado en los modelos probados. {ultimo} Intentá de nuevo más tarde.")
    raise ErrorIA(f"No se encontró un modelo de Gemini disponible ({ultimo}). Definí GEMINI_MODEL en .env con un modelo vigente.")


def probar_conexion():
    """Prueba mínima para el panel de administración. Devuelve (ok, mensaje)."""
    if not api_key():
        return False, "No se detectó GEMINI_API_KEY. Verificá que el archivo se llame exactamente .env (no .env.example), que la clave esté después del signo = sin comillas ni espacios, y reiniciá/recargá la aplicación."
    try:
        t = _gemini([{"text": "Respondé solo con la palabra: OK"}], json_mode=False, timeout=30)
        return True, f"Conexión correcta con Gemini (modelo {_modelo_ok['nombre']}). Respuesta: {t.strip()[:40]}"
    except ErrorIA as e:
        return False, str(e)
    except Exception as e:
        return False, f"Error inesperado: {type(e).__name__}: {e}"


def _normalizar(t):
    import unicodedata
    t = unicodedata.normalize("NFD", str(t).lower())
    return "".join(ch for ch in t if unicodedata.category(ch) != "Mn")


def cultivo_coincide(cultivo_lote, identificado, bandera):
    """True si la foto corresponde al cultivo del lote, False si no, None si no se puede saber."""
    ident, lote = _normalizar(identificado), _normalizar(cultivo_lote)
    if not ident or "no identific" in ident or "no determin" in ident:
        return None
    if lote in ident or ident in lote:
        return True
    return False          # nombres distintos (ej. "tomate" vs "trigo"): no coincide


def _parsear_json(texto):
    texto = texto.strip()
    texto = re.sub(r"^```(?:json)?|```$", "", texto, flags=re.MULTILINE).strip()
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", texto, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise


def _lista(valor):
    if isinstance(valor, list):
        return [str(x) for x in valor if str(x).strip()][:8]
    if isinstance(valor, str) and valor.strip():
        return [valor.strip()]
    return []


def analizar_foto(ruta, cultivo_esperado, enfermedades_catalogo):
    """Analiza una foto de planta. Devuelve un dict normalizado.

    cultivo_esperado: nombre del cultivo del lote (ej. "Soja").
    enfermedades_catalogo: lista de nombres de enfermedades conocidas para ese cultivo.
    """
    dano = indice_dano(ruta)
    if not api_key():
        return _modo_demo(dano, enfermedades_catalogo, "No hay GEMINI_API_KEY configurada.")

    prompt = f"""Sos un asistente de fitopatología para agricultura argentina.
Analizá la fotografía adjunta (hoja o planta). El lote está registrado como cultivo: "{cultivo_esperado}".
Enfermedades del catálogo para ese cultivo: {json.dumps(enfermedades_catalogo, ensure_ascii=False)}.

PASO 1 (obligatorio): decidí qué se ve realmente en la foto y si corresponde al cultivo "{cultivo_esperado}".
Si la foto muestra OTRO cultivo (por ejemplo trigo en vez de tomate), un paisaje, una ciudad, una persona u otra cosa,
NO diagnostiques enfermedades: poné "coincide_con_lote": false, "estado": "dudoso", "enfermedad": "Ninguna" y explicá en "escena" qué ves.

Respondé SOLO un objeto JSON con estas claves exactas:
- "escena": descripción breve (máx. 25 palabras) de lo que muestra la foto
- "es_planta": true/false (false si la foto no muestra una planta/hoja/cultivo)
- "cultivo_identificado": nombre del cultivo que ves en la foto (texto corto) o "No identificable"
- "coincide_con_lote": true/false (el cultivo de la foto coincide con "{cultivo_esperado}")
- "estado": uno de "sano", "enfermo", "dudoso"
- "enfermedad": nombre EXACTO del catálogo si corresponde, "Otra: <nombre>" si es una enfermedad/problema no listado, o "Ninguna"
- "confianza": número entre 0 y 1
- "severidad": uno de "ninguna", "baja", "media", "alta"
- "sintomas_observados": lista de 2 a 5 síntomas visibles en la foto
- "causas_posibles": lista de 1 a 4 causas posibles (hongos, plagas, deficiencias, estrés hídrico, etc.)
- "recomendaciones_inspeccion": lista de 3 a 5 acciones concretas de inspección a campo
- "comentario": una oración breve explicando el razonamiento

Reglas: no inventes certeza; si la imagen es borrosa o ambigua usá "dudoso" y confianza baja.
Son recomendaciones de INSPECCIÓN, no indiques dosis de agroquímicos."""

    try:
        texto = _gemini([
            {"text": prompt},
            {"inline_data": {"mime_type": "image/jpeg", "data": _preparar_imagen(ruta)}},
        ])
        r = _parsear_json(texto)
    except ErrorIA as e:
        return _modo_demo(dano, enfermedades_catalogo, str(e))
    except (TimeoutError, KeyError, IndexError, ValueError, json.JSONDecodeError) as e:
        return _modo_demo(dano, enfermedades_catalogo, f"La respuesta de la IA no se pudo interpretar ({type(e).__name__}).")

    es_planta = bool(r.get("es_planta", True))
    estado = r.get("estado", "dudoso")
    if not es_planta:
        estado = "no_planta"
    elif estado not in ("sano", "enfermo", "dudoso"):
        estado = "dudoso"
    severidad = r.get("severidad", "ninguna")
    if severidad not in ("ninguna", "baja", "media", "alta"):
        severidad = "ninguna"
    try:
        confianza = max(0.0, min(1.0, float(r.get("confianza", 0.5))))
    except (TypeError, ValueError):
        confianza = 0.5

    enf = str(r.get("enfermedad", "Ninguna")).strip()
    identificado = str(r.get("cultivo_identificado", "No identificable"))[:120]
    coincide = cultivo_coincide(cultivo_esperado, identificado, r.get("coincide_con_lote", True))
    return {
        "motor": "gemini",
        "escena": str(r.get("escena", ""))[:300],
        "cultivo_detectado": identificado,
        "coincide_con_lote": coincide,
        "estado": estado,
        "enfermedad_texto": None if enf.lower() in ("ninguna", "none", "") else enf[:200],
        "confianza": confianza,
        "severidad": severidad if estado != "no_planta" else "ninguna",
        "sintomas": _lista(r.get("sintomas_observados")),
        "causas": _lista(r.get("causas_posibles")),
        "recomendaciones": _lista(r.get("recomendaciones_inspeccion")),
        "comentario": str(r.get("comentario", ""))[:400],
        "indice_dano": dano,
        "aviso": ADVERTENCIA,
    }


def analizar_zona(ruta, lat, lng, cultivo=None):
    """Analiza una zona completa vista desde satélite como una única imagen."""
    if not api_key():
        return {
            "motor": "demo",
            "estado": "dudoso",
            "confianza": 0.2,
            "severidad": "ninguna",
            "hallazgos": ["No se configuró GEMINI_API_KEY."],
            "sectores_atencion": [],
            "recomendaciones": ["Configurar Gemini y volver a ejecutar el análisis."],
            "comentario": "No se calculó NDVI ni se clasificaron cultivos. La imagen satelital RGB no permite obtener ese índice.",
            "error_ia": "No se configuró GEMINI_API_KEY.",
            "aviso": ADVERTENCIA,
        }

    cultivo_texto = f'El lote/campo está asociado a "{cultivo}".' if cultivo else ""
    prompt = f"""Sos un analista de imágenes satelitales para agricultura argentina.
Analizá esta ZONA COMPLETA, no una hoja aislada. Coordenadas centrales aproximadas: {lat:.6f}, {lng:.6f}.
{cultivo_texto}

Respondé SOLO un objeto JSON exacto con:
- "estado": "sano", "dudoso" o "alerta"
- "confianza": número entre 0 y 1
- "severidad": "ninguna", "baja", "media" o "alta"
- "hallazgos": lista de 3 a 6 observaciones espaciales concretas
- "sectores_atencion": lista de sectores de la cuadrícula que parecen irregulares (ej. "Fila central, columna derecha")
- "recomendaciones": lista de 3 a 5 acciones de verificación a campo
- "comentario": síntesis breve

Buscá patrones visibles de color/filas/huecos, zonas homogéneas o irregulares y diferencias entre sectores.
La imagen es RGB de cartografía satelital y su fecha puede no ser actual; no la llames NDVI ni afirmes qué cultivo hay si no se distingue.
No afirmes que una zona enferma sin evidencia: distinguí vegetación, suelo, sombra, riego, caminos y cosecha.
No indiques dosis de agroquímicos."""
    try:
        resultado = _parsear_json(_gemini([
            {"text": prompt},
            {"inline_data": {"mime_type": "image/jpeg", "data": _preparar_imagen(ruta, 1280)}},
        ]))
        estado = resultado.get("estado", "dudoso")
        if estado not in ("sano", "dudoso", "alerta"):
            estado = "dudoso"
        severidad = resultado.get("severidad", "ninguna")
        if severidad not in ("ninguna", "baja", "media", "alta"):
            severidad = "ninguna"
        try:
            confianza = max(0.0, min(1.0, float(resultado.get("confianza", 0.5))))
        except (TypeError, ValueError):
            confianza = 0.5
        return {
            "motor": "gemini",
            "estado": estado,
            "confianza": confianza,
            "severidad": severidad,
            "hallazgos": _lista(resultado.get("hallazgos")),
            "sectores_atencion": _lista(resultado.get("sectores_atencion")),
            "recomendaciones": _lista(resultado.get("recomendaciones")),
            "comentario": str(resultado.get("comentario", ""))[:400],
            "aviso": ADVERTENCIA,
        }
    except (ErrorIA, TimeoutError, KeyError, IndexError, ValueError, json.JSONDecodeError) as e:
        return {
            "motor": "demo",
            "estado": "dudoso",
            "confianza": 0.2,
            "severidad": "ninguna",
            "hallazgos": ["La IA satelital no pudo procesar el mosaico."],
            "sectores_atencion": [],
            "recomendaciones": ["Repetir el análisis y revisar manualmente los sectores con menor cobertura."],
            "comentario": "No se calculó NDVI ni se clasificaron cultivos. La imagen satelital RGB no permite obtener ese índice.",
            "error_ia": str(e),
            "aviso": ADVERTENCIA,
        }


def _modo_demo(dano, enfermedades_catalogo, motivo):
    """Respaldo sin IA externa: solo índice de daño. Nunca afirma que hay enfermedad."""
    if dano is None:
        estado, sev = "dudoso", "ninguna"
    elif dano < 4:
        estado, sev = "sano", "ninguna"
    else:
        estado = "dudoso"
        sev = "baja" if dano < 15 else "media" if dano < 35 else "alta"
    return {
        "motor": "demo",
        "escena": "",
        "error_ia": motivo,
        "cultivo_detectado": "No determinado (modo demo)",
        "coincide_con_lote": None,
        "estado": estado,
        "enfermedad_texto": None,
        "confianza": 0.2,
        "severidad": sev,
        "sintomas": ([f"Aprox. {dano}% del tejido visible con coloración amarillenta/parda (puede deberse a madurez, suelo o luz)."]
                     if dano is not None else ["No se detectó suficiente tejido vegetal."]),
        "causas": ["Sin IA externa no es posible estimar la causa ni confirmar el cultivo."],
        "recomendaciones": ["Inspeccionar la planta a campo.", "Resolver el problema de conexión con la IA (ver aviso) y repetir el análisis."],
        "comentario": f"MODO DEMO: {motivo}",
        "indice_dano": dano,
        "aviso": ADVERTENCIA,
    }


# --------------------------------------------------------------------------
# 3) Resumen de informes con IA (texto)
# --------------------------------------------------------------------------
def redactar_informe(titulo, datos):
    """Genera un texto explicativo a partir de estadísticas agregadas."""
    if not api_key():
        return _informe_simple(titulo, datos)
    prompt = (f"Redactá en español, para un productor agropecuario, un informe técnico breve (máx. 250 palabras) "
              f"titulado «{titulo}», basado SOLO en estos datos agregados (JSON):\n"
              f"{json.dumps(datos, ensure_ascii=False)}\n\n"
              "Incluí: situación general, problemas más frecuentes, lotes/sectores de atención y 3 recomendaciones "
              "de inspección. Aclará que son estimaciones basadas en fotografías y no diagnósticos confirmados. "
              "No inventes datos que no estén en el JSON ni indiques dosis de productos.")
    try:
        return _gemini([{"text": prompt}], json_mode=False).strip()
    except Exception:
        return _informe_simple(titulo, datos)


def _informe_simple(titulo, d):
    lineas = [f"{titulo} (resumen automático sin IA externa)",
              f"Se registraron {d.get('total', 0)} análisis: {d.get('sanos', 0)} sanos, "
              f"{d.get('enfermos', 0)} con síntomas y {d.get('dudosos', 0)} dudosos."]
    if d.get("enfermedades"):
        top = ", ".join(f"{k} ({v})" for k, v in list(d["enfermedades"].items())[:3])
        lineas.append(f"Problemas más frecuentes: {top}.")
    lineas.append("Estos valores son estimaciones basadas en fotografías; confirmar con inspección a campo.")
    return "\n".join(lineas)
