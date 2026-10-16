"""Cuántos sobres (booster packs) trae un producto, para calcular el precio por sobre.

Primero busca la cantidad escrita en el nombre ("36 sobres", "3-pack", "2 paquetes").
Si no está, usa el contenido típico del tipo de producto (ETB = 9, Booster Box = 36, ...).
Devuelve (cantidad, estimado) o (None, False) si no se puede saber (lotes, mazos, accesorios...).
"""
import re

SUSTANTIVOS = r"(?:sobres?|boosters?(?: packs?)?|booster packs?|packs?|paquetes?|refuerzos?|potenciadores?)"
EXPLICITO = [
    # "pack de 10", "paquete de 3" (pero no "paquete de 10 cartas")
    re.compile(r"\b(?:packs?|paquetes?)\s+de\s+(\d{1,2})\b(?!\s*cartas)"),
    # "36 sobres", "3-pack", "4 booster", "con 4 potenciadores" (no "SV3 pack")
    re.compile(r"(?<![\w.])(\d{1,2})\s*-?\s*(?:x\s*)?" + SUSTANTIVOS + r"\b"),
    re.compile(r"\bx\s*(\d{1,2})\s*(?:sobres?|boosters?)\b"),
]

ETB = r"elite trainer|\betb\b|caja de entrenador|caja de entrenamiento|caja [eé]lite"

# Contenido típico por tipo, en orden: gana la primera regla que calce. None = no se puede saber.
TIPICOS = [
    (r"slim|paquete de sobres|premium trainer box", None),
    (r"half booster box|media caja", 18),
    (r"booster box|caja de sobres|caja de refuerzo|caja de presentaci[oó]n|expositor|\bdisplay\b", 36),
    (ETB, 9),
    (r"booster bundle|\bbundle\b", 6),
    (r"build ?(&|and|y) ?battle", 4),
    (r"mini ?tin|mini ?lata|lata mini|tin mini", 2),
    (r"pok[eé] ?ball tin", 3),
    (r"\btin\b|\blata\b", 4),
    (r"sleeved|booster individual|\bsobre\b|paquete (de )?refuerzo|pack de refuerzo|paquete expansi[oó]n"
     r"|\bbooster\b(?! box| bundle)", 1),
    (r"blister", 1),
]

SIN_SOBRES = ("Lotes / Cartas sueltas", "Accesorios")


def estimar_sobres(nombre: str, categoria: str) -> tuple[int | None, bool]:
    if categoria in SIN_SOBRES:
        return None, False
    n = (nombre or "").lower()
    for rx in EXPLICITO:
        m = rx.search(n)
        if m and 1 <= int(m.group(1)) <= 40:
            return int(m.group(1)), False
    if categoria in ("Mazos / Battle", "Colección / Premium", "Otros") and not re.search(
            r"build ?(&|and|y) ?battle|\btin\b|\blata\b|" + ETB, n):
        return None, False  # el contenido varía demasiado para adivinarlo
    for rx, cant in TIPICOS:
        if re.search(rx, n):
            return cant, cant is not None
    return None, False
