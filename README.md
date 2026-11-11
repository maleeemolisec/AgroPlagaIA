# AgroPlaga IA – Detección inteligente de enfermedades en cultivos
Trabajo Final Integrador – Aplicaciones Informáticas (Opción 6).

Flask + SQLite/MySQL + Gemini (visión artificial) + Leaflet + Chart.js.
El acceso con Google es opcional; requiere configurar `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` en `.env`.

- Instalación y despliegue: `GUIA_DESPLIEGUE.md`
- Documentación (Word): carpeta `docs/` (análisis y diseño, documentación técnica, manual de usuario), `docs/DER_AgroPlagaIA.png`
- Base de datos de prueba: `agroplaga.db` ya incluida, o `python seed.py --force`; volcado SQL en `datos_prueba.sql`
- Pruebas: `python test_app.py`

En Vercel, configura una base de datos MySQL externa en `DATABASE_URL`: SQLite y sus datos locales no se incluyen en Git y no persisten en el almacenamiento efímero de las funciones. Las cuentas creadas localmente deben migrarse o volver a crearse en la base remota.
