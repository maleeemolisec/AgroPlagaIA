-- AgroPlaga IA - Esquema PostgreSQL
DROP TABLE IF EXISTS informes;
DROP TABLE IF EXISTS analisis;
DROP TABLE IF EXISTS lotes;
DROP TABLE IF EXISTS campos;
DROP TABLE IF EXISTS enfermedades;
DROP TABLE IF EXISTS cultivos;
DROP TABLE IF EXISTS usuarios;

CREATE TABLE usuarios (
    id            SERIAL PRIMARY KEY,
    nombre        VARCHAR(120) NOT NULL,
    email         VARCHAR(160) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    rol           VARCHAR(12) NOT NULL DEFAULT 'productor'
                  CHECK (rol IN ('admin','tecnico','productor')),
    activo        SMALLINT NOT NULL DEFAULT 1,
    creado        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cultivos (
    id                SERIAL PRIMARY KEY,
    nombre            VARCHAR(80) NOT NULL UNIQUE,
    nombre_cientifico VARCHAR(120),
    descripcion       TEXT
);

CREATE TABLE enfermedades (
    id                SERIAL PRIMARY KEY,
    cultivo_id        INTEGER REFERENCES cultivos(id) ON DELETE SET NULL,
    nombre            VARCHAR(160) NOT NULL,
    nombre_cientifico VARCHAR(160),
    agente            VARCHAR(16) NOT NULL DEFAULT 'hongo'
                      CHECK (agente IN ('hongo','bacteria','virus','plaga','nutricional','otro')),
    sintomas          TEXT,
    recomendacion     TEXT
);

CREATE TABLE campos (
    id            SERIAL PRIMARY KEY,
    usuario_id    INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nombre        VARCHAR(120) NOT NULL,
    localidad     VARCHAR(120),
    provincia     VARCHAR(80),
    superficie_ha DOUBLE PRECISION,
    latitud       DOUBLE PRECISION,
    longitud      DOUBLE PRECISION,
    creado        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE lotes (
    id            SERIAL PRIMARY KEY,
    campo_id      INTEGER NOT NULL REFERENCES campos(id) ON DELETE CASCADE,
    cultivo_id    INTEGER NOT NULL REFERENCES cultivos(id),
    nombre        VARCHAR(120) NOT NULL,
    superficie_ha DOUBLE PRECISION,
    fecha_siembra DATE,
    estado        VARCHAR(10) NOT NULL DEFAULT 'activo'
                  CHECK (estado IN ('activo','cosechado','barbecho'))
);

CREATE TABLE analisis (
    id                SERIAL PRIMARY KEY,
    lote_id           INTEGER NOT NULL REFERENCES lotes(id) ON DELETE CASCADE,
    usuario_id        INTEGER NOT NULL REFERENCES usuarios(id),
    foto              VARCHAR(255) NOT NULL,
    latitud           DOUBLE PRECISION,
    longitud          DOUBLE PRECISION,
    fecha             TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cultivo_detectado VARCHAR(120),
    estado            VARCHAR(12) NOT NULL DEFAULT 'dudoso'
                      CHECK (estado IN ('sano','enfermo','dudoso','no_planta')),
    enfermedad_id     INTEGER REFERENCES enfermedades(id) ON DELETE SET NULL,
    enfermedad_texto  VARCHAR(200),
    confianza         DOUBLE PRECISION,
    severidad         VARCHAR(10)
                      CHECK (severidad IN ('ninguna','baja','media','alta')),
    sintomas          TEXT,
    causas            TEXT,
    recomendaciones   TEXT,
    indice_dano       DOUBLE PRECISION,
    motor             VARCHAR(30) NOT NULL DEFAULT 'demo',
    observaciones     TEXT,
    validado          SMALLINT NOT NULL DEFAULT 0
);

CREATE TABLE informes (
    id            SERIAL PRIMARY KEY,
    usuario_id    INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    tipo          VARCHAR(10) NOT NULL CHECK (tipo IN ('cultivo','lote')),
    referencia_id INTEGER NOT NULL,
    titulo        VARCHAR(200) NOT NULL,
    contenido     TEXT NOT NULL,
    creado        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_analisis_lote  ON analisis(lote_id);
CREATE INDEX idx_analisis_fecha ON analisis(fecha);
CREATE INDEX idx_lotes_campo    ON lotes(campo_id);
CREATE INDEX idx_campos_usuario ON campos(usuario_id);
