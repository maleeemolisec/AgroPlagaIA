"""AgroPlaga IA - Detección inteligente de enfermedades en cultivos.

Backend Flask. Estructura:
  1. Configuración y utilidades        4. Campos y lotes (CRUD)
  2. Autenticación y roles             5. Análisis con IA (CRUD)
  3. Dashboard y API                   6. Informes y administración
"""
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import smtplib
import ssl
import threading
import time
import uuid
from datetime import datetime
from email.message import EmailMessage
from functools import wraps

from authlib.integrations.base_client.errors import OAuthError
from authlib.integrations.flask_client import OAuth
from flask import (Flask, abort, flash, g, jsonify, redirect, render_template,
                   request, send_file, send_from_directory, session, url_for)
from joserfc.errors import JoseError
from PIL import Image, UnidentifiedImageError
from requests.exceptions import RequestException
from werkzeug.security import check_password_hash, generate_password_hash


def _cargar_env():
    """Lee un archivo .env (CLAVE=valor) si existe, sin depender de python-dotenv."""
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(ruta):
        for linea in open(ruta, encoding="utf-8"):
            linea = linea.strip()
            if linea and not linea.startswith("#") and "=" in linea:
                k, v = linea.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_cargar_env()   # debe ejecutarse ANTES de importar database e ia (leen variables al importar)

import database as dbm  # noqa: E402
import ia  # noqa: E402

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "static", "uploads")
EXT_PERMITIDAS = {"jpg", "jpeg", "png", "webp"}
VERCEL_RUNTIME = bool(os.environ.get("VERCEL"))
MAX_FOTO_BYTES = 4 * 1024 * 1024 if VERCEL_RUNTIME else 10 * 1024 * 1024

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-cambiar-en-produccion")
app.config["MAX_CONTENT_LENGTH"] = MAX_FOTO_BYTES + (256 * 1024 if VERCEL_RUNTIME else 0)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["GOOGLE_CLIENT_ID"] = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
app.config["GOOGLE_CLIENT_SECRET"] = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
app.config["GOOGLE_REDIRECT_URI"] = os.environ.get("GOOGLE_REDIRECT_URI", "").strip()
app.config["GOOGLE_OAUTH_ENABLED"] = bool(
    app.config["GOOGLE_CLIENT_ID"] and app.config["GOOGLE_CLIENT_SECRET"])
app.config["SMTP_HOST"] = os.environ.get("SMTP_HOST", "smtp.gmail.com").strip()
app.config["SMTP_PORT"] = int(os.environ.get("SMTP_PORT", "587"))
app.config["SMTP_USERNAME"] = os.environ.get("SMTP_USERNAME", "").strip()
app.config["SMTP_PASSWORD"] = os.environ.get("SMTP_PASSWORD", "").strip()
app.config["SMTP_FROM"] = os.environ.get("SMTP_FROM", app.config["SMTP_USERNAME"]).strip()
oauth = OAuth(app)
google_oauth = oauth.register(
    name="google",
    client_id=app.config["GOOGLE_CLIENT_ID"],
    client_secret=app.config["GOOGLE_CLIENT_SECRET"],
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)
if not VERCEL_RUNTIME:
    os.makedirs(UPLOAD_DIR, exist_ok=True)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CODIGO_EMAIL_TTL = 10 * 60
CODIGO_EMAIL_REENVIO = 60
CODIGO_EMAIL_INTENTOS = 5
_verification_schema_ready = False
_verification_schema_lock = threading.Lock()


# ==========================================================================
# 1. Configuración y utilidades
# ==========================================================================
def db():
    if "db" not in g:
        g.db = dbm.DB()
    return g.db


@app.teardown_appcontext
def cerrar_db(_):
    d = g.pop("db", None)
    if d:
        d.cerrar()


@app.template_filter("fecha")
def filtro_fecha(valor, formato="%d/%m/%Y %H:%M"):
    if not valor:
        return "—"
    if isinstance(valor, str):
        for f in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                valor = datetime.strptime(valor[:19], f)
                break
            except ValueError:
                continue
        else:
            return valor
    return valor.strftime(formato)


@app.template_filter("json_lista")
def filtro_json_lista(texto):
    try:
        v = json.loads(texto or "[]")
        return v if isinstance(v, list) else []
    except (ValueError, TypeError):
        return []


@app.context_processor
def inyectar():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return {
        "csrf_token": session["csrf"],
        "ia_real": bool(ia.api_key()),
        "google_habilitado": app.config["GOOGLE_OAUTH_ENABLED"],
    }


@app.before_request
def antes():
    g.user = None
    uid = session.get("uid")
    if uid:
        u = db().uno("SELECT id, nombre, email, rol, activo FROM usuarios WHERE id = ?", (uid,))
        if u and u["activo"]:
            g.user = u
        else:
            session.clear()
    # Protección CSRF para todo POST
    if request.method == "POST":
        esperado = session.get("csrf")
        recibido = request.form.get("_csrf", "")
        if not esperado or not secrets.compare_digest(str(esperado), str(recibido)):
            abort(400, "Token CSRF inválido. Recargá la página e intentá de nuevo.")


@app.after_request
def cabeceras(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    return resp


@app.context_processor
def limites_subida():
    return {"max_foto_mb": MAX_FOTO_BYTES // (1024 * 1024)}


def login_required(f):
    @wraps(f)
    def interior(*a, **k):
        if not g.user:
            flash("Iniciá sesión para continuar.", "warning")
            return redirect(url_for("login", next=request.path))
        return f(*a, **k)
    return interior


def roles_required(*roles):
    def deco(f):
        @wraps(f)
        def interior(*a, **k):
            if g.user["rol"] not in roles:
                abort(403)
            return f(*a, **k)
        return interior
    return deco


def a_float(v, minimo=None, maximo=None):
    try:
        x = float(str(v).replace(",", "."))
    except (TypeError, ValueError):
        return None
    if minimo is not None and x < minimo:
        return None
    if maximo is not None and x > maximo:
        return None
    return x


def alcance(alias_campo="c"):
    """Fragmento SQL para limitar datos: el productor solo ve lo suyo."""
    if g.user["rol"] == "productor":
        return f" AND {alias_campo}.usuario_id = ?", (g.user["id"],)
    return "", ()


def puede_editar_campo(campo):
    return g.user["rol"] == "admin" or campo["usuario_id"] == g.user["id"]


def asegurar_tabla_verificaciones():
    global _verification_schema_ready
    if _verification_schema_ready:
        return
    with _verification_schema_lock:
        if not _verification_schema_ready:
            db().script("""
                CREATE TABLE IF NOT EXISTS email_verifications (
                    email VARCHAR(320) PRIMARY KEY,
                    nombre VARCHAR(120) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    code_hash CHAR(64) NOT NULL,
                    expires_at BIGINT NOT NULL,
                    attempts SMALLINT NOT NULL DEFAULT 0,
                    last_sent_at BIGINT NOT NULL
                )
            """)
            _verification_schema_ready = True


def _hash_codigo(email, codigo):
    mensaje = f"{email}:{codigo}".encode("utf-8")
    return hmac.new(app.config["SECRET_KEY"].encode("utf-8"), mensaje, hashlib.sha256).hexdigest()


def enviar_codigo_verificacion(email, nombre, codigo):
    usuario = app.config["SMTP_USERNAME"]
    clave = app.config["SMTP_PASSWORD"]
    if not usuario or not clave or not app.config["SMTP_FROM"]:
        raise RuntimeError("Falta configurar el envío de correo SMTP.")

    mensaje = EmailMessage()
    mensaje["Subject"] = "Código para verificar tu cuenta de AgroPlaga IA"
    mensaje["From"] = app.config["SMTP_FROM"]
    mensaje["To"] = email
    mensaje.set_content(
        f"Hola {nombre},\n\n"
        f"Tu código de verificación de AgroPlaga IA es: {codigo}\n\n"
        "Vence en 10 minutos. Si no solicitaste crear esta cuenta, puedes ignorar este mensaje."
    )

    if app.config["SMTP_PORT"] == 465:
        with smtplib.SMTP_SSL(
                app.config["SMTP_HOST"], app.config["SMTP_PORT"], timeout=20,
                context=ssl.create_default_context()) as servidor:
            servidor.login(usuario, clave)
            servidor.send_message(mensaje)
    else:
        with smtplib.SMTP(app.config["SMTP_HOST"], app.config["SMTP_PORT"], timeout=20) as servidor:
            servidor.ehlo()
            servidor.starttls(context=ssl.create_default_context())
            servidor.ehlo()
            servidor.login(usuario, clave)
            servidor.send_message(mensaje)


def _emitir_codigo_verificacion(email, nombre=None, password_hash=None, permitir_reenvio=False):
    asegurar_tabla_verificaciones()
    pendiente = db().uno("SELECT * FROM email_verifications WHERE email = ?", (email,))
    ahora = int(time.time())
    if pendiente and ahora - pendiente["last_sent_at"] < CODIGO_EMAIL_REENVIO:
        return False
    if pendiente and not permitir_reenvio:
        return False

    codigo = f"{secrets.randbelow(1_000_000):06d}"
    if pendiente:
        nombre = pendiente["nombre"]
        password_hash = pendiente["password_hash"]
    if not nombre or not password_hash:
        return False
    db().ejecutar("DELETE FROM email_verifications WHERE email = ?", (email,))
    db().ejecutar(
        "INSERT INTO email_verifications "
        "(email, nombre, password_hash, code_hash, expires_at, attempts, last_sent_at) "
        "VALUES (?, ?, ?, ?, ?, 0, ?)",
        (email, nombre, password_hash, _hash_codigo(email, codigo),
         ahora + CODIGO_EMAIL_TTL, ahora),
        devolver_id=False,
    )
    try:
        enviar_codigo_verificacion(email, nombre, codigo)
    except RuntimeError as error:
        app.logger.warning("No se pudo enviar el código de verificación: %s", error)
        db().ejecutar("DELETE FROM email_verifications WHERE email = ?", (email,))
        raise
    except (OSError, smtplib.SMTPException):
        app.logger.exception("No se pudo enviar el código de verificación por correo.")
        db().ejecutar("DELETE FROM email_verifications WHERE email = ?", (email,))
        raise
    return True


def _iniciar_sesion(uid, destino=None):
    session.clear()
    session["uid"] = uid
    session["csrf"] = secrets.token_hex(16)
    return redirect(destino or url_for("dashboard"))


@app.errorhandler(400)
def e400(e):
    return render_template("error.html", codigo=400, mensaje=getattr(e, "description", "Solicitud inválida")), 400


@app.errorhandler(403)
def e403(e):
    return render_template("error.html", codigo=403, mensaje="No tenés permiso para ver esta página."), 403


@app.errorhandler(404)
def e404(e):
    return render_template("error.html", codigo=404, mensaje="No encontramos lo que buscás."), 404


@app.errorhandler(413)
def e413(e):
    return render_template("error.html", codigo=413, mensaje="La foto supera el máximo de 10 MB."), 413


# ==========================================================================
# 2. Autenticación y roles
# ==========================================================================
@app.route("/")
def inicio():
    if g.user:
        return redirect(url_for("dashboard"))
    return render_template("inicio.html")


@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        email = request.form.get("email", "").strip().lower()
        clave = request.form.get("password", "")
        clave2 = request.form.get("password2", "")
        errores = []
        if len(nombre) < 3:
            errores.append("El nombre debe tener al menos 3 caracteres.")
        if not EMAIL_RE.match(email):
            errores.append("El correo electrónico no es válido.")
        if len(clave) < 8 or not re.search(r"\d", clave) or not re.search(r"[A-Za-z]", clave):
            errores.append("La contraseña debe tener 8 o más caracteres, con letras y números.")
        if clave != clave2:
            errores.append("Las contraseñas no coinciden.")
        if not errores and db().uno("SELECT id FROM usuarios WHERE email = ?", (email,)):
            errores.append("Ya existe una cuenta con ese correo.")
        if errores:
            for e in errores:
                flash(e, "danger")
            return render_template("registro.html", nombre=nombre, email=email)
        asegurar_tabla_verificaciones()
        pendiente = db().uno("SELECT * FROM email_verifications WHERE email = ?", (email,))
        if pendiente and int(time.time()) - pendiente["last_sent_at"] < CODIGO_EMAIL_REENVIO:
            flash("Ya enviamos un código a ese correo. Revisá tu bandeja y el correo no deseado.", "info")
            return redirect(url_for("verificar_email", email=email))
        if pendiente:
            db().ejecutar("DELETE FROM email_verifications WHERE email = ?", (email,))
        try:
            enviado = _emitir_codigo_verificacion(
                email, nombre=nombre, password_hash=generate_password_hash(clave))
        except (OSError, smtplib.SMTPException, RuntimeError):
            flash("No se pudo enviar el correo. Revisá la configuración SMTP de Gmail e intentá de nuevo.", "danger")
            return render_template("registro.html", nombre=nombre, email=email)
        if enviado:
            flash("Te enviamos un código de 6 dígitos. Ingresalo para verificar tu correo y activar la cuenta.", "success")
        else:
            flash("Ya enviamos un código a ese correo. Revisá tu bandeja y esperá un minuto antes de pedir otro.", "info")
        return redirect(url_for("verificar_email", email=email))
    return render_template("registro.html", nombre="", email="")


@app.route("/registro/verificar", methods=["GET", "POST"])
def verificar_email():
    asegurar_tabla_verificaciones()
    email = request.values.get("email", "").strip().lower()
    if not EMAIL_RE.match(email):
        flash("El enlace de verificación no es válido. Comenzá el registro nuevamente.", "danger")
        return redirect(url_for("registro"))

    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        pendiente = db().uno("SELECT * FROM email_verifications WHERE email = ?", (email,))
        if not pendiente:
            flash("No hay una verificación pendiente para ese correo. Comenzá el registro nuevamente.", "danger")
            return redirect(url_for("registro"))
        ahora = int(time.time())
        if pendiente["expires_at"] <= ahora:
            db().ejecutar("DELETE FROM email_verifications WHERE email = ?", (email,))
            flash("El código venció. Volvé a completar el registro para recibir otro.", "warning")
            return redirect(url_for("registro"))
        if pendiente["attempts"] >= CODIGO_EMAIL_INTENTOS:
            db().ejecutar("DELETE FROM email_verifications WHERE email = ?", (email,))
            flash("Se agotaron los intentos. Volvé a completar el registro para recibir otro código.", "danger")
            return redirect(url_for("registro"))
        if not re.fullmatch(r"\d{6}", codigo) or not hmac.compare_digest(
                pendiente["code_hash"], _hash_codigo(email, codigo)):
            intentos = pendiente["attempts"] + 1
            db().ejecutar("UPDATE email_verifications SET attempts = ? WHERE email = ?", (intentos, email))
            if intentos >= CODIGO_EMAIL_INTENTOS:
                db().ejecutar("DELETE FROM email_verifications WHERE email = ?", (email,))
                flash("Se agotaron los intentos. Volvé a completar el registro para recibir otro código.", "danger")
                return redirect(url_for("registro"))
            flash(f"El código no es correcto. Te quedan {CODIGO_EMAIL_INTENTOS - intentos} intentos.", "danger")
            return render_template("verificar_email.html", email=email)

        if db().uno("SELECT id FROM usuarios WHERE email = ?", (email,)):
            db().ejecutar("DELETE FROM email_verifications WHERE email = ?", (email,))
            flash("Ese correo ya tiene una cuenta. Iniciá sesión.", "info")
            return redirect(url_for("login"))
        uid = db().ejecutar(
            "INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (?, ?, ?, 'productor')",
            (pendiente["nombre"], email, pendiente["password_hash"]),
        )
        db().ejecutar("DELETE FROM email_verifications WHERE email = ?", (email,))
        respuesta = _iniciar_sesion(uid)
        flash("Correo verificado. Tu cuenta está lista.", "success")
        return respuesta

    if not db().uno("SELECT email FROM email_verifications WHERE email = ?", (email,)):
        flash("No hay una verificación pendiente para ese correo. Comenzá el registro nuevamente.", "warning")
        return redirect(url_for("registro"))
    return render_template("verificar_email.html", email=email)


@app.route("/registro/reenviar", methods=["POST"])
def reenviar_codigo_email():
    email = request.form.get("email", "").strip().lower()
    if not EMAIL_RE.match(email):
        flash("El correo electrónico no es válido.", "danger")
        return redirect(url_for("registro"))
    asegurar_tabla_verificaciones()
    if not db().uno("SELECT email FROM email_verifications WHERE email = ?", (email,)):
        flash("No hay una verificación pendiente para ese correo. Comenzá el registro nuevamente.", "warning")
        return redirect(url_for("registro"))
    try:
        enviado = _emitir_codigo_verificacion(email, permitir_reenvio=True)
    except (OSError, smtplib.SMTPException, RuntimeError):
        flash("No se pudo enviar el correo. Intentá nuevamente más tarde.", "danger")
        return redirect(url_for("verificar_email", email=email))
    if enviado:
        flash("Te enviamos otro código de verificación.", "success")
    else:
        flash("Esperá un minuto antes de pedir otro código.", "warning")
    return redirect(url_for("verificar_email", email=email))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        clave = request.form.get("password", "")
        u = db().uno("SELECT * FROM usuarios WHERE email = ?", (email,))
        if u and u["activo"] and check_password_hash(u["password_hash"], clave):
            destino = request.args.get("next", "")
            if not destino.startswith("/") or destino.startswith("//"):
                destino = url_for("dashboard")
            return _iniciar_sesion(u["id"], destino)
        flash("Correo o contraseña incorrectos.", "danger")
    return render_template("login.html")


@app.route("/login/google")
def login_google():
    if not app.config["GOOGLE_OAUTH_ENABLED"]:
        flash("El inicio con Google todavía no está configurado.", "warning")
        return redirect(url_for("login"))
    destino = request.args.get("next", "")
    if not destino.startswith("/") or destino.startswith("//"):
        destino = url_for("dashboard")
    session["google_next"] = destino
    redirect_uri = app.config["GOOGLE_REDIRECT_URI"] or url_for(
        "callback_google", _external=True)
    return google_oauth.authorize_redirect(redirect_uri=redirect_uri)


@app.route("/login/google/callback")
def callback_google():
    if not app.config["GOOGLE_OAUTH_ENABLED"]:
        flash("El inicio con Google todavía no está configurado.", "warning")
        return redirect(url_for("login"))
    try:
        token = google_oauth.authorize_access_token()
    except (OAuthError, JoseError, RequestException):
        session.pop("google_next", None)
        flash("No se pudo validar el acceso con Google. Intentá de nuevo.", "danger")
        return redirect(url_for("login"))

    userinfo = token.get("userinfo")
    email = userinfo.get("email") if userinfo else None
    if isinstance(email, str):
        email = email.strip().lower()
    if (not userinfo or userinfo.get("email_verified") is not True
            or not isinstance(email, str) or not EMAIL_RE.match(email)):
        session.pop("google_next", None)
        flash("Google no confirmó un correo electrónico válido para esta cuenta.", "danger")
        return redirect(url_for("login"))

    usuario = db().uno("SELECT id, activo FROM usuarios WHERE email = ?", (email,))
    if usuario and not usuario["activo"]:
        session.pop("google_next", None)
        flash("Esta cuenta está desactivada. Contactá al administrador.", "danger")
        return redirect(url_for("login"))

    if usuario:
        uid = usuario["id"]
    else:
        nombre = userinfo.get("name")
        if not isinstance(nombre, str) or not nombre.strip():
            nombre = email.split("@", 1)[0]
        uid = db().ejecutar(
            "INSERT INTO usuarios (nombre, email, password_hash, rol) VALUES (?, ?, ?, 'productor')",
            (nombre.strip(), email, generate_password_hash(secrets.token_urlsafe(32))),
        )

    destino = session.pop("google_next", url_for("dashboard"))
    session.clear()
    session["uid"] = uid
    session["csrf"] = secrets.token_hex(16)
    return redirect(destino)


@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Sesión cerrada.", "info")
    return redirect(url_for("inicio"))


@app.route("/perfil", methods=["GET", "POST"])
@login_required
def perfil():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        actual = request.form.get("actual", "")
        nueva = request.form.get("nueva", "")
        if len(nombre) < 3:
            flash("El nombre debe tener al menos 3 caracteres.", "danger")
            return redirect(url_for("perfil"))
        db().ejecutar("UPDATE usuarios SET nombre = ? WHERE id = ?", (nombre, g.user["id"]))
        if nueva:
            u = db().uno("SELECT password_hash FROM usuarios WHERE id = ?", (g.user["id"],))
            if not check_password_hash(u["password_hash"], actual):
                flash("La contraseña actual no es correcta.", "danger")
                return redirect(url_for("perfil"))
            if len(nueva) < 8 or not re.search(r"\d", nueva) or not re.search(r"[A-Za-z]", nueva):
                flash("La nueva contraseña debe tener 8 o más caracteres, con letras y números.", "danger")
                return redirect(url_for("perfil"))
            db().ejecutar("UPDATE usuarios SET password_hash = ? WHERE id = ?",
                          (generate_password_hash(nueva), g.user["id"]))
        flash("Perfil actualizado.", "success")
        return redirect(url_for("perfil"))
    return render_template("perfil.html")


# ==========================================================================
# 3. Dashboard y API
# ==========================================================================
def consulta_analisis(extra_where="", extra_params=(), limite=None):
    """Consulta base de análisis con sus relaciones, respetando el alcance del usuario."""
    sc, sp = alcance("c")
    sql = ("SELECT a.*, l.nombre AS lote_nombre, c.id AS campo_id, c.nombre AS campo_nombre, "
           "c.usuario_id AS dueno_id, cu.id AS cultivo_id, cu.nombre AS cultivo_nombre, "
           "e.nombre AS enfermedad_nombre, u.nombre AS autor "
           "FROM analisis a JOIN lotes l ON l.id = a.lote_id JOIN campos c ON c.id = l.campo_id "
           "JOIN cultivos cu ON cu.id = l.cultivo_id JOIN usuarios u ON u.id = a.usuario_id "
           "LEFT JOIN enfermedades e ON e.id = a.enfermedad_id WHERE 1=1" + sc + extra_where +
           " ORDER BY a.fecha DESC, a.id DESC")
    if limite:
        sql += f" LIMIT {int(limite)}"
    return db().todos(sql, sp + tuple(extra_params))


def estadisticas(filas):
    est = {"total": len(filas), "sanos": 0, "enfermos": 0, "dudosos": 0, "enfermedades": {}, "por_severidad": {}}
    for f in filas:
        if f["estado"] == "sano":
            est["sanos"] += 1
        elif f["estado"] == "enfermo":
            est["enfermos"] += 1
        else:
            est["dudosos"] += 1
        nombre = f["enfermedad_nombre"] or f["enfermedad_texto"]
        if nombre and f["estado"] == "enfermo":
            est["enfermedades"][nombre] = est["enfermedades"].get(nombre, 0) + 1
        if f["severidad"]:
            est["por_severidad"][f["severidad"]] = est["por_severidad"].get(f["severidad"], 0) + 1
    est["enfermedades"] = dict(sorted(est["enfermedades"].items(), key=lambda x: -x[1]))
    return est


@app.route("/dashboard")
@login_required
def dashboard():
    filas = consulta_analisis()
    sc, sp = alcance("c")
    n_campos = db().uno("SELECT COUNT(*) AS n FROM campos c WHERE 1=1" + sc, sp)["n"]
    n_lotes = db().uno("SELECT COUNT(*) AS n FROM lotes l JOIN campos c ON c.id=l.campo_id WHERE 1=1" + sc, sp)["n"]
    return render_template("dashboard.html", est=estadisticas(filas), recientes=filas[:6],
                           n_campos=n_campos, n_lotes=n_lotes)


@app.route("/api/analisis.geojson")
@login_required
def api_geojson():
    feats = []
    for f in consulta_analisis():
        if f["latitud"] is None or f["longitud"] is None:
            continue
        feats.append({"type": "Feature",
                      "geometry": {"type": "Point", "coordinates": [f["longitud"], f["latitud"]]},
                      "properties": {"id": f["id"], "estado": f["estado"], "severidad": f["severidad"],
                                     "lote": f["lote_nombre"], "campo": f["campo_nombre"],
                                     "cultivo": f["cultivo_nombre"],
                                     "enfermedad": f["enfermedad_nombre"] or f["enfermedad_texto"] or "Sin hallazgos",
                                     "fecha": filtro_fecha(f["fecha"]),
                                     "url": url_for("analisis_ver", aid=f["id"])}})
    return jsonify({"type": "FeatureCollection", "features": feats})


@app.route("/api/campos.geojson")
@login_required
def api_campos():
    sc, sp = alcance("c")
    filas = db().todos("SELECT c.* FROM campos c WHERE c.latitud IS NOT NULL" + sc, sp)
    return jsonify({"type": "FeatureCollection", "features": [
        {"type": "Feature", "geometry": {"type": "Point", "coordinates": [c["longitud"], c["latitud"]]},
         "properties": {"nombre": c["nombre"], "url": url_for("campo_ver", cid=c["id"])}} for c in filas]})


# ==========================================================================
# 4. Campos y lotes (CRUD)
# ==========================================================================
def obtener_campo(cid):
    campo = db().uno("SELECT * FROM campos WHERE id = ?", (cid,))
    if not campo:
        abort(404)
    if g.user["rol"] == "productor" and campo["usuario_id"] != g.user["id"]:
        abort(403)
    return campo


def obtener_lote(lid):
    lote = db().uno("SELECT l.*, c.usuario_id AS dueno_id, c.nombre AS campo_nombre, cu.nombre AS cultivo_nombre "
                    "FROM lotes l JOIN campos c ON c.id = l.campo_id JOIN cultivos cu ON cu.id = l.cultivo_id "
                    "WHERE l.id = ?", (lid,))
    if not lote:
        abort(404)
    if g.user["rol"] == "productor" and lote["dueno_id"] != g.user["id"]:
        abort(403)
    return lote


@app.route("/campos")
@login_required
def campos_lista():
    sc, sp = alcance("c")
    filas = db().todos(
        "SELECT c.*, u.nombre AS dueno, (SELECT COUNT(*) FROM lotes l WHERE l.campo_id = c.id) AS n_lotes "
        "FROM campos c JOIN usuarios u ON u.id = c.usuario_id WHERE 1=1" + sc + " ORDER BY c.nombre", sp)
    return render_template("campos_lista.html", campos=filas)


def leer_campo_form():
    f = request.form
    datos = {"nombre": f.get("nombre", "").strip(), "localidad": f.get("localidad", "").strip(),
             "provincia": f.get("provincia", "").strip(),
             "superficie_ha": a_float(f.get("superficie_ha"), 0, 1000000),
             "latitud": a_float(f.get("latitud"), -90, 90), "longitud": a_float(f.get("longitud"), -180, 180)}
    errores = []
    if len(datos["nombre"]) < 2:
        errores.append("El nombre del campo es obligatorio.")
    if f.get("superficie_ha") and datos["superficie_ha"] is None:
        errores.append("La superficie debe ser un número positivo.")
    if (f.get("latitud") and datos["latitud"] is None) or (f.get("longitud") and datos["longitud"] is None):
        errores.append("La ubicación no es válida.")
    return datos, errores


@app.route("/campos/nuevo", methods=["GET", "POST"])
@login_required
def campo_nuevo():
    if request.method == "POST":
        datos, errores = leer_campo_form()
        if errores:
            for e in errores:
                flash(e, "danger")
            return render_template("campo_form.html", campo=datos, nuevo=True)
        cid = db().ejecutar(
            "INSERT INTO campos (usuario_id, nombre, localidad, provincia, superficie_ha, latitud, longitud) "
            "VALUES (?,?,?,?,?,?,?)",
            (g.user["id"], datos["nombre"], datos["localidad"], datos["provincia"],
             datos["superficie_ha"], datos["latitud"], datos["longitud"]))
        flash("Campo registrado. Ahora agregá sus lotes.", "success")
        return redirect(url_for("campo_ver", cid=cid))
    return render_template("campo_form.html", campo={"provincia": "Córdoba"}, nuevo=True)


@app.route("/campos/<int:cid>")
@login_required
def campo_ver(cid):
    campo = obtener_campo(cid)
    lotes = db().todos(
        "SELECT l.*, cu.nombre AS cultivo_nombre, "
        "(SELECT COUNT(*) FROM analisis a WHERE a.lote_id = l.id) AS n_analisis "
        "FROM lotes l JOIN cultivos cu ON cu.id = l.cultivo_id WHERE l.campo_id = ? ORDER BY l.nombre", (cid,))
    return render_template("campo_ver.html", campo=campo, lotes=lotes, puede_editar=puede_editar_campo(campo))


@app.route("/campos/<int:cid>/editar", methods=["GET", "POST"])
@login_required
def campo_editar(cid):
    campo = obtener_campo(cid)
    if not puede_editar_campo(campo):
        abort(403)
    if request.method == "POST":
        datos, errores = leer_campo_form()
        if errores:
            for e in errores:
                flash(e, "danger")
            datos["id"] = cid
            return render_template("campo_form.html", campo=datos, nuevo=False)
        db().ejecutar("UPDATE campos SET nombre=?, localidad=?, provincia=?, superficie_ha=?, latitud=?, longitud=? "
                      "WHERE id=?", (datos["nombre"], datos["localidad"], datos["provincia"],
                                     datos["superficie_ha"], datos["latitud"], datos["longitud"], cid))
        flash("Campo actualizado.", "success")
        return redirect(url_for("campo_ver", cid=cid))
    return render_template("campo_form.html", campo=campo, nuevo=False)


@app.route("/campos/<int:cid>/eliminar", methods=["POST"])
@login_required
def campo_eliminar(cid):
    campo = obtener_campo(cid)
    if not puede_editar_campo(campo):
        abort(403)
    borrar_fotos("SELECT a.foto FROM analisis a JOIN lotes l ON l.id = a.lote_id WHERE l.campo_id = ?", (cid,))
    db().ejecutar("DELETE FROM campos WHERE id = ?", (cid,))   # ON DELETE CASCADE borra lotes y análisis
    flash("Campo eliminado junto con sus lotes y análisis.", "info")
    return redirect(url_for("campos_lista"))


def cultivos_todos():
    return db().todos("SELECT * FROM cultivos ORDER BY nombre")


def leer_lote_form():
    f = request.form
    datos = {"nombre": f.get("nombre", "").strip(), "cultivo_id": f.get("cultivo_id", type=int),
             "superficie_ha": a_float(f.get("superficie_ha"), 0, 1000000),
             "fecha_siembra": f.get("fecha_siembra") or None, "estado": f.get("estado", "activo")}
    errores = []
    if len(datos["nombre"]) < 1:
        errores.append("El nombre del lote es obligatorio.")
    if not datos["cultivo_id"] or not db().uno("SELECT id FROM cultivos WHERE id = ?", (datos["cultivo_id"],)):
        errores.append("Elegí un cultivo válido.")
    if f.get("superficie_ha") and datos["superficie_ha"] is None:
        errores.append("La superficie debe ser un número positivo.")
    if datos["estado"] not in ("activo", "cosechado", "barbecho"):
        errores.append("Estado inválido.")
    if datos["fecha_siembra"]:
        try:
            datetime.strptime(datos["fecha_siembra"], "%Y-%m-%d")
        except ValueError:
            errores.append("La fecha de siembra no es válida.")
    return datos, errores


@app.route("/campos/<int:cid>/lotes/nuevo", methods=["GET", "POST"])
@login_required
def lote_nuevo(cid):
    campo = obtener_campo(cid)
    if not puede_editar_campo(campo):
        abort(403)
    if request.method == "POST":
        datos, errores = leer_lote_form()
        if errores:
            for e in errores:
                flash(e, "danger")
            return render_template("lote_form.html", campo=campo, lote=datos, cultivos=cultivos_todos(), nuevo=True)
        db().ejecutar("INSERT INTO lotes (campo_id, cultivo_id, nombre, superficie_ha, fecha_siembra, estado) "
                      "VALUES (?,?,?,?,?,?)", (cid, datos["cultivo_id"], datos["nombre"], datos["superficie_ha"],
                                               datos["fecha_siembra"], datos["estado"]))
        flash("Lote registrado.", "success")
        return redirect(url_for("campo_ver", cid=cid))
    return render_template("lote_form.html", campo=campo, lote={"estado": "activo"}, cultivos=cultivos_todos(), nuevo=True)


@app.route("/lotes/<int:lid>/editar", methods=["GET", "POST"])
@login_required
def lote_editar(lid):
    lote = obtener_lote(lid)
    campo = obtener_campo(lote["campo_id"])
    if not puede_editar_campo(campo):
        abort(403)
    if request.method == "POST":
        datos, errores = leer_lote_form()
        if errores:
            for e in errores:
                flash(e, "danger")
            return render_template("lote_form.html", campo=campo, lote=datos, cultivos=cultivos_todos(), nuevo=False)
        db().ejecutar("UPDATE lotes SET cultivo_id=?, nombre=?, superficie_ha=?, fecha_siembra=?, estado=? WHERE id=?",
                      (datos["cultivo_id"], datos["nombre"], datos["superficie_ha"], datos["fecha_siembra"],
                       datos["estado"], lid))
        flash("Lote actualizado.", "success")
        return redirect(url_for("campo_ver", cid=campo["id"]))
    return render_template("lote_form.html", campo=campo, lote=lote, cultivos=cultivos_todos(), nuevo=False)


@app.route("/lotes/<int:lid>/eliminar", methods=["POST"])
@login_required
def lote_eliminar(lid):
    lote = obtener_lote(lid)
    campo = obtener_campo(lote["campo_id"])
    if not puede_editar_campo(campo):
        abort(403)
    borrar_fotos("SELECT foto FROM analisis WHERE lote_id = ?", (lid,))
    db().ejecutar("DELETE FROM lotes WHERE id = ?", (lid,))
    flash("Lote eliminado junto con sus análisis.", "info")
    return redirect(url_for("campo_ver", cid=campo["id"]))


# ==========================================================================
# 5. Análisis con IA (CRUD)
# ==========================================================================
class ErrorAlmacenFotos(Exception):
    pass


class FotoNoEncontrada(Exception):
    pass


def _blob_sdk():
    try:
        from vercel.blob import sync as blob
    except ImportError as error:
        raise ErrorAlmacenFotos("Falta instalar vercel-blob.") from error
    return blob


def _usar_blob():
    return VERCEL_RUNTIME or bool(
        os.environ.get("BLOB_READ_WRITE_TOKEN")
        or os.environ.get("VERCEL_BLOB_READ_WRITE_TOKEN")
    )


def _guardar_blob(ruta, contenido):
    blob = _blob_sdk()
    try:
        return blob.put_blob(ruta, contenido, access="private", content_type="image/jpeg")
    except blob.BlobError as error:
        raise ErrorAlmacenFotos("No se pudo subir la foto a Vercel Blob.") from error


def _leer_blob(ruta):
    blob = _blob_sdk()
    try:
        return blob.get_blob(ruta, access="private")
    except blob.BlobNotFoundError as error:
        raise FotoNoEncontrada from error
    except blob.BlobError as error:
        raise ErrorAlmacenFotos("No se pudo descargar la foto de Vercel Blob.") from error


def _eliminar_blob(ruta):
    blob = _blob_sdk()
    try:
        blob.delete_blob(ruta)
    except blob.BlobError as error:
        raise ErrorAlmacenFotos("No se pudo eliminar la foto de Vercel Blob.") from error


def borrar_fotos(sql, params):
    for f in db().todos(sql, params):
        foto = f["foto"]
        if foto.startswith("blob:"):
            try:
                _eliminar_blob(foto[5:])
            except ErrorAlmacenFotos:
                app.logger.exception("No se pudo eliminar la foto %s", foto)
                raise
        else:
            try:
                os.remove(os.path.join(UPLOAD_DIR, os.path.basename(foto)))
            except FileNotFoundError:
                pass
            except OSError:
                app.logger.warning("No se pudo eliminar la foto local %s", foto, exc_info=True)


def guardar_foto(archivo):
    """Valida y almacena una imagen normalizada; devuelve su clave y los bytes analizados."""
    if not archivo or not archivo.filename:
        return None, "Seleccioná o tomá una fotografía.", None
    ext = archivo.filename.rsplit(".", 1)[-1].lower() if "." in archivo.filename else ""
    if ext not in EXT_PERMITIDAS:
        return None, "Formato no permitido. Usá JPG, PNG o WEBP.", None
    try:
        img = Image.open(archivo.stream)
        img.verify()
        archivo.stream.seek(0)
        img = Image.open(archivo.stream).convert("RGB")
        img.thumbnail((1600, 1600))
        salida = io.BytesIO()
        img.save(salida, "JPEG", quality=88)
    except (UnidentifiedImageError, OSError, ValueError):
        return None, "El archivo no es una imagen válida.", None

    nombre = uuid.uuid4().hex + ".jpg"
    contenido = salida.getvalue()
    try:
        if _usar_blob():
            ruta = f"analisis/{g.user['id']}/{nombre}"
            subida = _guardar_blob(ruta, contenido)
            nombre = "blob:" + subida.pathname
        else:
            with open(os.path.join(UPLOAD_DIR, nombre), "wb") as foto_local:
                foto_local.write(contenido)
    except (ErrorAlmacenFotos, OSError):
        app.logger.exception("No se pudo guardar una foto de análisis.")
        if _usar_blob():
            return None, "No se pudo guardar la foto. Verificá que Vercel Blob esté conectado al proyecto.", None
        return None, "No se pudo guardar la foto en el servidor.", None
    return nombre, None, contenido


def lotes_disponibles():
    sc, sp = alcance("c")
    return db().todos(
        "SELECT l.id, l.nombre, c.nombre AS campo_nombre, cu.nombre AS cultivo_nombre, c.latitud, c.longitud "
        "FROM lotes l JOIN campos c ON c.id = l.campo_id JOIN cultivos cu ON cu.id = l.cultivo_id "
        "WHERE l.estado = 'activo'" + sc + " ORDER BY c.nombre, l.nombre", sp)


def buscar_enfermedad(texto, cultivo_id):
    """Relaciona el texto devuelto por la IA con una fila del catálogo."""
    if not texto:
        return None
    t = texto.lower().strip()
    if t.startswith("otra"):
        return None
    for e in db().todos("SELECT id, nombre, nombre_cientifico FROM enfermedades WHERE cultivo_id = ? OR cultivo_id IS NULL",
                        (cultivo_id,)):
        if e["nombre"].lower() == t or t in e["nombre"].lower() or e["nombre"].lower() in t:
            return e["id"]
    return None


@app.route("/analisis")
@login_required
def analisis_lista():
    where, params = "", []
    q = request.args
    if q.get("lote", type=int):
        where += " AND a.lote_id = ?"; params.append(q.get("lote", type=int))
    if q.get("cultivo", type=int):
        where += " AND cu.id = ?"; params.append(q.get("cultivo", type=int))
    if q.get("estado") in ("sano", "enfermo", "dudoso", "no_planta"):
        where += " AND a.estado = ?"; params.append(q.get("estado"))
    if q.get("desde"):
        where += " AND a.fecha >= ?"; params.append(q.get("desde") + " 00:00:00")
    if q.get("hasta"):
        where += " AND a.fecha <= ?"; params.append(q.get("hasta") + " 23:59:59")
    filas = consulta_analisis(where, params)
    return render_template("analisis_lista.html", analisis=filas, lotes=lotes_todos_visibles(),
                           cultivos=cultivos_todos(), f=q)


def lotes_todos_visibles():
    sc, sp = alcance("c")
    return db().todos("SELECT l.id, l.nombre, c.nombre AS campo_nombre FROM lotes l JOIN campos c ON c.id = l.campo_id "
                      "WHERE 1=1" + sc + " ORDER BY c.nombre, l.nombre", sp)


@app.route("/analisis/nuevo", methods=["GET", "POST"])
@login_required
def analisis_nuevo():
    lotes = lotes_disponibles()
    if request.method == "POST":
        lid = request.form.get("lote_id", type=int)
        lote = next((l for l in lotes if l["id"] == lid), None)
        if not lote:
            flash("Elegí un lote activo válido.", "danger")
            return render_template("analisis_form.html", lotes=lotes, preseleccion=None)
        nombre_foto, error, contenido_foto = guardar_foto(request.files.get("foto"))
        if error:
            flash(error, "danger")
            return render_template("analisis_form.html", lotes=lotes, preseleccion=lid)
        lat = a_float(request.form.get("latitud"), -90, 90)
        lng = a_float(request.form.get("longitud"), -180, 180)
        if lat is None or lng is None:
            lat, lng = lote["latitud"], lote["longitud"]            # por defecto: ubicación del campo
        # Catálogo de enfermedades del cultivo para guiar a la IA
        lote_db = obtener_lote(lid)
        catalogo = [e["nombre"] for e in db().todos(
            "SELECT nombre FROM enfermedades WHERE cultivo_id = ? OR cultivo_id IS NULL ORDER BY nombre",
            (lote_db["cultivo_id"],))]
        r = ia.analizar_foto(contenido_foto, lote["cultivo_nombre"], catalogo)
        enf_id = buscar_enfermedad(r["enfermedad_texto"], lote_db["cultivo_id"])
        aid = db().ejecutar(
            "INSERT INTO analisis (lote_id, usuario_id, foto, latitud, longitud, fecha, cultivo_detectado, estado, "
            "enfermedad_id, enfermedad_texto, confianza, severidad, sintomas, causas, recomendaciones, "
            "indice_dano, motor, observaciones) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (lid, g.user["id"], nombre_foto, lat, lng, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
             r["cultivo_detectado"], r["estado"], enf_id, r["enfermedad_texto"], r["confianza"], r["severidad"],
             json.dumps(r["sintomas"], ensure_ascii=False), json.dumps(r["causas"], ensure_ascii=False),
             json.dumps(r["recomendaciones"], ensure_ascii=False), r["indice_dano"], r["motor"],
             (request.form.get("observaciones", "").strip() or None)))
        if r["motor"] == "demo":
            flash("Análisis guardado en MODO DEMO (sin IA externa). Configurá GEMINI_API_KEY para el análisis completo.", "warning")
        elif not r.get("coincide_con_lote", True):
            flash(f"Atención: la IA identificó «{r['cultivo_detectado']}», que no coincide con el cultivo del lote "
                  f"({lote['cultivo_nombre']}).", "warning")
        else:
            flash("Análisis completado.", "success")
        return redirect(url_for("analisis_ver", aid=aid))
    return render_template("analisis_form.html", lotes=lotes, preseleccion=request.args.get("lote", type=int))


def obtener_analisis(aid):
    filas = consulta_analisis(" AND a.id = ?", (aid,))
    if not filas:
        abort(404)
    return filas[0]


@app.route("/analisis/<int:aid>/foto")
@login_required
def analisis_foto(aid):
    a = obtener_analisis(aid)
    if a["foto"].startswith("blob:"):
        try:
            foto = _leer_blob(a["foto"][5:])
        except FotoNoEncontrada:
            abort(404)
        except ErrorAlmacenFotos:
            app.logger.exception("No se pudo leer la foto del análisis %s.", aid)
            abort(503, "No se pudo cargar la foto. Intentá nuevamente más tarde.")
        respuesta = send_file(io.BytesIO(foto.body), mimetype="image/jpeg", max_age=0)
    else:
        respuesta = send_from_directory(
            UPLOAD_DIR, os.path.basename(a["foto"]), mimetype="image/jpeg", max_age=0)
    respuesta.headers["Cache-Control"] = "private, no-store"
    return respuesta


@app.route("/analisis/<int:aid>")
@login_required
def analisis_ver(aid):
    a = obtener_analisis(aid)
    enf = db().uno("SELECT * FROM enfermedades WHERE id = ?", (a["enfermedad_id"],)) if a["enfermedad_id"] else None
    return render_template("analisis_ver.html", a=a, enf=enf, aviso=ia.ADVERTENCIA,
                           puede_borrar=g.user["rol"] == "admin" or a["dueno_id"] == g.user["id"] or a["usuario_id"] == g.user["id"])


@app.route("/analisis/<int:aid>/editar", methods=["GET", "POST"])
@login_required
def analisis_editar(aid):
    a = obtener_analisis(aid)
    if request.method == "POST":
        estado = request.form.get("estado")
        if estado not in ("sano", "enfermo", "dudoso", "no_planta"):
            abort(400)
        enf_id = request.form.get("enfermedad_id", type=int) or None
        if enf_id and not db().uno("SELECT id FROM enfermedades WHERE id = ?", (enf_id,)):
            abort(400)
        db().ejecutar("UPDATE analisis SET estado=?, enfermedad_id=?, observaciones=?, validado=? WHERE id=?",
                      (estado, enf_id, request.form.get("observaciones", "").strip() or None,
                       1 if request.form.get("validado") else 0, aid))
        flash("Análisis actualizado.", "success")
        return redirect(url_for("analisis_ver", aid=aid))
    enfs = db().todos("SELECT id, nombre FROM enfermedades WHERE cultivo_id = ? OR cultivo_id IS NULL ORDER BY nombre",
                      (a["cultivo_id"],))
    return render_template("analisis_editar.html", a=a, enfermedades=enfs)


@app.route("/analisis/<int:aid>/eliminar", methods=["POST"])
@login_required
def analisis_eliminar(aid):
    a = obtener_analisis(aid)
    if not (g.user["rol"] == "admin" or a["dueno_id"] == g.user["id"] or a["usuario_id"] == g.user["id"]):
        abort(403)
    borrar_fotos("SELECT foto FROM analisis WHERE id = ?", (aid,))
    db().ejecutar("DELETE FROM analisis WHERE id = ?", (aid,))
    flash("Análisis eliminado.", "info")
    return redirect(url_for("analisis_lista"))


# ==========================================================================
# 6. Informes y administración
# ==========================================================================
def datos_informe(tipo, ref):
    if tipo == "lote":
        lote = obtener_lote(ref)
        titulo = f"Informe del lote «{lote['nombre']}» ({lote['campo_nombre']} · {lote['cultivo_nombre']})"
        filas = consulta_analisis(" AND a.lote_id = ?", (ref,))
    elif tipo == "cultivo":
        cu = db().uno("SELECT * FROM cultivos WHERE id = ?", (ref,))
        if not cu:
            abort(404)
        titulo = f"Informe del cultivo «{cu['nombre']}»"
        filas = consulta_analisis(" AND cu.id = ?", (ref,))
    else:
        abort(404)
    return titulo, filas


@app.route("/informes")
@login_required
def informes_lista():
    guardados = db().todos("SELECT * FROM informes WHERE usuario_id = ? ORDER BY creado DESC", (g.user["id"],))
    return render_template("informes_lista.html", lotes=lotes_todos_visibles(), cultivos=cultivos_todos(),
                           guardados=guardados)


@app.route("/informes/ver")
@login_required
def informe_ver():
    tipo = request.args.get("tipo", "")
    ref = request.args.get("id", type=int)
    if not ref:
        abort(404)
    titulo, filas = datos_informe(tipo, ref)
    return render_template("informe_ver.html", titulo=titulo, tipo=tipo, ref=ref, filas=filas,
                           est=estadisticas(filas), texto=None, guardado=None)


@app.route("/informes/generar", methods=["POST"])
@login_required
def informe_generar():
    """Genera el texto del informe con IA y lo guarda en la base de datos."""
    tipo = request.form.get("tipo", "")
    ref = request.form.get("id", type=int)
    titulo, filas = datos_informe(tipo, ref)
    est = estadisticas(filas)
    est["detalle_lotes"] = {}
    for f in filas:
        d = est["detalle_lotes"].setdefault(f["lote_nombre"], {"analisis": 0, "enfermos": 0})
        d["analisis"] += 1
        d["enfermos"] += 1 if f["estado"] == "enfermo" else 0
    texto = ia.redactar_informe(titulo, est)
    iid = db().ejecutar("INSERT INTO informes (usuario_id, tipo, referencia_id, titulo, contenido, creado) "
                        "VALUES (?,?,?,?,?,?)", (g.user["id"], tipo, ref, titulo, texto,
                                                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    flash("Informe generado y guardado.", "success")
    return redirect(url_for("informe_guardado", iid=iid))


@app.route("/informes/<int:iid>")
@login_required
def informe_guardado(iid):
    inf = db().uno("SELECT * FROM informes WHERE id = ?", (iid,))
    if not inf or (inf["usuario_id"] != g.user["id"] and g.user["rol"] != "admin"):
        abort(404)
    titulo, filas = datos_informe(inf["tipo"], inf["referencia_id"])
    return render_template("informe_ver.html", titulo=inf["titulo"], tipo=inf["tipo"], ref=inf["referencia_id"],
                           filas=filas, est=estadisticas(filas), texto=inf["contenido"], guardado=inf)


@app.route("/informes/<int:iid>/eliminar", methods=["POST"])
@login_required
def informe_eliminar(iid):
    inf = db().uno("SELECT * FROM informes WHERE id = ?", (iid,))
    if not inf or (inf["usuario_id"] != g.user["id"] and g.user["rol"] != "admin"):
        abort(404)
    db().ejecutar("DELETE FROM informes WHERE id = ?", (iid,))
    flash("Informe eliminado.", "info")
    return redirect(url_for("informes_lista"))


# ---- Administración: usuarios -------------------------------------------
@app.route("/admin/usuarios")
@login_required
@roles_required("admin")
def admin_usuarios():
    return render_template("admin_usuarios.html", usuarios=db().todos("SELECT * FROM usuarios ORDER BY nombre"))


@app.route("/admin/usuarios/<int:uid>/editar", methods=["POST"])
@login_required
@roles_required("admin")
def admin_usuario_editar(uid):
    rol = request.form.get("rol")
    if rol not in ("admin", "tecnico", "productor"):
        abort(400)
    activo = 1 if request.form.get("activo") else 0
    if uid == g.user["id"] and (rol != "admin" or not activo):
        flash("No podés quitarte el rol de administrador ni desactivarte a vos mismo.", "danger")
        return redirect(url_for("admin_usuarios"))
    db().ejecutar("UPDATE usuarios SET rol = ?, activo = ? WHERE id = ?", (rol, activo, uid))
    flash("Usuario actualizado.", "success")
    return redirect(url_for("admin_usuarios"))


@app.route("/admin/usuarios/<int:uid>/eliminar", methods=["POST"])
@login_required
@roles_required("admin")
def admin_usuario_eliminar(uid):
    if uid == g.user["id"]:
        flash("No podés eliminar tu propia cuenta.", "danger")
        return redirect(url_for("admin_usuarios"))
    if db().uno("SELECT id FROM analisis WHERE usuario_id = ? LIMIT 1", (uid,)):
        flash("El usuario tiene análisis registrados; desactivalo en lugar de eliminarlo.", "warning")
        return redirect(url_for("admin_usuarios"))
    db().ejecutar("DELETE FROM usuarios WHERE id = ?", (uid,))
    flash("Usuario eliminado.", "info")
    return redirect(url_for("admin_usuarios"))


# ---- Administración: catálogos ------------------------------------------
@app.route("/admin/cultivos", methods=["GET", "POST"])
@login_required
@roles_required("admin")
def admin_cultivos():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        if len(nombre) < 2:
            flash("El nombre es obligatorio.", "danger")
        elif db().uno("SELECT id FROM cultivos WHERE nombre = ?", (nombre,)):
            flash("Ese cultivo ya existe.", "danger")
        else:
            db().ejecutar("INSERT INTO cultivos (nombre, nombre_cientifico, descripcion) VALUES (?,?,?)",
                          (nombre, request.form.get("nombre_cientifico", "").strip() or None,
                           request.form.get("descripcion", "").strip() or None))
            flash("Cultivo agregado.", "success")
        return redirect(url_for("admin_cultivos"))
    return render_template("admin_cultivos.html", cultivos=db().todos(
        "SELECT cu.*, (SELECT COUNT(*) FROM lotes l WHERE l.cultivo_id = cu.id) AS n_lotes FROM cultivos cu ORDER BY nombre"))


@app.route("/admin/cultivos/<int:cid>/editar", methods=["POST"])
@login_required
@roles_required("admin")
def admin_cultivo_editar(cid):
    nombre = request.form.get("nombre", "").strip()
    if len(nombre) < 2:
        flash("El nombre es obligatorio.", "danger")
    else:
        db().ejecutar("UPDATE cultivos SET nombre=?, nombre_cientifico=?, descripcion=? WHERE id=?",
                      (nombre, request.form.get("nombre_cientifico", "").strip() or None,
                       request.form.get("descripcion", "").strip() or None, cid))
        flash("Cultivo actualizado.", "success")
    return redirect(url_for("admin_cultivos"))


@app.route("/admin/cultivos/<int:cid>/eliminar", methods=["POST"])
@login_required
@roles_required("admin")
def admin_cultivo_eliminar(cid):
    if db().uno("SELECT id FROM lotes WHERE cultivo_id = ? LIMIT 1", (cid,)):
        flash("No se puede eliminar: hay lotes que usan este cultivo.", "danger")
    else:
        db().ejecutar("DELETE FROM cultivos WHERE id = ?", (cid,))
        flash("Cultivo eliminado.", "info")
    return redirect(url_for("admin_cultivos"))


@app.route("/enfermedades")
@login_required
def enfermedades_lista():
    filas = db().todos("SELECT e.*, cu.nombre AS cultivo_nombre FROM enfermedades e "
                       "LEFT JOIN cultivos cu ON cu.id = e.cultivo_id ORDER BY cu.nombre, e.nombre")
    return render_template("enfermedades_lista.html", enfermedades=filas, cultivos=cultivos_todos())


def leer_enfermedad_form():
    f = request.form
    agente = f.get("agente", "hongo")
    if agente not in ("hongo", "bacteria", "virus", "plaga", "nutricional", "otro"):
        agente = "otro"
    return {"cultivo_id": f.get("cultivo_id", type=int) or None, "nombre": f.get("nombre", "").strip(),
            "nombre_cientifico": f.get("nombre_cientifico", "").strip() or None, "agente": agente,
            "sintomas": f.get("sintomas", "").strip() or None, "recomendacion": f.get("recomendacion", "").strip() or None}


@app.route("/admin/enfermedades/nueva", methods=["POST"])
@login_required
@roles_required("admin")
def admin_enfermedad_nueva():
    d = leer_enfermedad_form()
    if len(d["nombre"]) < 2:
        flash("El nombre es obligatorio.", "danger")
    else:
        db().ejecutar("INSERT INTO enfermedades (cultivo_id, nombre, nombre_cientifico, agente, sintomas, recomendacion) "
                      "VALUES (?,?,?,?,?,?)", (d["cultivo_id"], d["nombre"], d["nombre_cientifico"], d["agente"],
                                               d["sintomas"], d["recomendacion"]))
        flash("Enfermedad agregada al catálogo.", "success")
    return redirect(url_for("enfermedades_lista"))


@app.route("/admin/enfermedades/<int:eid>/editar", methods=["POST"])
@login_required
@roles_required("admin")
def admin_enfermedad_editar(eid):
    d = leer_enfermedad_form()
    if len(d["nombre"]) < 2:
        flash("El nombre es obligatorio.", "danger")
    else:
        db().ejecutar("UPDATE enfermedades SET cultivo_id=?, nombre=?, nombre_cientifico=?, agente=?, sintomas=?, "
                      "recomendacion=? WHERE id=?", (d["cultivo_id"], d["nombre"], d["nombre_cientifico"], d["agente"],
                                                     d["sintomas"], d["recomendacion"], eid))
        flash("Enfermedad actualizada.", "success")
    return redirect(url_for("enfermedades_lista"))


@app.route("/admin/enfermedades/<int:eid>/eliminar", methods=["POST"])
@login_required
@roles_required("admin")
def admin_enfermedad_eliminar(eid):
    db().ejecutar("DELETE FROM enfermedades WHERE id = ?", (eid,))
    flash("Enfermedad eliminada del catálogo.", "info")
    return redirect(url_for("enfermedades_lista"))


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
