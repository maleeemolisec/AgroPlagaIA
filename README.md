# AgroPlaga IA – Detección inteligente de enfermedades en cultivos
Trabajo Final Integrador – Aplicaciones Informáticas (Opción 6).

Flask + SQLite/MySQL/PostgreSQL + Gemini (visión artificial) + Leaflet + Chart.js.
El acceso con Google es opcional; requiere configurar `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` en `.env`.

- Instalación y despliegue: `GUIA_DESPLIEGUE.md`
- Documentación (Word): carpeta `docs/` (análisis y diseño, documentación técnica, manual de usuario), `docs/DER_AgroPlagaIA.png`
- Base de datos de prueba: `agroplaga.db` local, o `python seed.py` para generar datos de demostración
- Pruebas: `python test_app.py`

En Vercel, configura una base de datos PostgreSQL externa en `DATABASE_URL` y ejecuta `python seed.py --production` una vez desde tu equipo para preparar tablas y crear el primer administrador. SQLite y sus datos locales no se incluyen en Git ni persisten en el almacenamiento efímero de las funciones; las cuentas creadas localmente deben volver a registrarse.

El alta pública verifica el correo con un código enviado por SMTP de Gmail; configura `SMTP_USERNAME`, `SMTP_PASSWORD` (contraseña de aplicación) y `SMTP_FROM` en Vercel. Luego de verificar el código, la sesión queda iniciada. Consulta `GUIA_DESPLIEGUE.md` para los pasos y el comando seguro `python seed.py --catalogs-only` para completar catálogos faltantes sin borrar cuentas.
