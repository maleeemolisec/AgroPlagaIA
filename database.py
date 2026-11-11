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


def es_mysql():
    return DATABASE_URL.startswith("mysql")


class DB:
    """Pequeño envoltorio que unifica sqlite3 y pymysql."""

    def __init__(self):
        if es_mysql():
            import pymysql  # se instala solo si se usa MySQL
            u = urlparse(DATABASE_URL)
            self.conn = pymysql.connect(
                host=u.hostname, user=unquote(u.username or ""), password=unquote(u.password or ""),
                database=u.path.lstrip("/"), port=u.port or 3306, charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor, autocommit=True)
            self.mysql = True
        else:
            path = DATABASE_URL.replace("sqlite:///", "", 1)
            self.conn = sqlite3.connect(path)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.mysql = False

    def _sql(self, sql):
        return sql.replace("?", "%s") if self.mysql else sql

    def todos(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(self._sql(sql), params)
        filas = cur.fetchall()
        cur.close()
        return [dict(f) for f in filas]

    def uno(self, sql, params=()):
        filas = self.todos(sql, params)
        return filas[0] if filas else None

    def ejecutar(self, sql, params=()):
        """INSERT / UPDATE / DELETE. Devuelve el id insertado."""
        cur = self.conn.cursor()
        cur.execute(self._sql(sql), params)
        nuevo_id = cur.lastrowid
        cur.close()
        if not self.mysql:
            self.conn.commit()
        return nuevo_id

    def script(self, texto):
        """Ejecuta un script con varias sentencias (para crear el esquema)."""
        if self.mysql:
            for sentencia in [s.strip() for s in texto.split(";") if s.strip()]:
                cur = self.conn.cursor()
                cur.execute(sentencia)
                cur.close()
        else:
            self.conn.executescript(texto)
            self.conn.commit()

    def cerrar(self):
        try:
            self.conn.close()
        except Exception:
            pass


def esquema_path():
    return os.path.join(BASE_DIR, "schema_mysql.sql" if es_mysql() else "schema.sql")
