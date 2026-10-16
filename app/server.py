"""Servidor local: API + página web.

Uso:  python -m uvicorn app.server:app --port 8000   (o doble clic en iniciar.bat)
"""
import os
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.db import conectar

RAIZ = Path(__file__).resolve().parent.parent
app = FastAPI(title="Rastreador Pokémon TCG")
_proceso: subprocess.Popen | None = None

CONSULTA = """
WITH ult AS (
    SELECT producto_id, MAX(fecha) AS fecha FROM precios GROUP BY producto_id
), stats AS (
    SELECT producto_id, MIN(precio) AS minimo, MAX(precio) AS maximo, COUNT(*) AS dias
    FROM precios GROUP BY producto_id
)
SELECT p.*, pr.precio, pr.precio_normal, pr.precio_tarjeta, pr.fecha AS fecha_precio,
       s.minimo, s.maximo, s.dias,
       (SELECT precio FROM precios WHERE producto_id = p.id AND fecha < pr.fecha
        ORDER BY fecha DESC LIMIT 1) AS precio_previo
FROM productos p
JOIN ult u ON u.producto_id = p.id
JOIN precios pr ON pr.producto_id = p.id AND pr.fecha = u.fecha
JOIN stats s ON s.producto_id = p.id
"""


def _fila(r) -> dict:
    d = dict(r)
    ref = d["precio_normal"] or d["maximo"]
    mejor = min(x for x in (d["precio"], d["precio_tarjeta"]) if x)
    d["mejor_precio"] = mejor
    d["descuento_pct"] = round((ref - d["precio"]) * 100 / ref) if ref and ref > d["precio"] else 0
    d["en_oferta"] = bool(d["precio_normal"] and d["precio_normal"] > d["precio"])
    d["es_minimo"] = d["dias"] > 1 and d["precio"] <= d["minimo"]
    d["cambio"] = d["precio"] - d["precio_previo"] if d["precio_previo"] else 0
    return d


@app.get("/api/productos")
def productos(q: str = "", tienda: str = "", categoria: str = "", idioma: str = "",
              ofertas: bool = False, marcados: bool = False, aniversario: bool = False,
              solo_vigentes: bool = True, precio_max: int = 0, orden: str = "precio"):
    sql, args = CONSULTA + " WHERE 1=1", []
    if q:
        for palabra in q.lower().split():
            sql += " AND lower(p.nombre) LIKE ?"
            args.append(f"%{palabra}%")
    for campo, valor in (("p.tienda", tienda), ("p.categoria", categoria), ("p.idioma", idioma)):
        if valor:
            sql += f" AND {campo} = ?"
            args.append(valor)
    if marcados:
        sql += " AND p.marcado = 1"
    if aniversario:
        sql += " AND p.aniversario30 = 1"
    if ofertas:
        sql += " AND pr.precio_normal > pr.precio"
    if precio_max:
        sql += " AND pr.precio <= ?"
        args.append(precio_max)
    if solo_vigentes:  # visto en los últimos 3 días
        sql += " AND u.fecha >= date('now', 'localtime', '-3 days')"
    con = conectar()
    filas = [_fila(r) for r in con.execute(sql, args)]
    con.close()
    claves = {
        "precio": lambda d: d["mejor_precio"],
        "precio_desc": lambda d: -d["mejor_precio"],
        "descuento": lambda d: -d["descuento_pct"],
        "cambio": lambda d: d["cambio"],
        "nombre": lambda d: d["nombre"].lower(),
        "reciente": lambda d: d["primera_vez"],
    }
    filas.sort(key=claves.get(orden, claves["precio"]), reverse=(orden == "reciente"))
    return filas


@app.get("/api/productos/{pid}/historial")
def historial(pid: int):
    con = conectar()
    prod = con.execute("SELECT * FROM productos WHERE id = ?", (pid,)).fetchone()
    if not prod:
        raise HTTPException(404)
    puntos = [dict(r) for r in con.execute(
        "SELECT fecha, precio, precio_normal, precio_tarjeta FROM precios WHERE producto_id = ? ORDER BY fecha",
        (pid,))]
    con.close()
    return {"producto": dict(prod), "puntos": puntos}


class Marca(BaseModel):
    marcado: bool


@app.post("/api/productos/{pid}/marcar")
def marcar(pid: int, m: Marca):
    con = conectar()
    con.execute(
        "UPDATE productos SET marcado = ?, marcado_en = CASE WHEN ? THEN datetime('now','localtime') END WHERE id = ?",
        (int(m.marcado), int(m.marcado), pid))
    con.commit()
    con.close()
    return {"ok": True}


@app.get("/api/resumen")
def resumen():
    con = conectar()
    r = {
        "tiendas": [x[0] for x in con.execute("SELECT DISTINCT tienda FROM productos ORDER BY 1")],
        "categorias": [x[0] for x in con.execute("SELECT DISTINCT categoria FROM productos ORDER BY 1")],
        "total": con.execute("SELECT COUNT(*) FROM productos").fetchone()[0],
        "marcados": con.execute("SELECT COUNT(*) FROM productos WHERE marcado = 1").fetchone()[0],
        "ultima": dict(x) if (x := con.execute(
            "SELECT * FROM ejecuciones ORDER BY id DESC LIMIT 1").fetchone()) else None,
        "alertas": [dict(x) for x in con.execute(
            """SELECT a.*, p.nombre, p.tienda, p.url FROM alertas a JOIN productos p ON p.id = a.producto_id
               ORDER BY a.id DESC LIMIT 30""")],
        "actualizando": _proceso is not None and _proceso.poll() is None,
    }
    con.close()
    return r


@app.post("/api/actualizar")
def actualizar(modo: str = "vigilancia"):
    global _proceso
    if _proceso is not None and _proceso.poll() is None:
        return {"ok": False, "mensaje": "Ya hay una actualización en curso"}
    log = open(RAIZ / "datos" / f"ultima_{modo}.log", "w", encoding="utf-8")
    _proceso = subprocess.Popen(
        [sys.executable, "-m", "app.scraper", "--modo", "completo" if modo == "completo" else "vigilancia"],
        cwd=RAIZ, stdout=log, stderr=subprocess.STDOUT, env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    return {"ok": True}


app.mount("/static", StaticFiles(directory=RAIZ / "web"), name="static")


@app.get("/")
def inicio():
    return FileResponse(RAIZ / "web" / "index.html")
