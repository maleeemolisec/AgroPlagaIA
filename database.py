"""Capa de acceso a datos de AgroPlaga IA.

Soporta SQLite (desarrollo / entrega simple) y MySQL (producción, p. ej. PythonAnywhere).
Se elige con la variable de entorno DATABASE_URL:

    sqlite:///agroplaga.db
    mysql://usuario:clave@host/nombre_bd

Todas las consultas usan parámetros (?), nunca se concatenan datos del usuario
en el SQL, lo que previene inyección SQL.
"""
import os
import re
import sqlite3
from urllib.parse import urlparse, unquote

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "agroplaga.db"))


class DatabaseConfigurationError(RuntimeError):
    """Configuración de base de datos incompatible con el entorno de ejecución."""


class DatabaseConnectionError(RuntimeError):
    """No se pudo abrir una conexión con la base de datos configurada."""


class DatabaseOperationError(RuntimeError):
    """Falló una consulta o una operación sobre la base de datos."""


def es_mysql():
    return DATABASE_URL.startswith("mysql")


def es_postgres():
    return DATABASE_URL.startswith(("postgres://", "postgresql://"))


class DB:
    """Pequeño envoltorio que unifica SQLite, MySQL y PostgreSQL."""

    def __init__(self):
        if os.environ.get("VERCEL"):
            if not DATABASE_URL.strip():
                raise DatabaseConfigurationError(
                    "Vercel necesita DATABASE_URL para usar una base persistente.")
            if not es_postgres():
                raise DatabaseConfigurationError(
                    "Vercel necesita que DATABASE_URL sea una conexión PostgreSQL de Neon.")
        if es_postgres():
            import psycopg
            from psycopg.rows import dict_row
            try:
                self.conn = psycopg.connect(DATABASE_URL, row_factory=dict_row, autocommit=True)
            except psycopg.Error as error:
                raise DatabaseConnectionError(
                    "No se pudo conectar con PostgreSQL. Revisá DATABASE_URL y la contraseña del rol.") from error
            self.postgres = True
            self.mysql = False
            self._db_error_types = (psycopg.Error,)
        elif es_mysql():
            import pymysql  # se instala solo si se usa MySQL
            u = urlparse(DATABASE_URL)
            try:
                self.conn = pymysql.connect(
                    host=u.hostname, user=unquote(u.username or ""), password=unquote(u.password or ""),
                    database=u.path.lstrip("/"), port=u.port or 3306, charset="utf8mb4",
                    cursorclass=pymysql.cursors.DictCursor, autocommit=True)
            except pymysql.MySQLError as error:
                raise DatabaseConnectionError(
                    "No se pudo conectar con MySQL. Revisá DATABASE_URL.") from error
            self.mysql = True
            self.postgres = False
            self._db_error_types = (pymysql.MySQLError,)
        else:
            path = DATABASE_URL.replace("sqlite:///", "", 1)
            try:
                self.conn = sqlite3.connect(path)
            except sqlite3.Error as error:
                raise DatabaseConnectionError(
                    "No se pudo abrir la base SQLite configurada.") from error
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.mysql = False
            self.postgres = False
            self._db_error_types = (sqlite3.Error,)

    def _sql(self, sql):
        return sql.replace("?", "%s") if self.mysql or self.postgres else sql

    def todos(self, sql, params=()):
        cur = self.conn.cursor()
        try:
            cur.execute(self._sql(sql), params)
            filas = cur.fetchall()
        except self._db_error_types as error:
            raise DatabaseOperationError("Falló una consulta a la base de datos.") from error
        finally:
            cur.close()
        return [dict(f) for f in filas]

    def uno(self, sql, params=()):
        filas = self.todos(sql, params)
        return filas[0] if filas else None

    def ejecutar(self, sql, params=(), devolver_id=True):
        """Ejecuta INSERT / UPDATE / DELETE; puede omitir la recuperación del id."""
        cur = self.conn.cursor()
        try:
            es_insert = sql.lstrip().upper().startswith("INSERT")
            if self.postgres and es_insert and devolver_id and "RETURNING" not in sql.upper():
                sql = sql.rstrip().rstrip(";") + " RETURNING id"
            cur.execute(self._sql(sql), params)
            if self.postgres:
                nuevo_id = cur.fetchone()["id"] if es_insert and devolver_id else None
            else:
                nuevo_id = cur.lastrowid if es_insert and devolver_id else None
        except self._db_error_types as error:
            raise DatabaseOperationError("Falló una operación en la base de datos.") from error
        finally:
            cur.close()
        if not self.mysql and not self.postgres:
            self.conn.commit()
        return nuevo_id

    def script(self, texto):
        """Ejecuta un script con varias sentencias (para crear el esquema)."""
        try:
            if self.mysql or self.postgres:
                for sentencia in [s.strip() for s in texto.split(";") if s.strip()]:
                    cur = self.conn.cursor()
                    try:
                        cur.execute(sentencia)
                    finally:
                        cur.close()
            else:
                self.conn.executescript(texto)
                self.conn.commit()
        except self._db_error_types as error:
            raise DatabaseOperationError("Falló una operación de esquema en la base de datos.") from error

    def cerrar(self):
        try:
            self.conn.close()
        except Exception:
            pass


def esquema_path():
    if es_postgres():
        nombre = "schema_postgres.sql"
    else:
        nombre = "schema_mysql.sql" if es_mysql() else "schema.sql"
    return os.path.join(BASE_DIR, nombre)
