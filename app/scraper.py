"""Scraper de Falabella, Paris, Ripley y Líder con Playwright.

Uso:
    python -m app.scraper              # tiendas activas en config.json
    python -m app.scraper --tienda paris
    python -m app.scraper --modo vigilancia   # pasada rápida (pág. 1) para detectar bajas
    python -m app.scraper --ver        # muestra el navegador mientras trabaja
"""
import argparse
import json
import random
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from playwright.sync_api import sync_playwright

from app.db import alerta_reciente, conectar, guardar_producto, registrar_alerta
from app.notificar import cargar_config as cargar_config_alertas, enviar

RAIZ = Path(__file__).resolve().parent.parent
CONFIG = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))

# --- Extractores: se ejecutan dentro de la página y devuelven una lista de productos ---

JS_FALABELLA = r"""() => {
  const n = document.getElementById('__NEXT_DATA__');
  if (!n) return null;
  const pp = JSON.parse(n.textContent).props.pageProps;
  const num = s => s ? parseInt(String(s).replace(/\D/g, ''), 10) : null;
  return (pp.results || []).map(r => {
    const ps = r.prices || [];
    const get = t => ps.find(p => p.type === t);
    const crossed = ps.find(p => p.crossed);
    const actual = get('eventPrice') || get('internetPrice') || ps.find(p => !p.crossed && p.type !== 'cmrPrice');
    const cmr = get('cmrPrice');
    return {
      sku: r.skuId || r.productId, nombre: r.displayName, url: r.url,
      imagen: (r.mediaUrls || [])[0] || null, marca: r.brand, vendedor: r.sellerName,
      precio: actual ? num(actual.price[0]) : null,
      precio_normal: crossed ? num(crossed.price[0]) : null,
      precio_tarjeta: cmr ? num(cmr.price[0]) : null,
    };
  });
}"""

JS_PARIS = r"""() => {
  const num = s => parseInt(s.replace(/\D/g, ''), 10);
  const ld = {};
  for (const s of document.querySelectorAll('script[type="application/ld+json"]')) {
    try {
      const me = JSON.parse(s.textContent).mainEntity;
      for (const li of (me && me.itemListElement) || []) ld[li.item.url.split('/').pop()] = li.item;
    } catch (e) {}
  }
  return [...document.querySelectorAll('a[id^="product-"]')].map(a => {
    const href = a.getAttribute('href') || '';
    const key = href.split('/').pop();
    const item = ld[key] || {};
    const sku = a.id.split('-').pop();
    const montos = (a.innerText.match(/\$\s?[\d.]+/g) || []).map(num);
    const precio = (item.offers && item.offers.price) || (montos.length ? montos[Math.min(1, montos.length - 1)] : null);
    const max = montos.length ? Math.max(...montos) : null;
    const min = montos.length ? Math.min(...montos) : null;
    const img = a.querySelector('img');
    return {
      sku, nombre: item.name || a.innerText.split('\n').find(l => l.length > 12) || sku,
      url: 'https://www.paris.cl' + href.replace(/^https?:\/\/[^/]+/, ''),
      imagen: item.image || (img && img.src) || null,
      marca: (item.brand && item.brand.name) || a.innerText.split('\n')[0], vendedor: null,
      precio, precio_normal: max && max > precio ? max : null,
      precio_tarjeta: min && min < precio ? min : null,
    };
  });
}"""

JS_RIPLEY = r"""() => {
  const num = s => parseInt(s.replace(/\D/g, ''), 10);
  const vistos = {};
  for (const a of document.querySelectorAll('a[href*="-mpm"]')) {
    const m = a.href.match(/-(mpm\d+)/);
    if (!m || vistos[m[1]] || !/\$/.test(a.innerText)) continue;
    const lineas = a.innerText.split('\n').map(l => l.trim()).filter(Boolean);
    const montos = lineas.filter(l => /^\$\s?[\d.]+$/.test(l)).map(num);
    const textos = lineas.filter(l => !/^[-\$]|%$/.test(l) && !/env[ií]o|retiro/i.test(l));
    const nombre = textos.reduce((a, b) => b.length > a.length ? b : a, '');
    const img = a.querySelector('img');
    let precio = null, normal = null, tarjeta = null;
    if (montos.length === 1) precio = montos[0];
    if (montos.length === 2) [normal, precio] = montos;
    if (montos.length >= 3) [normal, precio, tarjeta] = montos;
    vistos[m[1]] = {
      sku: m[1], nombre, url: a.href.split('?')[0],
      imagen: img ? (img.src || img.dataset.src) : null,
      marca: textos[0] !== nombre ? textos[0] : null, vendedor: null,
      precio, precio_normal: normal, precio_tarjeta: tarjeta,
    };
  }
  return Object.values(vistos);
}"""

JS_LIDER = r"""() => {
  const n = document.getElementById('__NEXT_DATA__');
  if (!n) return null;
  const sr = JSON.parse(n.textContent).props.pageProps.initialData?.searchResult;
  if (!sr) return [];
  const num = s => s ? parseInt(String(s).replace(/\D/g, ''), 10) || null : null;
  const items = (sr.itemStacks || []).flatMap(s => s.items || []);
  return items.filter(i => i.__typename === 'Product' && i.priceInfo).map(i => ({
    sku: i.usItemId || i.id, nombre: i.name,
    url: 'https://www.lider.cl' + (i.canonicalUrl || ''),
    imagen: i.imageInfo && i.imageInfo.thumbnailUrl, marca: i.brand, vendedor: i.sellerName,
    precio: num(i.priceInfo.linePrice) || num(i.priceInfo.itemPrice),
    precio_normal: num(i.priceInfo.wasPrice),
    precio_tarjeta: null,
  }));
}"""

TIENDAS = {
    "falabella": {
        "url": lambda q, p: f"https://www.falabella.com/falabella-cl/search?Ntt={quote(q)}&page={p}",
        "esperar": "#__NEXT_DATA__",
        "js": JS_FALABELLA,
    },
    "paris": {
        "url": lambda q, p: f"https://www.paris.cl/search?q={quote(q)}&page={p}",
        "esperar": 'a[id^="product-"]',
        "js": JS_PARIS,
    },
    "ripley": {
        "url": lambda q, p: f"https://simple.ripley.cl/search/{quote(q)}?page={p}",
        "esperar": 'a[href*="-mpm"]',
        "js": JS_RIPLEY,
    },
    "lider": {
        "url": lambda q, p: f"https://www.lider.cl/search?q={quote(q)}&page={p}",
        "esperar": "#__NEXT_DATA__",
        "js": JS_LIDER,
    },
}


# --- Clasificación de productos ---

def _norm(s: str) -> str:
    return (s or "").lower()


def pasa_filtro(nombre: str, tema: dict) -> bool:
    n = _norm(nombre)
    return (
        any(k in n for k in tema["debe_contener_alguna"])
        and any(k in n for k in tema["y_alguna_de"])
        and not any(re.search(r"\b" + re.escape(k) + r"\b", n) for k in tema["excluir"])
    )


# El orden importa: gana la primera que calce.
CATEGORIAS = [
    ("Accesorios", r"fundas?\b|sleeves\b|protector|[aá]lbum|deck box|portamazo|playmat|calcoman"),
    ("Lotes / Cartas sueltas", r"\blote\b|cartas originales|cartas variadas|holograficas|\d{2,} cartas pok"),
    ("Elite Trainer Box", r"elite trainer|\betb\b|caja de entrenador|caja de entrenamiento|caja [eé]lite|trainer box"),
    ("Booster Box / Display", r"booster box|display|caja de sobres|caja de refuerzo"),
    ("Booster Bundle", r"bundle"),
    ("Tin / Lata", r"\btin\b|\blata\b"),
    ("Colección / Premium", r"collection|colecci[oó]n|premium|binder|carpeta|poster|\bbox\b"),
    ("Mazos / Battle", r"deck|mazo|baraja|battle|starter|set de inicio|toolkit|league|academy"),
    ("Sobres / Booster", r"booster|sobres?\b|blister|sleeved|refuerzo|expansi[oó]n|\bpacks?\b"),
]


def clasificar(nombre: str) -> dict:
    n = _norm(nombre)
    categoria = next((c for c, rx in CATEGORIAS if re.search(rx, n)), "Otros")
    if re.search(r"espa[ñn]|\besp\b|castellano", n):
        idioma = "Español"
    elif re.search(r"ingl[eé]s|\bing\b|\bingle\b|english", n):
        idioma = "Inglés"
    else:
        idioma = None
    aniversario = bool(re.search(r"30th|30\.?º? aniversario|30 a[ñn]os|celebration", n))
    return {"categoria": categoria, "idioma": idioma, "aniversario30": int(aniversario)}


def reclasificar(con, log=print) -> None:
    """Aplica las reglas actuales a lo ya guardado y borra lo que ya no pasa el filtro (salvo marcados)."""
    temas = {t["nombre"]: t for t in CONFIG["temas"]}
    borrados = 0
    for r in con.execute("SELECT id, nombre, tema, marcado FROM productos").fetchall():
        tema = temas.get(r["tema"])
        if tema and not pasa_filtro(r["nombre"], tema) and not r["marcado"]:
            con.execute("DELETE FROM productos WHERE id = ?", (r["id"],))
            borrados += 1
            continue
        c = clasificar(r["nombre"])
        con.execute("UPDATE productos SET categoria = ?, idioma = ?, aniversario30 = ? WHERE id = ?",
                    (c["categoria"], c["idioma"], c["aniversario30"], r["id"]))
    con.commit()
    if borrados:
        log(f"Limpieza: {borrados} producto(s) que ya no pasan el filtro")


# --- Recorrido ---

def raspar_tienda(page, tienda: str, tema: dict, busquedas: list[str], paginas: int, log) -> dict:
    conf = TIENDAS[tienda]
    encontrados: dict[str, dict] = {}
    for q in busquedas:
        for p in range(1, paginas + 1):
            url = conf["url"](q, p)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_selector(conf["esperar"], state="attached", timeout=20000)
                page.wait_for_timeout(1500)
                lista = page.evaluate(conf["js"]) or []
            except Exception as e:  # bloqueo, timeout o cambio de diseño
                log(f"  [{tienda}] '{q}' pág {p}: sin resultados ({type(e).__name__})")
                break
            nuevos = 0
            for prod in lista:
                if not prod.get("sku") or not prod.get("precio"):
                    continue
                if prod["sku"] not in encontrados:
                    nuevos += 1
                encontrados[prod["sku"]] = prod
            log(f"  [{tienda}] '{q}' pág {p}: {len(lista)} productos ({nuevos} nuevos)")
            time.sleep(random.uniform(*CONFIG["pausa_segundos_entre_paginas"]))
            if nuevos == 0:
                break
    validos = {k: v for k, v in encontrados.items() if pasa_filtro(v["nombre"], tema)}
    return validos


# --- Alertas ---

def _clp(n: int) -> str:
    return "$" + f"{n:,}".replace(",", ".")


def evaluar_alertas(prod: dict, antes: dict, tienda_tenia_datos: bool, conf: dict) -> list[tuple[str, str]]:
    """Devuelve [(tipo, motivo)] según el precio nuevo vs. lo que había guardado."""
    alertas = []
    precio = prod["precio"]
    if antes["nuevo"]:
        # En la primera pasada de una tienda todo es "nuevo": no avisamos para no llenarte de mensajes.
        if tienda_tenia_datos and conf.get("avisar_productos_nuevos", True):
            alertas.append(("nuevo", "🆕 Producto nuevo"))
        return alertas
    ant = antes["precio_anterior"]
    if ant and precio < ant:
        baja_pct = (ant - precio) * 100 / ant
        if baja_pct >= conf.get("umbral_baja_pct", 5):
            alertas.append(("baja", f"📉 Bajó {baja_pct:.0f}% ({_clp(ant)} → {_clp(precio)})"))
        elif antes["marcado"] and conf.get("avisar_cualquier_baja_si_marcado", True):
            alertas.append(("baja", f"⭐ Tu marcado bajó {baja_pct:.0f}% ({_clp(ant)} → {_clp(precio)})"))
    minimo = antes["minimo_anterior"]
    # Con un solo día de historial el "mínimo" es el mismo precio anterior: ya lo cubre la alerta de baja.
    if antes["dias"] >= 2 and minimo and precio < minimo and conf.get("avisar_minimo_historico", True):
        alertas.append(("minimo", f"🏆 Nuevo mínimo histórico (antes {_clp(minimo)})"))
    return alertas


def enviar_alertas(con, pendientes: list[dict], log) -> int:
    if not pendientes:
        return 0
    lineas_txt, lineas_html = [], []
    for a in pendientes[:25]:
        p = a["prod"]
        motivos = " · ".join(m for _, m in a["alertas"])
        extra = f" (tarjeta {_clp(p['precio_tarjeta'])})" if p.get("precio_tarjeta") else ""
        lineas_txt.append(f"[{a['tienda'].upper()}] {p['nombre']}\n{motivos}\nAhora {_clp(p['precio'])}{extra}\n{p['url']}")
        lineas_html.append(
            f"<b>[{a['tienda'].upper()}]</b> <a href=\"{p['url']}\">{p['nombre']}</a>\n"
            f"{motivos}\nAhora <b>{_clp(p['precio'])}</b>{extra}"
        )
    if len(pendientes) > 25:
        lineas_txt.append(f"...y {len(pendientes) - 25} más (revisa la página)")
        lineas_html.append(f"<i>...y {len(pendientes) - 25} más (revisa la página)</i>")
    titulo = f"Pokémon TCG: {len(pendientes)} alerta(s) de precio"
    canales = enviar(titulo, titulo + "\n\n" + "\n\n".join(lineas_txt),
                     f"<b>{titulo}</b>\n\n" + "\n\n".join(lineas_html))
    for a in pendientes:
        for tipo, _ in a["alertas"]:
            registrar_alerta(con, a["antes"]["id"], tipo, a["prod"]["precio"], a["antes"]["precio_anterior"], canales)
    con.commit()
    log(f"Alertas: {len(pendientes)} producto(s), enviadas por: {', '.join(canales) or 'ningún canal configurado'}")
    return len(pendientes)


# --- Ejecución ---

def ejecutar(tiendas: list[str], modo: str = "completo", ver: bool = False, log=print) -> dict:
    con = conectar()
    conf_alertas = cargar_config_alertas()
    inicio = datetime.now().isoformat(timespec="seconds")
    resumen = {}
    pendientes = []
    if modo == "vigilancia":
        busquedas_modo, paginas = CONFIG["vigilancia"]["busquedas"], CONFIG["vigilancia"]["paginas"]
    else:
        busquedas_modo, paginas = None, CONFIG["paginas_max_por_busqueda"]
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not ver)
        ctx = browser.new_context(
            locale="es-CL",
            timezone_id="America/Santiago",
            viewport={"width": 1366, "height": 900},
        )
        page = ctx.new_page()
        for tema in [t for t in CONFIG["temas"] if t.get("activo")]:
            for tienda in tiendas:
                log(f"== {tienda} · {tema['nombre']} · {modo} ==")
                tenia_datos = con.execute(
                    "SELECT 1 FROM productos WHERE tienda = ? LIMIT 1", (tienda,)
                ).fetchone() is not None
                productos = raspar_tienda(page, tienda, tema, busquedas_modo or tema["busquedas"], paginas, log)
                for prod in productos.values():
                    antes = guardar_producto(con, {
                        **prod, **clasificar(prod["nombre"]),
                        "tienda": tienda, "tema": tema["nombre"],
                    })
                    alertas = [
                        (t, m) for t, m in evaluar_alertas(prod, antes, tenia_datos, conf_alertas)
                        if not alerta_reciente(con, antes["id"], t, prod["precio"])
                    ]
                    if alertas:
                        pendientes.append({"tienda": tienda, "prod": prod, "antes": antes, "alertas": alertas})
                con.commit()
                resumen[tienda] = resumen.get(tienda, 0) + len(productos)
                log(f"   -> {len(productos)} productos guardados")
        browser.close()
    if modo == "completo":
        reclasificar(con, log)
    resumen["alertas"] = enviar_alertas(con, pendientes, log)
    con.execute(
        "INSERT INTO ejecuciones (inicio, fin, modo, resumen) VALUES (?, ?, ?, ?)",
        (inicio, datetime.now().isoformat(timespec="seconds"), modo, json.dumps(resumen)),
    )
    con.commit()
    con.close()
    return resumen


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tienda", choices=list(TIENDAS), action="append")
    ap.add_argument("--modo", choices=["completo", "vigilancia"], default="completo")
    ap.add_argument("--ver", action="store_true", help="mostrar el navegador")
    args = ap.parse_args()
    print(ejecutar(args.tienda or CONFIG["tiendas_activas"], modo=args.modo, ver=args.ver))
