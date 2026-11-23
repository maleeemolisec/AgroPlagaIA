# AgroPlaga IA – Detección inteligente de enfermedades en cultivos
Trabajo Final Integrador – Aplicaciones Informáticas (Opción 6).

Flask + SQLite/MySQL/PostgreSQL + Gemini (visión artificial) + Leaflet + Chart.js.
El acceso con Google es opcional; requiere configurar `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` en `.env`.
El mapa productivo combina campos/lotes registrados, una capa de vigor vegetal NDVI de NASA MODIS (compuesto de 8 días) y consulta meteorológica de Open-Meteo. NDVI no identifica la especie de cultivo ni reemplaza datos de suelo.
Al crear o editar un lote se puede dibujar gratis su perímetro sobre la imagen satelital; se guarda y aparece en rojo en el mapa productivo y en los mapas de análisis. El proveedor de imagen RGB no garantiza actualización en tiempo real. Un análisis de zona en modo demo no muestra porcentajes de cobertura inventados.

- Instalación y despliegue: `GUIA_DESPLIEGUE.md`
- Documentación (Word): carpeta `docs/` (análisis y diseño, documentación técnica, manual de usuario), `docs/DER_AgroPlagaIA.png`
- Base de datos de prueba: `agroplaga.db` local, o `python seed.py` para generar datos de demostración
- Pruebas: `python test_app.py`

En Vercel, configura una base de datos PostgreSQL externa en `DATABASE_URL` y ejecuta `python seed.py --production` una vez desde tu equipo para preparar tablas y crear el primer administrador. SQLite y sus datos locales no se incluyen en Git ni persisten en el almacenamiento efímero de las funciones; las cuentas creadas localmente deben volver a registrarse.

El alta pública verifica el correo con un código enviado por SMTP de Gmail; configura `SMTP_USERNAME`, `SMTP_PASSWORD` (contraseña de aplicación) y `SMTP_FROM` en Vercel. Luego de verificar el código, la sesión queda iniciada. Consulta `GUIA_DESPLIEGUE.md` para los pasos y el comando seguro `python seed.py --catalogs-only` para completar catálogos faltantes sin borrar cuentas.

El acceso por teléfono puede enviar SMS desde una SIM propia usando SMS Gateway para Android. Requiere que Flask local y el teléfono estén en la misma red Wi-Fi; el costo depende del plan de telefonía. No funciona desde Vercel hacia una dirección local de tu Wi-Fi.

Para fotos en Vercel, conecta un store privado de **Vercel Blob** al proyecto. Las fotos se sirven desde una ruta autenticada y no se guardan en el disco efímero de la función. El límite de carga en Vercel es 4 MB por foto por el límite de solicitudes de Functions.

## Novedades
- La base (Neon/PostgreSQL, SQLite o MySQL) se crea y migra sola al arrancar. Ver `GUIA_VERCEL.md`.
- Inicio de sesión con correo, Google, **Facebook** y **teléfono (SMS)**.
- La IA verifica que la foto sea del cultivo del lote y se avisa si la ubicación marcada no coincide con el campo.
- El mapa productivo nacional permite filtrar cultivos registrados, consultar el clima y activar la capa NDVI con su fecha publicada.
- Pruebas: `python test_app.py` y `python test_nuevo.py`.
