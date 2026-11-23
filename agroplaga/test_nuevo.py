"""Pruebas de: base vacía, verificación email, SMS local, Facebook y cultivo."""
import io, os, re, sys, tempfile, json
from unittest.mock import patch
tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(tmp, "vacia.db")      # base SIN tablas
os.environ.update({"SMS_MODO_PRUEBA": "1", "FACEBOOK_CLIENT_ID": "id", "FACEBOOK_CLIENT_SECRET": "sec",
                   "REGISTRO_SIN_VERIFICAR": "1", "ADMIN_EMAIL": "admin@prueba.com", "ADMIN_PASSWORD": "Admin12345", "GEMINI_API_KEY": ""})
for k in ("SMTP_USERNAME", "SMTP_PASSWORD"): os.environ.pop(k, None)
os.environ.pop("VERCEL", None)
import app as A, ia, sms
from PIL import Image
ok = fail = 0
def check(n, c):
    global ok, fail; ok += bool(c); fail += (not c); print(("  ✔ " if c else "  ✘ ") + n)
def csrf(c, url):
    return re.search(r'name="_csrf" value="([^"]+)"', c.get(url).get_data(as_text=True)).group(1)
def post(c, url, page=None, **d):
    d["_csrf"] = csrf(c, page or url); return c.post(url, data=d, follow_redirects=True)
def foto():
    b = io.BytesIO(); Image.new("RGB", (300, 200), (40, 150, 40)).save(b, "JPEG"); b.seek(0); return b

print("== Base de datos vacía (el error 503 de Neon)")
c = A.app.test_client()
r = c.get("/login")
check("Con la base sin tablas, /login ya NO da 503", r.status_code == 200)
d = A.dbm.DB()
check("Se crearon las 8 tablas + identidades", not A.dbm._faltan_tablas(d) and d.uno("SELECT COUNT(*) AS n FROM identidades")["n"] == 0)
check("Catálogos cargados (cultivos y enfermedades)", d.uno("SELECT COUNT(*) AS n FROM cultivos")["n"] >= 8 and d.uno("SELECT COUNT(*) AS n FROM enfermedades")["n"] > 10)
check("Admin creado desde ADMIN_EMAIL/ADMIN_PASSWORD", d.uno("SELECT rol FROM usuarios WHERE email='admin@prueba.com'")["rol"] == "admin")
check("Columna telefono agregada", d.uno("SELECT telefono FROM usuarios LIMIT 1") is not None)
pg = A.dbm._esquema_idempotente(open("schema_postgres.sql", encoding="utf-8").read())
check("Esquema Postgres se vuelve idempotente (sin DROP, con IF NOT EXISTS)", "DROP TABLE" not in pg and pg.count("CREATE TABLE IF NOT EXISTS") >= 7 and "CREATE INDEX IF NOT EXISTS" in pg)

print("== Registro y verificación de correo")
A.app.config.update(SMTP_USERNAME="", SMTP_PASSWORD="", SMTP_FROM="")
r = post(c, "/registro", nombre="Ana Prueba", email="ana@x.com", password="Clave1234", password2="Clave1234")
check("Registro sin SMTP no activa ni crea la cuenta",
      "No se pudo enviar el correo" in r.get_data(as_text=True)
      and d.uno("SELECT id FROM usuarios WHERE email='ana@x.com'") is None)

codigos = []
c_email = A.app.test_client()
with patch.object(A, "enviar_codigo_verificacion",
                  side_effect=lambda email, nombre, codigo: codigos.append(codigo)):
    r = post(c_email, "/registro", nombre="Ana Prueba", email="ana@x.com",
             password="Clave1234", password2="Clave1234")
url_verificacion = "/registro/verificar?email=ana%40x.com"
r = post(c_email, url_verificacion, page=url_verificacion, codigo=codigos[0])
check("El correo verificado crea la cuenta e inicia sesión",
      "Correo verificado" in r.get_data(as_text=True)
      and d.uno("SELECT id FROM usuarios WHERE email='ana@x.com'") is not None)
c_login_email = A.app.test_client()
r = post(c_login_email, "/login", email=" ANA@x.com ", password="Clave1234 ")
check("Login por correo funciona (tolera mayúsculas y espacios)", "Hola" in r.get_data(as_text=True))
c2 = A.app.test_client()
check("Correo inexistente → mensaje claro", "No existe una cuenta" in post(c2, "/login", email="no@x.com", password="x").get_data(as_text=True))

print("== Teléfono")
check("Normaliza +54 351 → +549351", sms.normalizar("+54 351 123-4567") == "+5493511234567")
check("Rechaza número sin código de país", sms.normalizar("3511234567") is None)
c3 = A.app.test_client()
r = post(c3, "/telefono/login", telefono="+54 9 351 1111111")
check("Login con teléfono inexistente dirige a crear una cuenta por correo",
      "No existe una cuenta con ese número" in r.get_data(as_text=True))
registro_telefono = c3.get("/telefono/registro", follow_redirects=True)
check("El alta por teléfono exige primero verificar un correo",
      "Primero creá y verificá una cuenta con tu correo" in registro_telefono.get_data(as_text=True)
      and d.uno("SELECT id FROM usuarios WHERE telefono='+5493511111111'") is None)
import io as _io, contextlib
with patch.dict(os.environ, {"SMS_MODO_PRUEBA": "", "SMS_GATEWAY_URL": "http://192.168.1.55:8080",
                            "SMS_GATEWAY_USERNAME": "test", "SMS_GATEWAY_PASSWORD": "test"}):
    with patch.object(sms.requests, "post", return_value=type("Respuesta", (), {"status_code": 201})()) as envio:
        ok_sms, _ = sms.enviar_codigo("+5493511234567")
        codigo_sms = re.search(r"es (\d{6})", envio.call_args.kwargs["json"]["textMessage"]["text"]).group(1)
        verificado_sms, _ = sms.verificar_codigo("+5493511234567", codigo_sms)
        reutilizado_sms, _ = sms.verificar_codigo("+5493511234567", codigo_sms)
        check("SMS Gateway envía por la API local y valida el código de un solo uso",
              ok_sms and verificado_sms and not reutilizado_sms
              and envio.call_args.args[0] == "http://192.168.1.55:8080/message"
              and envio.call_args.kwargs["auth"] == ("test", "test"))
with patch.dict(os.environ, {"VERCEL": "1", "SMS_MODO_PRUEBA": "",
                            "SMS_GATEWAY_URL": "http://192.168.1.55:8080",
                            "SMS_GATEWAY_USERNAME": "test", "SMS_GATEWAY_PASSWORD": "test"}):
    ok_sms, error_sms = sms.enviar_codigo("+5493511234567")
    check("Vercel no intenta acceder a la pasarela privada local",
          not ok_sms and "no se puede usar desde Vercel" in error_sms)

buf = _io.StringIO()
with contextlib.redirect_stdout(buf):
    post(c_email, "/telefono/vincular", telefono="+54 9 351 1111111")
codigo = re.search(r"Código para .*: (\d{6})", buf.getvalue()).group(1)
post(c_email, "/telefono/codigo", codigo=codigo)
u = d.uno("SELECT * FROM usuarios WHERE telefono='+5493511111111'")
check("Vincular teléfono a una cuenta con correo verificado", u and u["email"] == "ana@x.com")
c4 = A.app.test_client(); buf = _io.StringIO()
with contextlib.redirect_stdout(buf):
    post(c4, "/telefono/login", telefono="+54 9 351 1111111")
codigo = re.search(r"Código para .*: (\d{6})", buf.getvalue()).group(1)
r = post(c4, "/telefono/codigo", codigo=codigo)
with c4.session_transaction() as sesion_tel:
    check("Login con teléfono existente (verificado por SMS)",
          u and sesion_tel.get("uid") == u["id"])
# límite de intentos
c7 = A.app.test_client(); buf = _io.StringIO()
with contextlib.redirect_stdout(buf):
    post(c7, "/telefono/login", telefono="+54 9 351 1111111")
for _ in range(6): r = post(c7, "/telefono/codigo", codigo="111111")
check("Más de 5 intentos fallidos bloquea el código", "Demasiados intentos" in r.get_data(as_text=True))

print("== Facebook (simulado)")
class FakeResp:
    def __init__(s, d): s.d = d
    def json(s): return s.d
def fake_fb(datos):
    A.facebook_oauth.authorize_access_token = lambda *a, **k: {"access_token": "t"}
    A.facebook_oauth.get = lambda *a, **k: FakeResp(datos)
cf = A.app.test_client()
r = cf.get("/login/facebook"); check("Redirige a Facebook", r.status_code == 302 and "facebook.com" in r.headers["Location"])
fake_fb({"id": "123456", "name": "Marta Face", "email": "marta@fb.com"})
r = cf.get("/login/facebook/callback", follow_redirects=True)
check("Facebook no crea cuenta sin verificación previa del correo",
      "Primero creá tu cuenta con correo y verificá el código" in r.get_data(as_text=True)
      and d.uno("SELECT id FROM usuarios WHERE email='marta@fb.com'") is None)
cf2 = A.app.test_client(); r = cf2.get("/login/facebook/callback", follow_redirects=True)
check("Facebook no crea cuentas internas sin estar vinculado",
      d.uno("SELECT COUNT(*) AS n FROM usuarios WHERE email='marta@fb.com'")["n"] == 0)
fake_fb({"id": "999", "name": "Sin Correo"})
cf3 = A.app.test_client(); r = cf3.get("/login/facebook/callback", follow_redirects=True)
check("Facebook sin email no crea una cuenta ficticia",
      "Facebook no compartió un correo válido" in r.get_data(as_text=True)
      and d.uno("SELECT id FROM usuarios WHERE nombre='Sin Correo'") is None)
fake_fb({"id": "777", "name": "Ana Prueba", "email": "ana@x.com"})
cf4 = A.app.test_client(); cf4.get("/login/facebook/callback")
check("Facebook con email ya verificado: vincula, no duplica",
      d.uno("SELECT COUNT(*) AS n FROM usuarios WHERE email='ana@x.com'")["n"] == 1
      and d.uno("SELECT usuario_id FROM identidades WHERE proveedor='facebook' AND proveedor_uid='777'")["usuario_id"]
      == d.uno("SELECT id FROM usuarios WHERE email='ana@x.com'")["id"])
def falla(*a, **k): raise A.OAuthError("x")
A.facebook_oauth.authorize_access_token = falla
r = A.app.test_client().get("/login/facebook/callback", follow_redirects=True)
check("Facebook rechazado → mensaje de error", "No se pudo validar el acceso con Facebook" in r.get_data(as_text=True))

print("== IA: cultivo equivocado y ubicación")
A.ubicacion.consultar_zona = lambda *a, **k: None
ca = A.app.test_client(); post(ca, "/login", email="admin@prueba.com", password="Admin12345")
post(ca, "/campos/nuevo", nombre="Campo T", provincia="Córdoba", latitud="-31.4", longitud="-63.0", superficie_ha="50")
cid = d.uno("SELECT id FROM campos WHERE nombre='Campo T'")["id"]
tomate = d.uno("SELECT id FROM cultivos WHERE nombre='Tomate'")["id"]
post(ca, f"/campos/{cid}/lotes/nuevo", nombre="Lote Tomates", cultivo_id=str(tomate), estado="activo")
lid = d.uno("SELECT id FROM lotes WHERE nombre='Lote Tomates'")["id"]
os.environ["GEMINI_API_KEY"] = "k"
ia._gemini = lambda *a, **k: json.dumps({"escena": "campo de trigo maduro", "es_planta": True, "cultivo_identificado": "Trigo",
    "coincide_con_lote": False, "estado": "dudoso", "enfermedad": "Ninguna", "confianza": .8, "severidad": "ninguna",
    "sintomas_observados": [], "causas_posibles": [], "recomendaciones_inspeccion": [], "comentario": ""})
n0 = d.uno("SELECT COUNT(*) AS n FROM analisis")["n"]
tok = csrf(ca, "/analisis/nuevo")
r = ca.post("/analisis/nuevo", data={"_csrf": tok, "lote_id": str(lid), "foto": (foto(), "t.jpg")}, content_type="multipart/form-data", follow_redirects=True)
h = r.get_data(as_text=True)
check("Lote de tomate + foto de trigo → mensaje claro y NO se guarda", "registrado como Tomate" in h and "Trigo" in h and d.uno("SELECT COUNT(*) AS n FROM analisis")["n"] == n0)
ia._gemini = lambda *a, **k: json.dumps({"escena": "hoja de tomate", "es_planta": True, "cultivo_identificado": "Tomate",
    "coincide_con_lote": True, "estado": "sano", "enfermedad": "Ninguna", "confianza": .9, "severidad": "ninguna",
    "sintomas_observados": ["ok"], "causas_posibles": [], "recomendaciones_inspeccion": ["x"], "comentario": "bien"})
r = ca.post("/analisis/nuevo", data={"_csrf": tok, "lote_id": str(lid), "foto": (foto(), "t.jpg"), "latitud": "-24.0", "longitud": "-65.0"}, content_type="multipart/form-data", follow_redirects=True)
check("Foto correcta se analiza y avisa que la ubicación está lejos del campo", "km de la ubicación registrada" in r.get_data(as_text=True))
check("Panel admin de conexión con la IA", ca.get("/admin/ia").status_code == 200)
print(f"\nResultado: {ok} OK, {fail} con error"); sys.exit(1 if fail else 0)
