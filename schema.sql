-- AgroPlaga IA - Esquema SQLite
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS informes;
DROP TABLE IF EXISTS analisis;
DROP TABLE IF EXISTS lotes;
DROP TABLE IF EXISTS campos;
DROP TABLE IF EXISTS email_verifications;
DROP TABLE IF EXISTS enfermedades;
DROP TABLE IF EXISTS cultivos;
DROP TABLE IF EXISTS usuarios;

CREATE TABLE usuarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre        TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    rol           TEXT NOT NULL DEFAULT 'productor' CHECK (rol IN ('admin','tecnico','productor')),
    activo        INTEGER NOT NULL DEFAULT 1,
    creado        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE email_verifications (
    email         VARCHAR(320) PRIMARY KEY,
    nombre        VARCHAR(120) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    code_hash     CHAR(64) NOT NULL,
    expires_at    INTEGER NOT NULL,
    attempts      INTEGER NOT NULL DEFAULT 0,
    last_sent_at  INTEGER NOT NULL
);

CREATE TABLE cultivos (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre            TEXT NOT NULL UNIQUE,
    nombre_cientifico TEXT,
    descripcion       TEXT
);

CREATE TABLE enfermedades (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    cultivo_id        INTEGER REFERENCES cultivos(id) ON DELETE SET NULL,
    nombre            TEXT NOT NULL,
    nombre_cientifico TEXT,
    agente            TEXT NOT NULL DEFAULT 'hongo' CHECK (agente IN ('hongo','bacteria','virus','plaga','nutricional','otro')),
    sintomas          TEXT,
    recomendacion     TEXT
);

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

CREATE TABLE lotes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    campo_id      INTEGER NOT NULL REFERENCES campos(id) ON DELETE CASCADE,
    cultivo_id    INTEGER NOT NULL REFERENCES cultivos(id),
    nombre        TEXT NOT NULL,
    superficie_ha REAL,
    fecha_siembra TEXT,
    estado        TEXT NOT NULL DEFAULT 'activo' CHECK (estado IN ('activo','cosechado','barbecho'))
);

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

CREATE TABLE informes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id    INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    tipo          TEXT NOT NULL CHECK (tipo IN ('cultivo','lote')),
    referencia_id INTEGER NOT NULL,
    titulo        TEXT NOT NULL,
    contenido     TEXT NOT NULL,
    creado        TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_analisis_lote  ON analisis(lote_id);
CREATE INDEX idx_analisis_fecha ON analisis(fecha);
CREATE INDEX idx_lotes_campo    ON lotes(campo_id);
CREATE INDEX idx_campos_usuario ON campos(usuario_id);
