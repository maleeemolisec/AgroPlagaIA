-- AgroPlaga IA - Esquema MySQL 5.7+ / 8 (InnoDB, utf8mb4)
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS informes;
DROP TABLE IF EXISTS analisis;
DROP TABLE IF EXISTS lotes;
DROP TABLE IF EXISTS campos;
DROP TABLE IF EXISTS email_verifications;
DROP TABLE IF EXISTS enfermedades;
DROP TABLE IF EXISTS cultivos;
DROP TABLE IF EXISTS usuarios;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE usuarios (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    nombre        VARCHAR(120) NOT NULL,
    email         VARCHAR(160) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    rol           ENUM('admin','tecnico','productor') NOT NULL DEFAULT 'productor',
    activo        TINYINT(1) NOT NULL DEFAULT 1,
    creado        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE email_verifications (
    email         VARCHAR(320) PRIMARY KEY,
    nombre        VARCHAR(120) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    code_hash     CHAR(64) NOT NULL,
    expires_at    BIGINT NOT NULL,
    attempts      SMALLINT NOT NULL DEFAULT 0,
    last_sent_at  BIGINT NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE cultivos (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    nombre            VARCHAR(80) NOT NULL UNIQUE,
    nombre_cientifico VARCHAR(120),
    descripcion       TEXT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE enfermedades (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    cultivo_id        INT NULL,
    nombre            VARCHAR(160) NOT NULL,
    nombre_cientifico VARCHAR(160),
    agente            ENUM('hongo','bacteria','virus','plaga','nutricional','otro') NOT NULL DEFAULT 'hongo',
    sintomas          TEXT,
    recomendacion     TEXT,
    FOREIGN KEY (cultivo_id) REFERENCES cultivos(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE campos (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id    INT NOT NULL,
    nombre        VARCHAR(120) NOT NULL,
    localidad     VARCHAR(120),
    provincia     VARCHAR(80),
    superficie_ha DOUBLE,
    latitud       DOUBLE,
    longitud      DOUBLE,
    creado        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE lotes (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    campo_id      INT NOT NULL,
    cultivo_id    INT NOT NULL,
    nombre        VARCHAR(120) NOT NULL,
    superficie_ha DOUBLE,
    fecha_siembra DATE NULL,
    estado        ENUM('activo','cosechado','barbecho') NOT NULL DEFAULT 'activo',
    FOREIGN KEY (campo_id) REFERENCES campos(id) ON DELETE CASCADE,
    FOREIGN KEY (cultivo_id) REFERENCES cultivos(id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE analisis (
    id                INT AUTO_INCREMENT PRIMARY KEY,
    lote_id           INT NOT NULL,
    usuario_id        INT NOT NULL,
    foto              VARCHAR(255) NOT NULL,
    latitud           DOUBLE,
    longitud          DOUBLE,
    fecha             DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    cultivo_detectado VARCHAR(120),
    estado            ENUM('sano','enfermo','dudoso','no_planta') NOT NULL DEFAULT 'dudoso',
    enfermedad_id     INT NULL,
    enfermedad_texto  VARCHAR(200),
    confianza         DOUBLE,
    severidad         ENUM('ninguna','baja','media','alta'),
    sintomas          TEXT,
    causas            TEXT,
    recomendaciones   TEXT,
    indice_dano       DOUBLE,
    motor             VARCHAR(30) NOT NULL DEFAULT 'demo',
    observaciones     TEXT,
    validado          TINYINT(1) NOT NULL DEFAULT 0,
    FOREIGN KEY (lote_id) REFERENCES lotes(id) ON DELETE CASCADE,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id),
    FOREIGN KEY (enfermedad_id) REFERENCES enfermedades(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE informes (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    usuario_id    INT NOT NULL,
    tipo          ENUM('cultivo','lote') NOT NULL,
    referencia_id INT NOT NULL,
    titulo        VARCHAR(200) NOT NULL,
    contenido     MEDIUMTEXT NOT NULL,
    creado        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE INDEX idx_analisis_lote  ON analisis(lote_id);
CREATE INDEX idx_analisis_fecha ON analisis(fecha);
CREATE INDEX idx_lotes_campo    ON lotes(campo_id);
CREATE INDEX idx_campos_usuario ON campos(usuario_id);
