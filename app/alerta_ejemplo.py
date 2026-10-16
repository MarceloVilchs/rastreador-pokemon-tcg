"""Envía una alerta de EJEMPLO (no se guarda) con el formato real, usando un ETB de la base.

Uso:  python -m app.alerta_ejemplo
"""
from app.db import conectar
from app.notificar import enviar
from app.scraper import _clp

con = conectar()
p = con.execute("""
    SELECT p.nombre, p.tienda, p.url, pr.precio FROM productos p
    JOIN precios pr ON pr.producto_id = p.id
    WHERE p.categoria = 'Elite Trainer Box' ORDER BY pr.fecha DESC, pr.precio LIMIT 1""").fetchone()
antes = int(p["precio"] * 1.15)
motivo = f"📉 Bajó 13% ({_clp(antes)} → {_clp(p['precio'])})"
titulo = "Pokémon TCG: 1 alerta(s) de precio (EJEMPLO)"
enviar(
    titulo,
    f"{titulo}\n\n[{p['tienda'].upper()}] {p['nombre']}\n{motivo}\nAhora {_clp(p['precio'])}\n{p['url']}",
    f"<b>{titulo}</b>\n\n<b>[{p['tienda'].upper()}]</b> <a href=\"{p['url']}\">{p['nombre']}</a>\n"
    f"{motivo}\nAhora <b>{_clp(p['precio'])}</b>",
)
print("Ejemplo enviado:", p["nombre"])
