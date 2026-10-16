"""Asistente de Telegram: busca tu chat_id con el token de notificaciones.json, lo guarda y envía una prueba.

Antes: pega el token en notificaciones.json (o pásalo con --token) y escríbele cualquier mensaje a tu bot.
Uso:   python -m app.configurar_telegram [--token TOKEN]
"""
import argparse
import json
import shutil
import urllib.error
import urllib.request

from app.notificar import ARCHIVO, RAIZ, enviar


def _api(token: str, metodo: str) -> dict:
    with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/{metodo}", timeout=60) as r:
        return json.load(r)


def main(token_nuevo: str | None = None) -> None:
    if not ARCHIVO.exists():
        shutil.copy(RAIZ / "notificaciones.ejemplo.json", ARCHIVO)
    conf = json.loads(ARCHIVO.read_text(encoding="utf-8"))
    tg = conf.setdefault("telegram", {})
    if token_nuevo:
        tg.update({"token": token_nuevo.strip().replace(" ", ""), "activo": True})
        ARCHIVO.write_text(json.dumps(conf, ensure_ascii=False, indent=2), encoding="utf-8")
    token = tg.get("token", "").strip()
    if not token or "BOTFATHER" in token:
        print("Falta el token: pégalo en notificaciones.json -> telegram -> token")
        return
    try:
        bot = _api(token, "getMe")["result"]
        datos = _api(token, "getUpdates")
    except urllib.error.HTTPError as e:
        print(f"Telegram rechazó el token (error {e.code}): revisa que esté completo y sin espacios.")
        return
    except Exception as e:
        print("No se pudo conectar con Telegram (red o firewall):", type(e).__name__, "- intenta de nuevo.")
        return
    print(f"Token válido para el bot: {bot['first_name']} (@{bot['username']})")
    chats = [u["message"]["chat"] for u in datos.get("result", []) if "message" in u]
    for _ in range(4):  # espera en vivo hasta ~2 minutos a que le escribas
        if chats:
            break
        print(f"Esperando tu mensaje... escríbele 'hola' a @{bot['username']} ahora.", flush=True)
        try:
            datos = _api(token, "getUpdates?timeout=30")
        except Exception:
            continue
        chats = [u["message"]["chat"] for u in datos.get("result", []) if "message" in u]
    if not chats:
        print(f"Ese bot aún no recibe mensajes: abre https://t.me/{bot['username']}, toca Iniciar y escríbele 'hola'.")
        return
    chat = chats[-1]
    tg.update({"activo": True, "chat_id": str(chat["id"]), "token": token})
    ARCHIVO.write_text(json.dumps(conf, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"chat_id guardado para {chat.get('first_name') or chat.get('title') or 'tu chat'}.")
    canales = enviar(
        "Prueba rastreador Pokémon",
        "✅ Listo: aquí te llegarán las bajas de precio de Pokémon TCG.",
        "✅ <b>Listo</b>: aquí te llegarán las bajas de precio de <b>Pokémon TCG</b>.",
    )
    print("Mensaje de prueba enviado por:", ", ".join(canales) or "ninguno")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", help="token de BotFather (se guarda en notificaciones.json)")
    main(ap.parse_args().token)
