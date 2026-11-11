"""Pruebas automáticas de AgroPlaga IA (python test_app.py). Usa una base temporal."""
import io, os, re, sys, tempfile, json
from unittest.mock import patch
tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tmp, "test.db")
os.environ["GEMINI_API_KEY"] = ""
sys.argv = ["seed.py", "--force"]
import seed; seed.main()
import app as A, ia
from PIL import Image

ok = fail = 0
def check(nombre, cond):
    global ok, fail
    ok += cond; fail += (not cond)
    print(("  ✔ " if cond else "  ✘ ") + nombre)

def csrf(c, url="/login"):
    h = c.get(url).get_data(as_text=True)
    return re.search(r'name="_csrf" value="([^"]+)"', h).group(1)

def login(c, email, clave):
    t = csrf(c)
    return c.post("/login", data={"_csrf": t, "email": email, "password": clave}, follow_redirects=True)

def foto(color=(40, 150, 40), manchas=True):
    im = Image.new("RGB", (400, 300), color)
    if manchas:
        for x in range(50, 350, 40): im.paste((200, 120, 30), (x, 120, x + 20, 140))
    b = io.BytesIO(); im.save(b, "JPEG"); b.seek(0); return b

print("== Acceso y roles")
c = A.app.test_client()
A.app.config["GOOGLE_OAUTH_ENABLED"] = False
database_url_anterior = A.dbm.DATABASE_URL
A.dbm.DATABASE_URL = "postgresql://test:test@localhost/test?sslmode=require"
check("PostgreSQL selecciona el esquema correcto",
      A.dbm.es_postgres() and A.dbm.esquema_path().endswith("schema_postgres.sql"))
pg_db = A.dbm.DB.__new__(A.dbm.DB)
pg_db.postgres, pg_db.mysql = True, False

class CursorPostgresPrueba:
    def execute(self, sql, params):
        self.sql, self.params = sql, params
    def fetchone(self):
        return {"id": 27}
    def close(self):
        pass

class ConexionPostgresPrueba:
    def cursor(self):
        self.ultimo_cursor = CursorPostgresPrueba()
        return self.ultimo_cursor

pg_db.conn = ConexionPostgresPrueba()
id_prueba = pg_db.ejecutar("INSERT INTO usuarios (nombre) VALUES (?)", ("Prueba",))
check("PostgreSQL adapta parámetros y devuelve el ID insertado",
      id_prueba == 27 and pg_db.conn.ultimo_cursor.sql.endswith("VALUES (%s) RETURNING id"))
A.dbm.DATABASE_URL = database_url_anterior
url_anterior, argumentos_anteriores = A.dbm.DATABASE_URL, sys.argv[:]
A.dbm.DATABASE_URL = "sqlite:///" + os.path.join(tmp, "production-init.db")
sys.argv = ["seed.py", "--production"]
with patch("builtins.input", side_effect=["Administrador Prueba", "admin-prueba@test.com"]), \
        patch("seed.getpass", side_effect=["AdminSeguro2026", "AdminSeguro2026"]):
    seed.main()
base_produccion = A.dbm.DB()
usuario_admin = base_produccion.uno("SELECT rol FROM usuarios WHERE email = ?", ("admin-prueba@test.com",))
cuentas_demo = base_produccion.uno("SELECT COUNT(*) AS n FROM usuarios")["n"]
cliente_produccion = A.app.test_client()
token_registro = csrf(cliente_produccion, "/registro")
respuesta_registro = cliente_produccion.post("/registro", data={
    "_csrf": token_registro, "nombre": "Cuenta Nueva", "email": "nueva@test.com",
    "password": "NuevaClave123", "password2": "NuevaClave123",
}, follow_redirects=True)
cuenta_creada = base_produccion.uno("SELECT id FROM usuarios WHERE email = ?", ("nueva@test.com",))
base_produccion.cerrar()
A.dbm.DATABASE_URL, sys.argv = url_anterior, argumentos_anteriores
check("Inicialización de producción crea catálogos y admin sin cuentas demo",
      usuario_admin is not None and usuario_admin["rol"] == "admin" and cuentas_demo == 1)
check("Registro funciona con la base inicializada para producción",
      cuenta_creada is not None and "Cuenta creada" in respuesta_registro.get_data(as_text=True))
check("Panel sin sesión redirige a login", c.get("/dashboard").status_code == 302)
login_html = c.get("/login").data
check("Formulario de login ofrece Google", b"Continuar con Google" in login_html)
check("Login permite mostrar la contraseña", b'data-password-toggle="login-password"' in login_html)
check("Registro permite mostrar ambas contraseñas",
      c.get("/registro").data.count(b'class="password-toggle"') == 2)
rg = c.get("/login/google", follow_redirects=True)
check("Google sin configurar muestra aviso", "todavía no está configurado" in rg.get_data(as_text=True))
A.app.config["GOOGLE_OAUTH_ENABLED"] = True
cg = A.app.test_client()
with patch.object(A.google_oauth, "authorize_access_token", return_value={
    "userinfo": {"email": "google@test.com", "email_verified": True, "name": "Cuenta Google"}
}):
    cg.get("/login/google/callback")
google_user = A.dbm.DB().uno("SELECT id, rol FROM usuarios WHERE email = ?", ("google@test.com",))
check("Google crea usuario productor con correo verificado",
      google_user is not None and google_user["rol"] == "productor")
with cg.session_transaction() as s:
    check("Google inicia sesión", s.get("uid") == (google_user["id"] if google_user else None))
cu = A.app.test_client()
with patch.object(A.google_oauth, "authorize_access_token", return_value={
    "userinfo": {"email": "no-verificado@test.com", "email_verified": False, "name": "No Verificado"}
}):
    cu.get("/login/google/callback")
check("Google rechaza correo sin verificar",
      A.dbm.DB().uno("SELECT id FROM usuarios WHERE email = ?", ("no-verificado@test.com",)) is None)
A.app.config["GOOGLE_OAUTH_ENABLED"] = False
check("POST sin CSRF rechazado (400)", c.post("/login", data={"email": "x", "password": "y"}).status_code == 400)
r = login(c, "productor@agroplaga.com", "mala")
check("Login con clave incorrecta falla", "incorrectos" in r.get_data(as_text=True))
r = login(c, "productor@agroplaga.com", "Productor2026")
check("Login productor correcto", "Hola, Productor" in r.get_data(as_text=True))
check("Perfil permite mostrar ambas contraseñas",
      c.get("/perfil").data.count(b'class="password-toggle"') == 2)
check("Productor NO accede a /admin/usuarios (403)", c.get("/admin/usuarios").status_code == 403)
h = c.get("/campos").get_data(as_text=True)
check("Productor ve sus campos", "La Esperanza" in h and "Los Aromos" not in h)
check("Productor no ve campo ajeno (403)", c.get("/campos/3").status_code == 403)
check("Productor no ve análisis ajeno (404/403)", c.get("/analisis/11").status_code in (403, 404))

print("== Registro")
c2 = A.app.test_client(); t = csrf(c2, "/registro")
r = c2.post("/registro", data={"_csrf": t, "nombre": "Ana", "email": "mala", "password": "123", "password2": "x"})
check("Registro con datos inválidos muestra errores", "no es válido" in r.get_data(as_text=True))
r = c2.post("/registro", data={"_csrf": t, "nombre": "Ana Nueva", "email": "ana@test.com", "password": "Clave1234", "password2": "Clave1234"}, follow_redirects=True)
check("Registro válido crea cuenta", "Cuenta creada" in r.get_data(as_text=True))
check("Nuevo usuario queda como productor", A.dbm.DB().uno("SELECT rol FROM usuarios WHERE email='ana@test.com'")["rol"] == "productor")

print("== CRUD campos y lotes")
t = csrf(c, "/campos/nuevo")
r = c.post("/campos/nuevo", data={"_csrf": t, "nombre": "", "latitud": "999"}, follow_redirects=True)
check("Campo inválido rechazado", "obligatorio" in r.get_data(as_text=True))
r = c.post("/campos/nuevo", data={"_csrf": t, "nombre": "Campo Test", "localidad": "Villa María", "provincia": "Córdoba", "superficie_ha": "50", "latitud": "-31.4", "longitud": "-63.0"}, follow_redirects=True)
check("Alta de campo", "Campo registrado" in r.get_data(as_text=True))
cid = A.dbm.DB().uno("SELECT id FROM campos WHERE nombre='Campo Test'")["id"]
r = c.post(f"/campos/{cid}/lotes/nuevo", data={"_csrf": t, "nombre": "Lote T", "cultivo_id": "1", "superficie_ha": "10", "fecha_siembra": "2026-10-01", "estado": "activo"}, follow_redirects=True)
check("Alta de lote", "Lote registrado" in r.get_data(as_text=True))
lid = A.dbm.DB().uno("SELECT id FROM lotes WHERE nombre='Lote T'")["id"]
r = c.post(f"/campos/{cid}/editar", data={"_csrf": t, "nombre": "Campo Test 2", "superficie_ha": "60"}, follow_redirects=True)
check("Modificación de campo", "Campo Test 2" in r.get_data(as_text=True))

print("== Análisis con IA (modo demo, sin API key)")
t = csrf(c, "/analisis/nuevo")
r = c.post("/analisis/nuevo", data={"_csrf": t, "lote_id": str(lid), "foto": (foto(), "hoja.jpg")}, content_type="multipart/form-data", follow_redirects=True)
h = r.get_data(as_text=True)
check("Análisis guardado en modo demo con aviso", "MODO DEMO" in h or "modo demo" in h)
aid = A.dbm.DB().uno("SELECT MAX(id) AS m FROM analisis")["m"]
check("Detalle muestra índice de daño", "Índice de daño visual" in c.get(f"/analisis/{aid}").get_data(as_text=True))
r = c.post("/analisis/nuevo", data={"_csrf": t, "lote_id": str(lid), "foto": (io.BytesIO(b"no soy imagen"), "x.jpg")}, content_type="multipart/form-data", follow_redirects=True)
check("Archivo falso con extensión .jpg rechazado", "no es una imagen válida" in r.get_data(as_text=True))
r = c.post("/analisis/nuevo", data={"_csrf": t, "lote_id": str(lid), "foto": (io.BytesIO(b"abc"), "x.exe")}, content_type="multipart/form-data", follow_redirects=True)
check("Extensión .exe rechazada", "Formato no permitido" in r.get_data(as_text=True))
r = c.post(f"/analisis/{aid}/editar", data={"_csrf": t, "estado": "enfermo", "enfermedad_id": "1", "observaciones": "Confirmado", "validado": "on"}, follow_redirects=True)
check("Corrección / validación manual", "Validado por una persona" in r.get_data(as_text=True))
r = c.get("/analisis?estado=enfermo&cultivo=1")
check("Filtros de listado funcionan", r.status_code == 200)
g = c.get("/api/analisis.geojson").get_json()
check("GeoJSON de análisis válido", g["type"] == "FeatureCollection" and len(g["features"]) > 0)

print("== IA con Gemini simulada (respuesta JSON del modelo)")
os.environ["GEMINI_API_KEY"] = "clave-falsa"
ia._gemini = lambda partes, json_mode=True, timeout=60: json.dumps({
    "es_planta": True, "cultivo_identificado": "Soja", "coincide_con_lote": True, "estado": "enfermo",
    "enfermedad": "Roya asiática de la soja", "confianza": 0.87, "severidad": "media",
    "sintomas_observados": ["Pústulas pardas en el envés"], "causas_posibles": ["Humedad alta"],
    "recomendaciones_inspeccion": ["Revisar envés", "Muestrear 5 puntos", "Repetir en 7 días"], "comentario": "ok"})
t = csrf(c, "/analisis/nuevo")
c.post("/analisis/nuevo", data={"_csrf": t, "lote_id": str(lid), "foto": (foto(), "h.jpg")}, content_type="multipart/form-data")
row = A.dbm.DB().uno("SELECT * FROM analisis ORDER BY id DESC LIMIT 1")
check("Resultado de Gemini guardado (motor=gemini)", row["motor"] == "gemini" and row["estado"] == "enfermo")
check("Enfermedad vinculada al catálogo", row["enfermedad_id"] is not None)
ia._gemini = lambda *a, **k: (_ for _ in ()).throw(KeyError("falla"))
c.post("/analisis/nuevo", data={"_csrf": t, "lote_id": str(lid), "foto": (foto(), "h2.jpg")}, content_type="multipart/form-data")
check("Si la IA falla, cae a modo demo sin romper", A.dbm.DB().uno("SELECT motor FROM analisis ORDER BY id DESC LIMIT 1")["motor"] == "demo")
os.environ["GEMINI_API_KEY"] = ""

print("== Informes")
check("Informe por lote", "Análisis" in c.get(f"/informes/ver?tipo=lote&id={lid}").get_data(as_text=True))
check("Informe por cultivo", c.get("/informes/ver?tipo=cultivo&id=1").status_code == 200)
t = csrf(c, "/informes")
r = c.post("/informes/generar", data={"_csrf": t, "tipo": "lote", "id": str(lid)}, follow_redirects=True)
check("Informe generado y guardado", "Informe generado" in r.get_data(as_text=True))

print("== Administración")
ca = A.app.test_client(); login(ca, "admin@agroplaga.com", "Admin2026")
check("Admin ve usuarios", "Administración de usuarios" in ca.get("/admin/usuarios").get_data(as_text=True))
check("Admin ve todos los campos", "Los Aromos" in ca.get("/campos").get_data(as_text=True))
t = csrf(ca, "/admin/cultivos")
ca.post("/admin/cultivos", data={"_csrf": t, "nombre": "Cebada"})
check("Alta de cultivo (admin)", A.dbm.DB().uno("SELECT id FROM cultivos WHERE nombre='Cebada'") is not None)
ca.post("/admin/enfermedades/nueva", data={"_csrf": t, "nombre": "Prueba E", "agente": "hongo"})
check("Alta de enfermedad (admin)", A.dbm.DB().uno("SELECT id FROM enfermedades WHERE nombre='Prueba E'") is not None)
uid = A.dbm.DB().uno("SELECT id FROM usuarios WHERE email='ana@test.com'")["id"]
ca.post(f"/admin/usuarios/{uid}/editar", data={"_csrf": t, "rol": "tecnico", "activo": "on"})
check("Admin cambia rol de usuario", A.dbm.DB().uno("SELECT rol FROM usuarios WHERE id=?", (uid,))["rol"] == "tecnico")
cte = A.app.test_client(); login(cte, "tecnico@agroplaga.com", "Tecnico2026")
check("Técnico ve campos de todos", "Los Aromos" in cte.get("/campos").get_data(as_text=True))
check("Técnico NO accede a administración", cte.get("/admin/cultivos").status_code == 403)
t = csrf(c, "/campos")
c.post(f"/lotes/{lid}/eliminar", data={"_csrf": t})
check("Baja de lote (con análisis en cascada)", A.dbm.DB().uno("SELECT id FROM lotes WHERE id=?", (lid,)) is None
      and A.dbm.DB().uno("SELECT COUNT(*) AS n FROM analisis WHERE lote_id=?", (lid,))["n"] == 0)
c.post(f"/campos/{cid}/eliminar", data={"_csrf": t})
check("Baja de campo", A.dbm.DB().uno("SELECT id FROM campos WHERE id=?", (cid,)) is None)

print("== Seguridad")
r = c.get("/login?next=//evil.com"); t = csrf(c)
r = c.post("/login?next=//evil.com", data={"_csrf": t, "email": "productor@agroplaga.com", "password": "Productor2026"})
check("Open-redirect bloqueado", "evil.com" not in r.headers.get("Location", ""))
check("XSS escapado en nombre de campo", "&lt;script&gt;" in (lambda: (c.post("/campos/nuevo", data={"_csrf": csrf(c, "/campos/nuevo"), "nombre": "<script>alert(1)</script>"}), c.get("/campos").get_data(as_text=True))[1])())

print(f"\nResultado: {ok} OK, {fail} con error")
sys.exit(1 if fail else 0)
