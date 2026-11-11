"""Crea las tablas y carga datos de prueba (usuarios, catálogos, campos, lotes y análisis).

Uso:
    python seed.py            # crea todo (si la base ya tiene datos, avisa y no toca nada)
    python seed.py --force    # BORRA todo y vuelve a crear

Las fotos de prueba se generan con Pillow (hojas dibujadas), no son fotos reales.
Los análisis de prueba están marcados con motor = 'prueba'.
"""
import json
import os
import random
import sys
from datetime import datetime, timedelta

from PIL import Image, ImageDraw, ImageFilter
from werkzeug.security import generate_password_hash

# Cargar .env antes de importar database
ruta_env = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(ruta_env):
    for linea in open(ruta_env, encoding="utf-8"):
        linea = linea.strip()
        if linea and not linea.startswith("#") and "=" in linea:
            k, v = linea.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import database as dbm  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOADS = os.path.join(BASE, "static", "uploads")

CULTIVOS = [
    ("Soja", "Glycine max", "Oleaginosa de siembra primavero-estival."),
    ("Maíz", "Zea mays", "Cereal de siembra temprana o tardía."),
    ("Trigo", "Triticum aestivum", "Cereal de invierno."),
    ("Girasol", "Helianthus annuus", "Oleaginosa de siembra primaveral."),
    ("Maní", "Arachis hypogaea", "Leguminosa oleaginosa, típica del centro-sur de Córdoba."),
    ("Tomate", "Solanum lycopersicum", "Hortaliza de fruto."),
    ("Papa", "Solanum tuberosum", "Tubérculo."),
    ("Vid", "Vitis vinifera", "Cultivo perenne."),
]

# (cultivo, nombre, científico, agente, síntomas, qué inspeccionar)
ENFERMEDADES = [
    ("Soja", "Roya asiática de la soja", "Phakopsora pachyrhizi", "hongo",
     "Pústulas pequeñas pardo-rojizas en el envés de las hojas, amarillamiento y caída prematura del follaje.",
     "Revisar el envés de hojas del tercio inferior y medio con lupa; muestrear varios puntos del lote; registrar incidencia."),
    ("Soja", "Mancha ojo de rana", "Cercospora sojina", "hongo",
     "Manchas circulares con centro grisáceo y borde pardo-rojizo en hojas.",
     "Verificar si las manchas se repiten en varias plantas y en qué estadio está el cultivo."),
    ("Soja", "Mancha marrón", "Septoria glycines", "hongo",
     "Manchas pardas pequeñas e irregulares, empiezan en hojas inferiores.",
     "Inspeccionar hojas bajeras y observar si avanza hacia el tercio superior."),
    ("Maíz", "Roya común del maíz", "Puccinia sorghi", "hongo",
     "Pústulas pardo-rojizas elevadas en ambas caras de la hoja.",
     "Muestrear hojas por encima y por debajo de la espiga; medir porcentaje de área afectada."),
    ("Maíz", "Tizón foliar", "Exserohilum turcicum", "hongo",
     "Lesiones elípticas alargadas, grisáceas a pardas, de varios centímetros.",
     "Revisar hojas medias y superiores; relacionar con períodos de alta humedad."),
    ("Maíz", "Mancha gris de la hoja", "Cercospora zeae-maydis", "hongo",
     "Lesiones rectangulares grisáceas limitadas por las nervaduras.",
     "Inspeccionar lotes con rastrojo de maíz previo; evaluar avance entre estadios."),
    ("Maíz", "Mal de Río Cuarto", "Virus MRCV (vector Delphacodes kuscheli)", "virus",
     "Enanismo, acortamiento de entrenudos y pequeñas enaciones en las nervaduras.",
     "Contar plantas afectadas en tramos de surco; consultar a un técnico y a la estación experimental local."),
    ("Trigo", "Roya de la hoja", "Puccinia triticina", "hongo",
     "Pústulas pequeñas anaranjadas dispersas en la cara superior de la hoja.",
     "Revisar hoja bandera y la inmediata inferior; registrar severidad en varios puntos."),
    ("Trigo", "Roya amarilla o estriada", "Puccinia striiformis", "hongo",
     "Pústulas amarillas dispuestas en estrías siguiendo las nervaduras.",
     "Buscar focos en el lote; es frecuente con clima fresco y húmedo."),
    ("Trigo", "Mancha amarilla", "Pyrenophora tritici-repentis", "hongo",
     "Manchas ovaladas amarillentas con centro pardo.",
     "Revisar lotes con trigo sobre rastrojo de trigo; evaluar hojas superiores."),
    ("Girasol", "Mancha negra del tallo", "Phoma macdonaldii", "hongo",
     "Manchas negras en el tallo y pecíolos, puede haber quiebre del capítulo.",
     "Inspeccionar tallos desde la base; observar el estado del capítulo."),
    ("Girasol", "Roya negra del girasol", "Puccinia helianthi", "hongo",
     "Pústulas pardo-oscuras pulverulentas en hojas.",
     "Muestrear hojas medias e inferiores y registrar porcentaje de superficie afectada."),
    ("Maní", "Viruela temprana del maní", "Passalora arachidicola", "hongo",
     "Manchas circulares pardas con halo amarillo en los foliolos.",
     "Revisar las hojas inferiores y cuantificar defoliación."),
    ("Maní", "Viruela tardía del maní", "Nothopassalora personata", "hongo",
     "Manchas casi negras, más pequeñas, con poco halo, en el envés.",
     "Inspeccionar ambas caras de las hojas y evaluar caída de follaje."),
    ("Tomate", "Tizón tardío", "Phytophthora infestans", "hongo",
     "Manchas verde oscuro aceitosas que se necrosan, con micelio blanquecino en el envés.",
     "Revisar el envés en la mañana, con alta humedad; aislar plantas afectadas."),
    ("Tomate", "Tizón temprano", "Alternaria solani", "hongo",
     "Manchas pardas con anillos concéntricos (aspecto de diana) en hojas viejas.",
     "Revisar hojas bajeras y frutos; observar el avance hacia la parte superior."),
    (None, "Deficiencia de nitrógeno", None, "nutricional",
     "Amarillamiento uniforme que comienza en las hojas más viejas.",
     "Comparar con plantas vecinas, revisar fertilización y considerar análisis de suelo."),
    (None, "Pulgones", "Aphidoidea", "plaga",
     "Colonias de insectos pequeños en brotes y envés, hojas enruladas, melaza.",
     "Contar individuos por planta en varios puntos y observar presencia de enemigos naturales."),
    (None, "Estrés hídrico o golpe de calor", None, "otro",
     "Marchitez, bordes secos y enrollamiento de hojas, sin pústulas ni manchas definidas.",
     "Verificar humedad del suelo, historial de lluvias y temperaturas recientes."),
]

# Cada análisis: (índice de lote, estado, enfermedad (nombre) o None, severidad, confianza, días atrás)
ANALISIS = [
    (0, "enfermo", "Roya asiática de la soja", "media", 0.86, 2),
    (0, "enfermo", "Mancha ojo de rana", "baja", 0.74, 9),
    (0, "sano", None, "ninguna", 0.92, 16),
    (0, "enfermo", "Roya asiática de la soja", "alta", 0.9, 1),
    (1, "enfermo", "Tizón foliar", "media", 0.81, 5),
    (1, "enfermo", "Roya común del maíz", "baja", 0.77, 11),
    (1, "sano", None, "ninguna", 0.95, 20),
    (2, "enfermo", "Viruela tardía del maní", "media", 0.79, 4),
    (2, "dudoso", None, "baja", 0.42, 8),
    (2, "sano", None, "ninguna", 0.9, 14),
    (3, "enfermo", "Roya de la hoja", "media", 0.83, 6),
    (3, "enfermo", "Mancha amarilla", "baja", 0.7, 13),
    (3, "sano", None, "ninguna", 0.93, 25),
    (4, "enfermo", "Deficiencia de nitrógeno", "baja", 0.66, 3),
]

SINTOMAS = {
    "Roya asiática de la soja": ["Pústulas pardo-rojizas en el envés", "Amarillamiento de hojas del tercio medio"],
    "Mancha ojo de rana": ["Manchas circulares con centro grisáceo", "Borde pardo-rojizo definido"],
    "Tizón foliar": ["Lesiones elípticas alargadas grisáceas", "Necrosis desde el ápice de la hoja"],
    "Roya común del maíz": ["Pústulas elevadas pardo-rojizas en ambas caras"],
    "Viruela tardía del maní": ["Manchas casi negras pequeñas en el envés", "Defoliación incipiente"],
    "Roya de la hoja": ["Pústulas anaranjadas dispersas en la cara superior"],
    "Mancha amarilla": ["Manchas ovaladas amarillentas con centro pardo"],
    "Deficiencia de nitrógeno": ["Amarillamiento uniforme en hojas viejas"],
}


def dibujar_hoja(ruta, estado, enfermedad, semilla):
    """Genera una imagen sintética de hoja (verde con manchas según el problema)."""
    rnd = random.Random(semilla)
    W, H = 640, 480
    img = Image.new("RGB", (W, H), (rnd.randint(95, 125), rnd.randint(85, 105), rnd.randint(70, 90)))  # tierra
    d = ImageDraw.Draw(img)
    verde = (rnd.randint(40, 70), rnd.randint(130, 160), rnd.randint(40, 70))
    if enfermedad == "Deficiencia de nitrógeno":
        verde = (150, 170, 60)
    d.ellipse([70, 60, 570, 420], fill=verde)
    d.line([(70, 240), (570, 240)], fill=(30, 100, 35), width=6)      # nervadura central
    for x in range(140, 520, 55):                                       # nervaduras secundarias
        d.line([(x, 240), (x + 40, 100)], fill=(35, 105, 40), width=2)
        d.line([(x, 240), (x + 40, 380)], fill=(35, 105, 40), width=2)
    if estado != "sano":
        n = 12 if estado == "dudoso" else 35
        colores = {"Roya": (190, 95, 30), "Tizón": (150, 130, 90), "Mancha": (120, 80, 40), "Viruela": (50, 35, 25)}
        col = next((c for k, c in colores.items() if enfermedad and k in enfermedad), (200, 190, 70))
        for _ in range(n):
            x, y = rnd.randint(130, 520), rnd.randint(100, 380)
            r = rnd.randint(4, 12)
            d.ellipse([x - r, y - r, x + r, y + r], fill=col)
    img = img.filter(ImageFilter.GaussianBlur(1.1))
    img.save(ruta, "JPEG", quality=85)


def main():
    force = "--force" in sys.argv
    base = dbm.DB()
    try:
        existe = base.uno("SELECT COUNT(*) AS n FROM usuarios")
    except Exception:
        existe = None
    if existe and existe["n"] > 0 and not force:
        print("La base ya tiene datos. Usá `python seed.py --force` para borrar y recrear todo.")
        return
    base.script(open(dbm.esquema_path(), encoding="utf-8").read())
    print("✔ Tablas creadas")

    ids_c = {}
    for nombre, cient, desc in CULTIVOS:
        ids_c[nombre] = base.ejecutar("INSERT INTO cultivos (nombre, nombre_cientifico, descripcion) VALUES (?,?,?)",
                                      (nombre, cient, desc))
    ids_e = {}
    for cult, nombre, cient, agente, sint, rec in ENFERMEDADES:
        ids_e[nombre] = base.ejecutar(
            "INSERT INTO enfermedades (cultivo_id, nombre, nombre_cientifico, agente, sintomas, recomendacion) "
            "VALUES (?,?,?,?,?,?)", (ids_c.get(cult), nombre, cient, agente, sint, rec))
    print(f"✔ {len(CULTIVOS)} cultivos y {len(ENFERMEDADES)} enfermedades")

    usuarios = [("Administrador AgroPlaga", "admin@agroplaga.com", "Admin2026", "admin"),
                ("Técnica Laura Gómez", "tecnico@agroplaga.com", "Tecnico2026", "tecnico"),
                ("Productor Juan Pérez", "productor@agroplaga.com", "Productor2026", "productor"),
                ("Productora María Ruiz", "maria@agroplaga.com", "Productor2026", "productor")]
    uid = {}
    for nombre, email, clave, rol in usuarios:
        uid[email] = base.ejecutar("INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (?,?,?,?)",
                                   (nombre, email, generate_password_hash(clave), rol))
    print("✔ Usuarios de prueba creados")

    juan, maria = uid["productor@agroplaga.com"], uid["maria@agroplaga.com"]
    campos = [
        (juan, "La Esperanza", "Marcos Juárez", "Córdoba", 320, -32.6963, -62.1013),
        (juan, "El Ombú", "Río Cuarto", "Córdoba", 180, -33.1232, -64.3493),
        (maria, "Los Aromos", "Villa María", "Córdoba", 240, -32.4075, -63.2406),
    ]
    id_campos = [base.ejecutar("INSERT INTO campos (usuario_id, nombre, localidad, provincia, superficie_ha, latitud, longitud) "
                               "VALUES (?,?,?,?,?,?,?)", c) for c in campos]
    siembra = lambda dias: (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")
    lotes = [
        (id_campos[0], "Soja", "Lote 1 Norte", 80, siembra(70)),
        (id_campos[0], "Maíz", "Lote 2 Sur", 60, siembra(95)),
        (id_campos[1], "Maní", "Lote A", 45, siembra(80)),
        (id_campos[2], "Trigo", "Lote Este", 110, siembra(120)),
        (id_campos[2], "Girasol", "Lote Oeste", 70, siembra(85)),
    ]
    id_lotes = [base.ejecutar("INSERT INTO lotes (campo_id, cultivo_id, nombre, superficie_ha, fecha_siembra, estado) "
                              "VALUES (?,?,?,?,?, 'activo')", (c, ids_c[cu], n, s, f)) for c, cu, n, s, f in lotes]
    print("✔ Campos y lotes creados")

    os.makedirs(UPLOADS, exist_ok=True)
    rnd = random.Random(7)
    duenos = {0: juan, 1: juan, 2: juan, 3: maria, 4: maria}
    for i, (il, estado, enf, sev, conf, dias) in enumerate(ANALISIS, 1):
        archivo = f"prueba_{i:02d}.jpg"
        dibujar_hoja(os.path.join(UPLOADS, archivo), estado, enf, i)
        campo = campos[0 if il < 2 else 1 if il == 2 else 2]
        lat, lng = campo[5] + rnd.uniform(-0.004, 0.004), campo[6] + rnd.uniform(-0.004, 0.004)
        fecha = (datetime.now() - timedelta(days=dias, hours=rnd.randint(0, 8))).strftime("%Y-%m-%d %H:%M:%S")
        cult = lotes[il][1]
        base.ejecutar(
            "INSERT INTO analisis (lote_id, usuario_id, foto, latitud, longitud, fecha, cultivo_detectado, estado, "
            "enfermedad_id, enfermedad_texto, confianza, severidad, sintomas, causas, recomendaciones, indice_dano, "
            "motor, observaciones, validado) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (id_lotes[il], duenos[il], archivo, lat, lng, fecha, cult, estado,
             ids_e.get(enf), enf, conf, sev,
             json.dumps(SINTOMAS.get(enf, ["Sin síntomas visibles claros"]), ensure_ascii=False),
             json.dumps(["Condiciones de humedad favorables"] if enf else [], ensure_ascii=False),
             json.dumps(["Inspeccionar varios puntos del lote", "Registrar la incidencia", "Repetir el monitoreo en 7 días"], ensure_ascii=False),
             round(rnd.uniform(0, 4), 1) if estado == "sano" else round(rnd.uniform(8, 38), 1),
             "prueba", "Dato de prueba (imagen sintética)", 1 if i % 4 == 0 else 0))
    print(f"✔ {len(ANALISIS)} análisis de prueba con fotos generadas")
    print("\nUsuarios de prueba:")
    for nombre, email, clave, rol in usuarios:
        print(f"  {rol:10s} {email:28s} {clave}")


if __name__ == "__main__":
    main()
