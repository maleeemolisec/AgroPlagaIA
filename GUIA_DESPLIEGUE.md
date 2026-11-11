# Guía de despliegue en PythonAnywhere (gratis, con subdominio público)

Resultado: `https://TU_USUARIO.pythonanywhere.com`. El plan gratuito permite la API de Gemini
(`*.googleapis.com` está en su lista de sitios permitidos). Un dominio propio (ej. `agroplaga.com`) requiere plan pago.

1. Crear cuenta en pythonanywhere.com (plan "Beginner", gratis).
2. **Files** → subí `agroplaga.zip` a `/home/TU_USUARIO/` y en una consola **Bash**:
   ```bash
   unzip agroplaga.zip && cd agroplaga
   python3 -m venv venv && source venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env && nano .env      # completá SECRET_KEY y GEMINI_API_KEY
   python seed.py --force                 # crea la base con datos de prueba
   ```
3. Pestaña **Web** → *Add a new web app* → *Manual configuration* → misma versión de Python que usaste.
4. En **Virtualenv** poné: `/home/TU_USUARIO/agroplaga/venv`
5. En **Source code**: `/home/TU_USUARIO/agroplaga`
6. Abrí el **archivo WSGI** (link en la pestaña Web), borrá todo y pegá:
   ```python
   import sys
   sys.path.insert(0, "/home/TU_USUARIO/agroplaga")
   from wsgi import application
   ```
7. En **Static files** agregá: URL `/static/` → Directorio `/home/TU_USUARIO/agroplaga/static`
8. Botón verde **Reload**. Entrá a tu subdominio.
9. Cambiá las contraseñas de los usuarios de prueba desde la app (o eliminalos).
10. En el plan gratis hay que apretar "Run until 3 months from today" en la pestaña Web periódicamente para que no se apague.

## Opcional: usar MySQL
Pestaña **Databases** → creá una base MySQL, y en `.env`:
`DATABASE_URL=mysql://TU_USUARIO:CLAVE@TU_USUARIO.mysql.pythonanywhere-services.com/TU_USUARIO$agroplaga`
y corré `python seed.py --force`. (El soporte MySQL está implementado pero probado solo con SQLite: probalo antes de la entrega.)

## Probar en tu PC
```bash
python -m venv venv && venv\Scripts\activate    # Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                          # completá GEMINI_API_KEY y credenciales de Google
python seed.py && python app.py                 # http://127.0.0.1:5000
```
Usuarios de prueba: `admin@agroplaga.com / Admin2026`, `tecnico@agroplaga.com / Tecnico2026`, `productor@agroplaga.com / Productor2026`.

### Habilitar el inicio de sesión con Google
1. En [Google Cloud Console](https://console.cloud.google.com/), creá o seleccioná un proyecto y configurá la pantalla de consentimiento de OAuth.
2. Creá un **ID de cliente de OAuth** de tipo **Aplicación web**.
3. En **URI de redireccionamiento autorizados**, agregá exactamente `http://127.0.0.1:5000/login/google/callback` para desarrollo local.
4. Copiá el ID de cliente y el secreto en `.env` como `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`. No compartas ni publiques el secreto.
5. Reiniciá la app. El primer acceso con un correo confirmado por Google crea una cuenta con rol `productor`; si ese correo ya existe, se conserva su cuenta y rol.

Para producción, agregá en Google Cloud la URL HTTPS de tu dominio terminada en `/login/google/callback` y configurá la misma URL en `GOOGLE_REDIRECT_URI`.
