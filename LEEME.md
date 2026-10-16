# Rastreador Pokémon TCG

Rastrea precios de cartas Pokémon (ETB, boosters, tins, colecciones, 30 aniversario…) en
**Falabella y Paris**, guarda el histórico diario y te avisa al celular cuando algo baja.

> **Ripley y Líder** están desactivadas: Ripley responde 403 (Cloudflare) y Líder muestra un CAPTCHA
> "Robot or human?" a navegadores automatizados. El proyecto no intenta saltar esos bloqueos. Sus lectores
> quedan escritos en `app/scraper.py` por si algún día lo permiten (se activan en `tiendas_activas` de `config.json`).

## Uso diario

| Qué | Cómo |
|---|---|
| Abrir la página | Doble clic en `iniciar.bat` → se abre http://localhost:8000 |
| Barrido completo (todas las búsquedas) | Botón **🔄 Barrido completo** o `barrido.bat` |
| Vigilancia rápida (solo pág. 1, para detectar bajas) | Botón **⚡ Vigilar ahora** o `vigilar.bat` |
| Automatizar (diario + cada 30 min) | Clic derecho en `programar_tareas.ps1` → *Ejecutar con PowerShell* |

En la página: haz clic en ☆ para **marcar** un producto y en la tarjeta para ver el **gráfico de precios**.

## Cómo evita bloqueos

- **Barrido completo 1 vez al día**: 5 búsquedas × hasta 4 páginas por tienda, con pausas aleatorias de 3–6 s.
- **Vigilancia cada 30 min**: solo 2 búsquedas, página 1 (≈8 cargas en total). Cada página trae 30–48 productos,
  así que con muy pocas consultas se detectan las bajas.
- Si una tienda empieza a bloquear, sube el intervalo o la pausa en `config.json`. No se saltan CAPTCHAs.

## Alertas al celular

1. Copia `notificaciones.ejemplo.json` como `notificaciones.json`.
2. Activa (`"activo": true`) el canal o los canales que quieras:

**Telegram (recomendado, gratis e instantáneo)**
1. En Telegram, habla con **@BotFather** → `/newbot` → te entrega un *token*.
2. Escríbele cualquier cosa a tu bot nuevo.
3. Abre `https://api.telegram.org/bot<TOKEN>/getUpdates` en el navegador y copia el número de `"chat":{"id": ...}`.
4. Pon `token` y `chat_id` en `notificaciones.json`.

**Correo (Gmail)**: activa la verificación en 2 pasos en tu cuenta Google y crea una *contraseña de aplicación*
(Cuenta Google → Seguridad → Contraseñas de aplicaciones). Úsala en `clave_app`, no tu clave normal.

**WhatsApp (CallMeBot, gratis para uso personal)**: sigue las instrucciones de https://www.callmebot.com/blog/free-api-whatsapp-messages/
para obtener tu `apikey` y ponla junto a tu número.

3. Prueba: `.venv\Scripts\python.exe -m app.notificar`

**Qué dispara una alerta** (configurable en `notificaciones.json`):
- Baja ≥ `umbral_baja_pct` % respecto del último precio visto.
- Cualquier baja si el producto está marcado ★.
- Nuevo mínimo histórico.
- Producto que aparece por primera vez (lanzamientos o reposiciones).
- La misma alerta no se repite durante 7 días.

## Agregar otros productos (solo si tú lo autorizas)

En `config.json` hay una lista de `temas`. Para rastrear algo más, agrega un tema con sus búsquedas y palabras
clave, y déjalo en `"activo": false` hasta que quieras encenderlo.

## Estructura

```
app/scraper.py    Playwright: lee cada tienda, filtra, guarda y evalúa alertas
app/db.py         SQLite (datos/precios.db): productos, precios por día, alertas
app/notificar.py  Telegram / correo / WhatsApp
app/server.py     API local (FastAPI)
web/index.html    Página con filtros, ★ y gráfico (Chart.js)
config.json       Búsquedas, filtros y vigilancia
```

## Más adelante: subirlo a la web

El scraper necesita un navegador real, así que conviene que siga corriendo en tu PC (o en un VPS barato).
La página se puede publicar aparte (Vercel/Render) leyendo una base en la nube (Supabase). Lo vemos cuando quieras.
