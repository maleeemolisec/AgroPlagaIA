# Configuración en Vercel + Neon (lo que tenés que hacer vos)

## 1. Arreglo del error 503 «Falta una tabla»
No hay que ejecutar nada a mano: **al recibir la primera visita la app crea sola todas las tablas en Neon**
(sin borrar datos) y carga cultivos y enfermedades. Solo asegurate de que en
Vercel → Settings → Environment Variables → **Production** exista `DATABASE_URL` con la cadena de Neon
(`postgresql://...?sslmode=require`) y hacé **Redeploy**.

## 2. Poder entrar ya mismo (administrador)
Agregá en Vercel: `ADMIN_EMAIL`, `ADMIN_PASSWORD` (8+ caracteres, letras y números) y `ADMIN_NAME`.
Redeploy → entrá en /login con ese correo y contraseña. (Se crea una sola vez, solo si no hay admin.)

## 3. Registro con correo (verificación por código)
Necesita enviar mails: `SMTP_USERNAME` = tu Gmail, `SMTP_PASSWORD` = **contraseña de aplicación**
(Cuenta Google → Seguridad → Verificación en 2 pasos → Contraseñas de aplicaciones), `SMTP_FROM` = tu Gmail.

## 4. Continuar con Facebook
1. developers.facebook.com → *Mis apps* → *Crear app* → agregá el producto **Facebook Login**.
2. Facebook Login → Configuración → **URI de redireccionamiento de OAuth válidos**:
   `https://TU-DOMINIO.vercel.app/login/facebook/callback`
3. Configuración de la app → Básica: copiá *Identificador* y *Clave secreta* a `FACEBOOK_CLIENT_ID` y `FACEBOOK_CLIENT_SECRET`
   (y `FACEBOOK_REDIRECT_URI` con la misma URL del paso 2).
4. Mientras la app esté en modo *Desarrollo* solo pueden entrar los administradores/testers de la app.
   Para abrirla a todos hay que pasarla a *Publicada* (Facebook pide URL de política de privacidad).

## 5. Ingresar con número de teléfono (SMS)
El envío de SMS con la integración local usa un teléfono Android con SIM en la misma red Wi-Fi que Flask; una función de Vercel no puede alcanzar esa red privada. En Vercel, el inicio por teléfono no estará disponible con esta modalidad. Para probar SMS localmente, seguí los pasos de SMS Gateway Android en `GUIA_DESPLIEGUE.md`. El mensaje puede tener costo según el plan de la operadora.

## Cómo funciona la verificación
- **Teléfono:** se envía un código por SMS; solo con el código correcto se inicia sesión o se vincula un teléfono
  a una cuenta existente (máx. 5 intentos, 1 reenvío por minuto). Primero hay que crear y verificar una cuenta por correo.
- **Facebook / Google:** el proveedor confirma que la cuenta existe y es de quien ingresa.
- **Correo:** código de 6 dígitos enviado al mail.
En el perfil se puede vincular un teléfono a una cuenta ya creada.

## Si algo falla
- Admin → Usuarios → **Probar conexión con la IA**: diagnostica Gemini.
- Variables nuevas = siempre **Redeploy** en Vercel.
