"""Envío de alertas por Telegram, correo (SMTP) y WhatsApp (CallMeBot).

La configuración vive en notificaciones.json (no se comparte: contiene tus claves).
Prueba:  python -m app.notificar
"""
import json
import smtplib
import urllib.parse
import urllib.request
from email.mime.text import MIMEText
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ARCHIVO = RAIZ / "notificaciones.json"


def cargar_config() -> dict:
    if not ARCHIVO.exists():
        return {}
    return json.loads(ARCHIVO.read_text(encoding="utf-8"))


def _telegram(c: dict, texto: str) -> None:
    datos = urllib.parse.urlencode({
        "chat_id": c["chat_id"], "text": texto, "parse_mode": "HTML",
        "disable_web_page_preview": "false",
    }).encode()
    urllib.request.urlopen(f"https://api.telegram.org/bot{c['token']}/sendMessage", datos, timeout=20)


def _correo(c: dict, asunto: str, texto: str) -> None:
    msg = MIMEText(texto, "plain", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = asunto, c["usuario"], c["para"]
    with smtplib.SMTP_SSL(c.get("smtp", "smtp.gmail.com"), c.get("puerto", 465), timeout=30) as s:
        s.login(c["usuario"], c["clave_app"])
        s.send_message(msg)


def _whatsapp(c: dict, texto: str) -> None:
    q = urllib.parse.urlencode({"phone": c["telefono"], "text": texto, "apikey": c["apikey"]})
    urllib.request.urlopen(f"https://api.callmebot.com/whatsapp.php?{q}", timeout=30)


def enviar(asunto: str, texto: str, texto_html: str | None = None) -> list[str]:
    """Envía por todos los canales activos. Devuelve los canales que funcionaron."""
    conf = cargar_config()
    ok = []
    canales = [
        ("telegram", lambda c: _telegram(c, texto_html or texto)),
        ("correo", lambda c: _correo(c, asunto, texto)),
        ("whatsapp_callmebot", lambda c: _whatsapp(c, texto)),
    ]
    for nombre, fn in canales:
        c = conf.get(nombre, {})
        if not c.get("activo"):
            continue
        try:
            fn(c)
            ok.append(nombre)
        except Exception as e:
            print(f"  ! No se pudo enviar por {nombre}: {e}")
    return ok


if __name__ == "__main__":
    canales = enviar("Prueba rastreador Pokémon", "✅ Las alertas del rastreador Pokémon TCG funcionan.")
    print("Enviado por:", canales or "ningún canal (revisa notificaciones.json)")
