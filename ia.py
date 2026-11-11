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
import os
import re
import urllib.error
import urllib.request

from PIL import Image

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"

ADVERTENCIA = ("Resultado orientativo generado por IA a partir de una fotografía. No es un diagnóstico "
               "confirmado: validar con inspección a campo o consulta con un ingeniero agrónomo.")


def api_key():
    return os.environ.get("GEMINI_API_KEY", "").strip()


def _abrir_imagen(origen):
    return Image.open(io.BytesIO(origen) if isinstance(origen, bytes) else origen)


# --------------------------------------------------------------------------
# 1) Procesamiento de imagen propio
# --------------------------------------------------------------------------
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
def _gemini(partes, json_mode=True, timeout=60):
    cuerpo = {
        "contents": [{"parts": partes}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json" if json_mode else "text/plain",
        },
    }
    req = urllib.request.Request(
        GEMINI_URL.format(modelo=GEMINI_MODEL),
        data=json.dumps(cuerpo).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key()},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    partes_resp = data["candidates"][0]["content"]["parts"]
    return "".join(p.get("text", "") for p in partes_resp if not p.get("thought"))


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

Respondé SOLO un objeto JSON con estas claves exactas:
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
    except (urllib.error.URLError, TimeoutError, KeyError, IndexError, ValueError, json.JSONDecodeError) as e:
        return _modo_demo(dano, enfermedades_catalogo, f"Falló la consulta a la IA ({type(e).__name__}).")

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
    return {
        "motor": "gemini",
        "cultivo_detectado": str(r.get("cultivo_identificado", "No identificable"))[:120],
        "coincide_con_lote": bool(r.get("coincide_con_lote", True)),
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


def _modo_demo(dano, enfermedades_catalogo, motivo):
    """Respaldo sin IA externa: usa únicamente el índice de daño por color."""
    if dano is None:
        estado, sev = "dudoso", "ninguna"
    elif dano < 4:
        estado, sev = "sano", "ninguna"
    elif dano < 15:
        estado, sev = "enfermo", "baja"
    elif dano < 35:
        estado, sev = "enfermo", "media"
    else:
        estado, sev = "enfermo", "alta"
    return {
        "motor": "demo",
        "cultivo_detectado": "No determinado (modo demo)",
        "coincide_con_lote": True,
        "estado": estado,
        "enfermedad_texto": None,
        "confianza": 0.3,
        "severidad": sev,
        "sintomas": ([f"Aprox. {dano}% del tejido visible con coloración amarillenta/parda."]
                     if dano is not None else ["No se detectó suficiente tejido vegetal."]),
        "causas": ["Sin IA externa: no es posible estimar la causa."],
        "recomendaciones": ["Inspeccionar la planta a campo.", "Configurar GEMINI_API_KEY para obtener un diagnóstico completo."],
        "comentario": f"MODO DEMO: {motivo} Solo se calculó el índice de daño por color.",
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
