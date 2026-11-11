BEGIN TRANSACTION;
CREATE TABLE analisis (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    lote_id           INTEGER NOT NULL REFERENCES lotes(id) ON DELETE CASCADE,
    usuario_id        INTEGER NOT NULL REFERENCES usuarios(id),
    foto              TEXT NOT NULL,
    latitud           REAL,
    longitud          REAL,
    fecha             TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cultivo_detectado TEXT,
    estado            TEXT NOT NULL DEFAULT 'dudoso' CHECK (estado IN ('sano','enfermo','dudoso','no_planta')),
    enfermedad_id     INTEGER REFERENCES enfermedades(id) ON DELETE SET NULL,
    enfermedad_texto  TEXT,
    confianza         REAL,
    severidad         TEXT CHECK (severidad IN ('ninguna','baja','media','alta')),
    sintomas          TEXT,
    causas            TEXT,
    recomendaciones   TEXT,
    indice_dano       REAL,
    motor             TEXT NOT NULL DEFAULT 'demo',
    observaciones     TEXT,
    validado          INTEGER NOT NULL DEFAULT 0
);
INSERT INTO "analisis" VALUES(1,1,3,'prueba_01.jpg',-3.2697709337881335e+01,-62.1040932066086,'2026-11-07 18:50:49','Soja','enfermo',1,'Roya asiática de la soja',0.86,'media','["Pústulas pardo-rojizas en el envés", "Amarillamiento de hojas del tercio medio"]','["Condiciones de humedad favorables"]','["Inspeccionar varios puntos del lote", "Registrar la incidencia", "Repetir el monitoreo en 7 días"]',10.2,'prueba','Dato de prueba (imagen sintética)',0);
INSERT INTO "analisis" VALUES(2,1,3,'prueba_02.jpg',-3.26960129439655489e+01,-62.1023744886647,'2026-10-31 18:50:49','Soja','enfermo',2,'Mancha ojo de rana',0.74,'baja','["Manchas circulares con centro grisáceo", "Borde pardo-rojizo definido"]','["Condiciones de humedad favorables"]','["Inspeccionar varios puntos del lote", "Registrar la incidencia", "Repetir el monitoreo en 7 días"]',35.3,'prueba','Dato de prueba (imagen sintética)',0);
INSERT INTO "analisis" VALUES(3,1,3,'prueba_03.jpg',-3.26985824145533143e+01,-6.21046124221304864e+01,'2026-10-24 12:50:49','Soja','sano',NULL,NULL,0.92,'ninguna','["Sin síntomas visibles claros"]','[]','["Inspeccionar varios puntos del lote", "Registrar la incidencia", "Repetir el monitoreo en 7 días"]',0.3,'prueba','Dato de prueba (imagen sintética)',0);
INSERT INTO "analisis" VALUES(4,1,3,'prueba_04.jpg',-3.26995742958932495e+01,-6.21019038464868629e+01,'2026-11-08 17:50:49','Soja','enfermo',1,'Roya asiática de la soja',0.9,'alta','["Pústulas pardo-rojizas en el envés", "Amarillamiento de hojas del tercio medio"]','["Condiciones de humedad favorables"]','["Inspeccionar varios puntos del lote", "Registrar la incidencia", "Repetir el monitoreo en 7 días"]',36.4,'prueba','Dato de prueba (imagen sintética)',1);
INSERT INTO "analisis" VALUES(5,2,3,'prueba_05.jpg',-3.2695254992674144e+01,-6.21006360247643201e+01,'2026-11-04 18:50:49','Maíz','enfermo',5,'Tizón foliar',0.81,'media','["Lesiones elípticas alargadas grisáceas", "Necrosis desde el ápice de la hoja"]','["Condiciones de humedad favorables"]','["Inspeccionar varios puntos del lote", "Registrar la incidencia", "Repetir el monitoreo en 7 días"]',25.3,'prueba','Dato de prueba (imagen sintética)',0);
INSERT INTO "analisis" VALUES(6,2,3,'prueba_06.jpg',-32.6971265562028,-6.20974899591552613e+01,'2026-10-29 18:50:49','Maíz','enfermo',4,'Roya común del maíz',0.77,'baja','["Pústulas elevadas pardo-rojizas en ambas caras"]','["Condiciones de humedad favorables"]','["Inspeccionar varios puntos del lote", "Registrar la incidencia", "Repetir el monitoreo en 7 días"]',24.7,'prueba','Dato de prueba (imagen sintética)',0);
INSERT INTO "analisis" VALUES(7,2,3,'prueba_07.jpg',-3.26992346014684684e+01,-6.21019468876514295e+01,'2026-10-20 10:50:49','Maíz','sano',NULL,NULL,0.95,'ninguna','["Sin síntomas visibles claros"]','[]','["Inspeccionar varios puntos del lote", "Registrar la incidencia", "Repetir el monitoreo en 7 días"]',0.5,'prueba','Dato de prueba (imagen sintética)',0);
INSERT INTO "analisis" VALUES(8,3,3,'prueba_08.jpg',-3.31247321454071794e+01,-6.43467709891270374e+01,'2026-11-05 16:50:49','Maní','enfermo',14,'Viruela tardía del maní',0.79,'media','["Manchas casi negras pequeñas en el envés", "Defoliación incipiente"]','["Condiciones de humedad favorables"]','["Inspeccionar varios puntos del lote", "Registrar la incidencia", "Repetir el monitoreo en 7 días"]',11.1,'prueba','Dato de prueba (imagen sintética)',1);
INSERT INTO "analisis" VALUES(9,3,3,'prueba_09.jpg',-3.3122630364868705e+01,-6.43517970317857077e+01,'2026-11-01 17:50:49','Maní','dudoso',NULL,NULL,0.42,'baja','["Sin síntomas visibles claros"]','[]','["Inspeccionar varios puntos del lote", "Registrar la incidencia", "Repetir el monitoreo en 7 días"]',24.4,'prueba','Dato de prueba (imagen sintética)',0);
INSERT INTO "analisis" VALUES(10,3,3,'prueba_10.jpg',-3.31266976882002097e+01,-6.43528231906402652e+01,'2026-10-26 15:50:49','Maní','sano',NULL,NULL,0.9,'ninguna','["Sin síntomas visibles claros"]','[]','["Inspeccionar varios puntos del lote", "Registrar la incidencia", "Repetir el monitoreo en 7 días"]',2.0,'prueba','Dato de prueba (imagen sintética)',0);
INSERT INTO "analisis" VALUES(11,4,4,'prueba_11.jpg',-3.24072462380273549e+01,-6.3238382169800154e+01,'2026-11-03 11:50:49','Trigo','enfermo',8,'Roya de la hoja',0.83,'media','["Pústulas anaranjadas dispersas en la cara superior"]','["Condiciones de humedad favorables"]','["Inspeccionar varios puntos del lote", "Registrar la incidencia", "Repetir el monitoreo en 7 días"]',25.6,'prueba','Dato de prueba (imagen sintética)',0);
INSERT INTO "analisis" VALUES(12,4,4,'prueba_12.jpg',-3.24078745249890332e+01,-6.32422018640250911e+01,'2026-10-27 16:50:49','Trigo','enfermo',10,'Mancha amarilla',0.7,'baja','["Manchas ovaladas amarillentas con centro pardo"]','["Condiciones de humedad favorables"]','["Inspeccionar varios puntos del lote", "Registrar la incidencia", "Repetir el monitoreo en 7 días"]',29.0,'prueba','Dato de prueba (imagen sintética)',1);
INSERT INTO "analisis" VALUES(13,4,4,'prueba_13.jpg',-3.24095472279142242e+01,-6.3240004610317932e+01,'2026-10-15 10:50:49','Trigo','sano',NULL,NULL,0.93,'ninguna','["Sin síntomas visibles claros"]','[]','["Inspeccionar varios puntos del lote", "Registrar la incidencia", "Repetir el monitoreo en 7 días"]',2.0,'prueba','Dato de prueba (imagen sintética)',0);
INSERT INTO "analisis" VALUES(14,5,4,'prueba_14.jpg',-3.24087521944803285e+01,-6.32410093264765791e+01,'2026-11-06 17:50:49','Girasol','enfermo',17,'Deficiencia de nitrógeno',0.66,'baja','["Amarillamiento uniforme en hojas viejas"]','["Condiciones de humedad favorables"]','["Inspeccionar varios puntos del lote", "Registrar la incidencia", "Repetir el monitoreo en 7 días"]',11.5,'prueba','Dato de prueba (imagen sintética)',0);
CREATE TABLE campos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id    INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nombre        TEXT NOT NULL,
    localidad     TEXT,
    provincia     TEXT,
    superficie_ha REAL,
    latitud       REAL,
    longitud      REAL,
    creado        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO "campos" VALUES(1,3,'La Esperanza','Marcos Juárez','Córdoba',320.0,-32.6963,-62.1013,'2026-11-09 18:50:49');
INSERT INTO "campos" VALUES(2,3,'El Ombú','Río Cuarto','Córdoba',180.0,-33.1232,-64.3493,'2026-11-09 18:50:49');
INSERT INTO "campos" VALUES(3,4,'Los Aromos','Villa María','Córdoba',240.0,-32.4075,-63.2406,'2026-11-09 18:50:49');
CREATE TABLE cultivos (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre            TEXT NOT NULL UNIQUE,
    nombre_cientifico TEXT,
    descripcion       TEXT
);
INSERT INTO "cultivos" VALUES(1,'Soja','Glycine max','Oleaginosa de siembra primavero-estival.');
INSERT INTO "cultivos" VALUES(2,'Maíz','Zea mays','Cereal de siembra temprana o tardía.');
INSERT INTO "cultivos" VALUES(3,'Trigo','Triticum aestivum','Cereal de invierno.');
INSERT INTO "cultivos" VALUES(4,'Girasol','Helianthus annuus','Oleaginosa de siembra primaveral.');
INSERT INTO "cultivos" VALUES(5,'Maní','Arachis hypogaea','Leguminosa oleaginosa, típica del centro-sur de Córdoba.');
INSERT INTO "cultivos" VALUES(6,'Tomate','Solanum lycopersicum','Hortaliza de fruto.');
INSERT INTO "cultivos" VALUES(7,'Papa','Solanum tuberosum','Tubérculo.');
INSERT INTO "cultivos" VALUES(8,'Vid','Vitis vinifera','Cultivo perenne.');
CREATE TABLE enfermedades (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    cultivo_id        INTEGER REFERENCES cultivos(id) ON DELETE SET NULL,
    nombre            TEXT NOT NULL,
    nombre_cientifico TEXT,
    agente            TEXT NOT NULL DEFAULT 'hongo' CHECK (agente IN ('hongo','bacteria','virus','plaga','nutricional','otro')),
    sintomas          TEXT,
    recomendacion     TEXT
);
INSERT INTO "enfermedades" VALUES(1,1,'Roya asiática de la soja','Phakopsora pachyrhizi','hongo','Pústulas pequeñas pardo-rojizas en el envés de las hojas, amarillamiento y caída prematura del follaje.','Revisar el envés de hojas del tercio inferior y medio con lupa; muestrear varios puntos del lote; registrar incidencia.');
INSERT INTO "enfermedades" VALUES(2,1,'Mancha ojo de rana','Cercospora sojina','hongo','Manchas circulares con centro grisáceo y borde pardo-rojizo en hojas.','Verificar si las manchas se repiten en varias plantas y en qué estadio está el cultivo.');
INSERT INTO "enfermedades" VALUES(3,1,'Mancha marrón','Septoria glycines','hongo','Manchas pardas pequeñas e irregulares, empiezan en hojas inferiores.','Inspeccionar hojas bajeras y observar si avanza hacia el tercio superior.');
INSERT INTO "enfermedades" VALUES(4,2,'Roya común del maíz','Puccinia sorghi','hongo','Pústulas pardo-rojizas elevadas en ambas caras de la hoja.','Muestrear hojas por encima y por debajo de la espiga; medir porcentaje de área afectada.');
INSERT INTO "enfermedades" VALUES(5,2,'Tizón foliar','Exserohilum turcicum','hongo','Lesiones elípticas alargadas, grisáceas a pardas, de varios centímetros.','Revisar hojas medias y superiores; relacionar con períodos de alta humedad.');
INSERT INTO "enfermedades" VALUES(6,2,'Mancha gris de la hoja','Cercospora zeae-maydis','hongo','Lesiones rectangulares grisáceas limitadas por las nervaduras.','Inspeccionar lotes con rastrojo de maíz previo; evaluar avance entre estadios.');
INSERT INTO "enfermedades" VALUES(7,2,'Mal de Río Cuarto','Virus MRCV (vector Delphacodes kuscheli)','virus','Enanismo, acortamiento de entrenudos y pequeñas enaciones en las nervaduras.','Contar plantas afectadas en tramos de surco; consultar a un técnico y a la estación experimental local.');
INSERT INTO "enfermedades" VALUES(8,3,'Roya de la hoja','Puccinia triticina','hongo','Pústulas pequeñas anaranjadas dispersas en la cara superior de la hoja.','Revisar hoja bandera y la inmediata inferior; registrar severidad en varios puntos.');
INSERT INTO "enfermedades" VALUES(9,3,'Roya amarilla o estriada','Puccinia striiformis','hongo','Pústulas amarillas dispuestas en estrías siguiendo las nervaduras.','Buscar focos en el lote; es frecuente con clima fresco y húmedo.');
INSERT INTO "enfermedades" VALUES(10,3,'Mancha amarilla','Pyrenophora tritici-repentis','hongo','Manchas ovaladas amarillentas con centro pardo.','Revisar lotes con trigo sobre rastrojo de trigo; evaluar hojas superiores.');
INSERT INTO "enfermedades" VALUES(11,4,'Mancha negra del tallo','Phoma macdonaldii','hongo','Manchas negras en el tallo y pecíolos, puede haber quiebre del capítulo.','Inspeccionar tallos desde la base; observar el estado del capítulo.');
INSERT INTO "enfermedades" VALUES(12,4,'Roya negra del girasol','Puccinia helianthi','hongo','Pústulas pardo-oscuras pulverulentas en hojas.','Muestrear hojas medias e inferiores y registrar porcentaje de superficie afectada.');
INSERT INTO "enfermedades" VALUES(13,5,'Viruela temprana del maní','Passalora arachidicola','hongo','Manchas circulares pardas con halo amarillo en los foliolos.','Revisar las hojas inferiores y cuantificar defoliación.');
INSERT INTO "enfermedades" VALUES(14,5,'Viruela tardía del maní','Nothopassalora personata','hongo','Manchas casi negras, más pequeñas, con poco halo, en el envés.','Inspeccionar ambas caras de las hojas y evaluar caída de follaje.');
INSERT INTO "enfermedades" VALUES(15,6,'Tizón tardío','Phytophthora infestans','hongo','Manchas verde oscuro aceitosas que se necrosan, con micelio blanquecino en el envés.','Revisar el envés en la mañana, con alta humedad; aislar plantas afectadas.');
INSERT INTO "enfermedades" VALUES(16,6,'Tizón temprano','Alternaria solani','hongo','Manchas pardas con anillos concéntricos (aspecto de diana) en hojas viejas.','Revisar hojas bajeras y frutos; observar el avance hacia la parte superior.');
INSERT INTO "enfermedades" VALUES(17,NULL,'Deficiencia de nitrógeno',NULL,'nutricional','Amarillamiento uniforme que comienza en las hojas más viejas.','Comparar con plantas vecinas, revisar fertilización y considerar análisis de suelo.');
INSERT INTO "enfermedades" VALUES(18,NULL,'Pulgones','Aphidoidea','plaga','Colonias de insectos pequeños en brotes y envés, hojas enruladas, melaza.','Contar individuos por planta en varios puntos y observar presencia de enemigos naturales.');
INSERT INTO "enfermedades" VALUES(19,NULL,'Estrés hídrico o golpe de calor',NULL,'otro','Marchitez, bordes secos y enrollamiento de hojas, sin pústulas ni manchas definidas.','Verificar humedad del suelo, historial de lluvias y temperaturas recientes.');
CREATE TABLE informes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id    INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    tipo          TEXT NOT NULL CHECK (tipo IN ('cultivo','lote')),
    referencia_id INTEGER NOT NULL,
    titulo        TEXT NOT NULL,
    contenido     TEXT NOT NULL,
    creado        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE lotes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    campo_id      INTEGER NOT NULL REFERENCES campos(id) ON DELETE CASCADE,
    cultivo_id    INTEGER NOT NULL REFERENCES cultivos(id),
    nombre        TEXT NOT NULL,
    superficie_ha REAL,
    fecha_siembra TEXT,
    estado        TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo','cosechado','barbecho'))
);
INSERT INTO "lotes" VALUES(1,1,1,'Lote 1 Norte',80.0,'2026-08-31','activo');
INSERT INTO "lotes" VALUES(2,1,2,'Lote 2 Sur',60.0,'2026-08-06','activo');
INSERT INTO "lotes" VALUES(3,2,5,'Lote A',45.0,'2026-08-21','activo');
INSERT INTO "lotes" VALUES(4,3,3,'Lote Este',110.0,'2026-07-12','activo');
INSERT INTO "lotes" VALUES(5,3,4,'Lote Oeste',70.0,'2026-08-16','activo');
CREATE TABLE usuarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre        TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    rol           TEXT NOT NULL DEFAULT 'productor' CHECK (rol IN ('admin','tecnico','productor')),
    activo        INTEGER NOT NULL DEFAULT 1,
    creado        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO "usuarios" VALUES(1,'Administrador AgroPlaga','admin@agroplaga.com','scrypt:32768:8:1$hARHZYnuqVO4J6BL$ba15e63d8eba1aca77b9609cc8ff7203beaaa4e9241f5addeec184a6eb1681e36640a7d66f85601058da3581fa84de7da5cd5cd2a2c3aa729ba1bb32c27fd4d0','admin',1,'2026-11-09 18:50:48');
INSERT INTO "usuarios" VALUES(2,'Técnica Laura Gómez','tecnico@agroplaga.com','scrypt:32768:8:1$OCrxPBTSd0NeoUpJ$298cd63d1a5bd4ec8345ff8a0f5bf7bca62cbac6707028502c8617e5836cce497b406100060d55b251093f6cc228aebd03282e9b230ccdbcece51df787a9f0d0','tecnico',1,'2026-11-09 18:50:48');
INSERT INTO "usuarios" VALUES(3,'Productor Juan Pérez','productor@agroplaga.com','scrypt:32768:8:1$s3h1xqpzeNanGh9w$2615093d8660e571b8ab2e114d1157ed870907f0418a2d125bd6272c1cd27322f5e0b1fcb6977da4e0411e5ab7d9c9231ca6c4699705fa0fd25fc2d2cf5131fd','productor',1,'2026-11-09 18:50:48');
INSERT INTO "usuarios" VALUES(4,'Productora María Ruiz','maria@agroplaga.com','scrypt:32768:8:1$ZGoIRBh5HzPA6Af8$e90b63961e223951b9d7b3147a2832de7d4d1cfaa2f13621c8879c449c68314cea4b64ee673c22dce38d9820c3a1a351f7dddf72b558fa1a3938e6dd655c32fb','productor',1,'2026-11-09 18:50:49');
CREATE INDEX idx_analisis_lote  ON analisis(lote_id);
CREATE INDEX idx_analisis_fecha ON analisis(fecha);
CREATE INDEX idx_lotes_campo    ON lotes(campo_id);
CREATE INDEX idx_campos_usuario ON campos(usuario_id);
DELETE FROM "sqlite_sequence";
INSERT INTO "sqlite_sequence" VALUES('cultivos',8);
INSERT INTO "sqlite_sequence" VALUES('enfermedades',19);
INSERT INTO "sqlite_sequence" VALUES('usuarios',4);
INSERT INTO "sqlite_sequence" VALUES('campos',3);
INSERT INTO "sqlite_sequence" VALUES('lotes',5);
INSERT INTO "sqlite_sequence" VALUES('analisis',14);
COMMIT;