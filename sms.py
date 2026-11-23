"""Verificación de teléfonos con SMS Gateway para Android en la red local.

La aplicación Android envía mensajes mediante una SIM propia. La disponibilidad y
el costo de cada SMS dependen del plan de telefonía móvil.

Variables necesarias:
    SMS_GATEWAY_URL=http://192.168.1.20:8080
    SMS_GATEWAY_USERNAME, SMS_GATEWAY_PASSWORD

Modo de prueba local (NUNCA en producción): SMS_MODO_PRUEBA=1 imprime el código
en la consola y se ignora cuando la app corre en Vercel.
"""
import hmac
import os
import re
import secrets
import time
from urllib.parse import urlparse

import requests

E164 = re.compile(r"^\+[1-9]\d{7,14}$")
_codigos = {}


def _cfg(nombre):
    return os.environ.get(nombre, "").strip()


def modo_prueba():
    return _cfg("SMS_MODO_PRUEBA") == "1" and not os.environ.get("VERCEL")


def configurado():
    if modo_prueba():
        return True
    return not os.environ.get("VERCEL") and bool(
        _cfg("SMS_GATEWAY_URL")
        and _cfg("SMS_GATEWAY_USERNAME")
        and _cfg("SMS_GATEWAY_PASSWORD")
    )


def normalizar(texto):
    """Devuelve E.164 o None; para Argentina agrega el 9 de móviles si falta."""
    if not texto:
        return None
    t = str(texto).strip()
    if not t.startswith("+"):
        return None
    digitos = re.sub(r"\D", "", t)
    if digitos.startswith("54") and not digitos.startswith("549") and len(digitos) == 12:
        digitos = "549" + digitos[2:]
    numero = "+" + digitos
    return numero if E164.match(numero) else None


def enmascarar(numero):
    return numero if len(numero) < 8 else numero[:3] + "•" * (len(numero) - 6) + numero[-3:]


def _guardar_codigo(numero, codigo):
    _codigos[numero] = (codigo, time.time() + 600)


def _enviar_por_pasarela(numero, codigo):
    base_url = _cfg("SMS_GATEWAY_URL").rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False, "La dirección de SMS Gateway no es válida. Revisá SMS_GATEWAY_URL en .env."
    try:
        respuesta = requests.post(
            base_url + "/message",
            json={
                "textMessage": {"text": f"Tu código de AgroPlaga IA es {codigo}. Vence en 10 minutos."},
                "phoneNumbers": [numero],
            },
            auth=(_cfg("SMS_GATEWAY_USERNAME"), _cfg("SMS_GATEWAY_PASSWORD")),
            timeout=15,
        )
    except requests.RequestException:
        return False, "No se pudo conectar con el teléfono pasarela. Revisá que esté encendido y en la misma red Wi-Fi."
    if respuesta.status_code in (200, 201, 202):
        return True, "Te enviamos un código por SMS usando el teléfono configurado."
    if respuesta.status_code in (401, 403):
        return False, "SMS Gateway rechazó las credenciales. Revisá el usuario y la contraseña de la app."
    return False, f"El teléfono pasarela rechazó el envío (HTTP {respuesta.status_code}). Revisá la SIM y los permisos de SMS."


def enviar_codigo(numero):
    """Envía un código; devuelve (ok, mensaje_para_el_usuario)."""
    codigo = f"{secrets.randbelow(1_000_000):06d}"
    if modo_prueba():
        _guardar_codigo(numero, codigo)
        print(f"[SMS MODO PRUEBA] Código para {numero}: {codigo}", flush=True)
        return True, "Modo de prueba: el código se imprimió en la consola del servidor."
    if not configurado():
        if os.environ.get("VERCEL"):
            return False, "La pasarela Android local no se puede usar desde Vercel; ejecutá AgroPlaga en la misma red Wi-Fi."
        return False, "Configurá SMS Gateway para Android en el archivo .env."
    ok, mensaje = _enviar_por_pasarela(numero, codigo)
    if ok:
        _guardar_codigo(numero, codigo)
    return ok, mensaje


def verificar_codigo(numero, codigo):
    """Valida un código de un solo uso, con vencimiento de diez minutos."""
    codigo = re.sub(r"\D", "", codigo or "")
    if len(codigo) < 4 or len(codigo) > 10:
        return False, "Ingresá el código que recibiste."
    esperado = _codigos.get(numero)
    if esperado and time.time() < esperado[1] and hmac.compare_digest(esperado[0], codigo):
        _codigos.pop(numero, None)
        return True, "Número verificado."
    if esperado and time.time() >= esperado[1]:
        _codigos.pop(numero, None)
    return False, "El código es incorrecto o venció."
