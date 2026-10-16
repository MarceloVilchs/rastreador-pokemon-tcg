"""Base de datos SQLite: productos y un precio por producto por día."""
import sqlite3
from datetime import date, datetime
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "datos" / "precios.db"

ESQUEMA = """
CREATE TABLE IF NOT EXISTS productos (
    id            INTEGER PRIMARY KEY,
    tienda        TEXT NOT NULL,
    sku           TEXT NOT NULL,
    nombre        TEXT NOT NULL,
    url           TEXT,
    imagen        TEXT,
    marca         TEXT,
    vendedor      TEXT,
    tema          TEXT,
    categoria     TEXT,
    idioma        TEXT,
    aniversario30 INTEGER DEFAULT 0,
    primera_vez   TEXT,
    ultima_vez    TEXT,
    marcado       INTEGER DEFAULT 0,
    marcado_en    TEXT,
    UNIQUE (tienda, sku)
);
CREATE TABLE IF NOT EXISTS precios (
    producto_id    INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
    fecha          TEXT NOT NULL,
    precio         INTEGER NOT NULL,
    precio_normal  INTEGER,
    precio_tarjeta INTEGER,
    PRIMARY KEY (producto_id, fecha)
);
CREATE TABLE IF NOT EXISTS ejecuciones (
    id        INTEGER PRIMARY KEY,
    inicio    TEXT,
    fin       TEXT,
    modo      TEXT,
    resumen   TEXT
);
CREATE TABLE IF NOT EXISTS alertas (
    id              INTEGER PRIMARY KEY,
    producto_id     INTEGER NOT NULL REFERENCES productos(id) ON DELETE CASCADE,
    fecha_hora      TEXT NOT NULL,
    tipo            TEXT NOT NULL,
    precio          INTEGER,
    precio_anterior INTEGER,
    canales         TEXT
);
"""


def conectar() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(ESQUEMA)
    columnas = {r["name"] for r in con.execute("PRAGMA table_info(ejecuciones)")}
    if "modo" not in columnas:
        con.execute("ALTER TABLE ejecuciones ADD COLUMN modo TEXT")
    return con


def guardar_producto(con: sqlite3.Connection, p: dict) -> dict:
    """Inserta o actualiza el producto y registra el precio de hoy (si ya hay uno hoy, lo reemplaza).

    Devuelve cómo estaba antes: si es nuevo, su último precio, su mínimo histórico y si está marcado.
    """
    ahora = datetime.now().isoformat(timespec="seconds")
    previo = con.execute(
        """
        SELECT p.id, p.marcado,
               (SELECT precio FROM precios WHERE producto_id = p.id ORDER BY fecha DESC LIMIT 1) AS ultimo,
               (SELECT MIN(precio) FROM precios WHERE producto_id = p.id) AS minimo,
               (SELECT COUNT(*) FROM precios WHERE producto_id = p.id) AS dias
        FROM productos p WHERE p.tienda = ? AND p.sku = ?
        """,
        (p["tienda"], p["sku"]),
    ).fetchone()
    con.execute(
        """
        INSERT INTO productos (tienda, sku, nombre, url, imagen, marca, vendedor, tema,
                               categoria, idioma, aniversario30, primera_vez, ultima_vez)
        VALUES (:tienda, :sku, :nombre, :url, :imagen, :marca, :vendedor, :tema,
                :categoria, :idioma, :aniversario30, :ahora, :ahora)
        ON CONFLICT (tienda, sku) DO UPDATE SET
            nombre = excluded.nombre, url = excluded.url, imagen = excluded.imagen,
            marca = excluded.marca, vendedor = excluded.vendedor, categoria = excluded.categoria,
            idioma = excluded.idioma, aniversario30 = excluded.aniversario30,
            ultima_vez = excluded.ultima_vez
        """,
        {**p, "ahora": ahora},
    )
    pid = con.execute(
        "SELECT id FROM productos WHERE tienda = ? AND sku = ?", (p["tienda"], p["sku"])
    ).fetchone()["id"]
    con.execute(
        """
        INSERT INTO precios (producto_id, fecha, precio, precio_normal, precio_tarjeta)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (producto_id, fecha) DO UPDATE SET
            precio = excluded.precio, precio_normal = excluded.precio_normal,
            precio_tarjeta = excluded.precio_tarjeta
        """,
        (pid, date.today().isoformat(), p["precio"], p.get("precio_normal"), p.get("precio_tarjeta")),
    )
    return {
        "id": pid,
        "nuevo": previo is None,
        "marcado": bool(previo and previo["marcado"]),
        "precio_anterior": previo["ultimo"] if previo else None,
        "minimo_anterior": previo["minimo"] if previo else None,
        "dias": previo["dias"] if previo else 0,
    }


def alerta_reciente(con: sqlite3.Connection, producto_id: int, tipo: str, precio: int, dias: int = 7) -> bool:
    """True si ya avisamos lo mismo (mismo producto, tipo y precio) en los últimos días."""
    return con.execute(
        """
        SELECT 1 FROM alertas WHERE producto_id = ? AND tipo = ? AND precio = ?
          AND fecha_hora >= datetime('now', 'localtime', ?)
        """,
        (producto_id, tipo, precio, f"-{dias} days"),
    ).fetchone() is not None


def registrar_alerta(con, producto_id, tipo, precio, precio_anterior, canales) -> None:
    con.execute(
        "INSERT INTO alertas (producto_id, fecha_hora, tipo, precio, precio_anterior, canales) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (producto_id, datetime.now().isoformat(timespec="seconds"), tipo, precio, precio_anterior,
         ",".join(canales)),
    )
