"""
parser.py
Extracción de datos desde el HTML de ADAC con BeautifulSoup.

CONFIRMADO CONTRA HTML REAL DE ADAC (investigación completa, incluye las
4 capas de la jerarquía):
  1. Marca -> modelos           (parse_brand_page)
  2. Modelo -> generaciones     (parse_model_page)
  3. Generación -> variantes    (parse_generation_page)
  4. Variante -> ficha técnica  (parse_variant_specs)

Las 4 páginas se sirven como HTML plano, sin JavaScript del lado del
cliente y sin protección anti-bot detectada (sin Cloudflare challenge,
sin captcha). La tabla de "Technische Daten" viene organizada en
secciones (Allgemein, Motor und Antrieb, Maße und Gewichte, etc.), cada
una como una tabla de 2 columnas "Kategorie | Herstellerangabe".
"""

import re
from bs4 import BeautifulSoup

BRAND_MODEL_LINK_RE = re.compile(
    r"/rund-ums-fahrzeug/autokatalog/marken-modelle/([\w-]+)/([\w-]+)/?$"
)
GENERATION_LINK_RE = re.compile(
    r"/rund-ums-fahrzeug/autokatalog/marken-modelle/[\w-]+/[\w-]+/([\w-]+)/?$"
)
VARIANT_LINK_RE = re.compile(
    r"/rund-ums-fahrzeug/autokatalog/marken-modelle/[\w-]+/[\w-]+/[\w-]+/(\d+)/?$"
)
YEAR_RANGE_RE = re.compile(r"(\d{4})\s*-\s*(\d{4})?")

MOTORART_MAP = {
    "otto": "ICE",
    "diesel": "ICE",
    "gas": "ICE",
    "wankel": "ICE",
    "otto (mild-hybrid)": "MHEV",
    "diesel (mild-hybrid)": "MHEV",
    "voll-hybrid": "HEV",
    "plugin-hybrid": "PHEV",
    "elektro": "BEV",
    "wasserstoff (e-motor)": "FCEV",
}


def parse_brand_page(html: str, base_url: str) -> list[dict]:
    """Devuelve [{name, url}] para cada modelo listado en la página de marca."""
    soup = BeautifulSoup(html, "lxml")
    models = []
    seen = set()

    for a in soup.select("a[href*='/autokatalog/marken-modelle/']"):
        href = a.get("href", "")
        match = BRAND_MODEL_LINK_RE.search(href)
        if not match:
            continue
        model_slug = match.group(2)
        if model_slug in seen:
            continue
        seen.add(model_slug)

        text = a.get_text(strip=True)
        # El texto suele venir como "A4Generationen" pegado -- limpiamos el sufijo
        name = re.sub(r"\d*\s*Generation(en)?$", "", text).strip() or model_slug.upper()

        full_url = href if href.startswith("http") else base_url.rstrip("/") + href
        models.append({"name": name, "url": full_url})

    return models


def parse_model_page(html: str, base_url: str) -> list[dict]:
    """Devuelve [{name, url, year_from, year_to}] para cada generación del modelo."""
    soup = BeautifulSoup(html, "lxml")
    generations = []
    seen = set()

    for a in soup.select("a[href*='/autokatalog/marken-modelle/']"):
        href = a.get("href", "")
        match = GENERATION_LINK_RE.search(href)
        if not match:
            continue
        if href in seen:
            continue
        seen.add(href)

        block_text = a.get_text(" ", strip=True)
        year_match = YEAR_RANGE_RE.search(block_text)
        year_from = int(year_match.group(1)) if year_match else None
        year_to = int(year_match.group(2)) if year_match and year_match.group(2) else None

        # Nombre = texto antes del rango de años
        name = block_text
        if year_match:
            name = block_text[: year_match.start()].strip()
        name = name or match.group(1)

        full_url = href if href.startswith("http") else base_url.rstrip("/") + href
        generations.append(
            {"name": name, "url": full_url, "year_from": year_from, "year_to": year_to}
        )

    return generations


def parse_generation_page(html: str, base_url: str) -> list[dict]:
    """
    Devuelve [{name, url, fuel, power, price}] para cada variante listada
    en la tabla de una página de generación.

    Confirmado contra HTML real: la página de generación trae una tabla
    markdown-style con columnas Fahrzeug | Kraftstoff | Leistung |
    Listenpreis | (comparar), agrupada por carrocería (A4 Limousine, A4
    Avant, etc.). Cada celda "Fahrzeug" es un link a la ficha técnica
    (URL terminada en ID numérico).
    """
    soup = BeautifulSoup(html, "lxml")
    variants = []
    seen = set()

    for a in soup.select("a[href*='/autokatalog/marken-modelle/']"):
        href = a.get("href", "")
        if not VARIANT_LINK_RE.search(href):
            continue
        if href in seen:
            continue
        seen.add(href)

        name = a.get_text(strip=True)
        full_url = href if href.startswith("http") else base_url.rstrip("/") + href

        # Los datos de combustible/potencia/precio están en las celdas
        # hermanas de la misma fila <tr> -- si el parser de la tabla no
        # los captura acá (varía según cómo BeautifulSoup arme el árbol
        # sobre el markdown-table), igual se pueden sacar de
        # parse_variant_specs() más adelante, así que no son bloqueantes.
        row = a.find_parent("tr")
        fuel = power = price = None
        if row:
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if len(cells) >= 4:
                fuel, power, price = cells[1], cells[2], cells[3]

        variants.append({
            "name": name, "url": full_url,
            "fuel": fuel, "power": power, "price": price,
        })

    return variants


def parse_variant_specs(html: str) -> dict:
    """
    Extrae specs clave-valor de una página de ficha técnica (variante).

    CONFIRMADO contra HTML real de ADAC (ej. Audi A1 1.4 TFSI Ambition,
    /audi/a1/8x/222372/): la ficha técnica viene organizada en 8 secciones
    (Allgemein, Motor und Antrieb, Maße und Gewichte, Karosserie und
    Fahrwerk, Messwerte Hersteller, Sicherheitsausstattung,
    Herstellergarantien, Preise und Ausstattung), cada una como tabla de
    2 columnas "Kategorie | Herstellerangabe" -- exactamente el Patrón 1
    de abajo. El Patrón 2 (dl/dt/dd) se deja como fallback defensivo por
    si alguna variante particular usa un layout distinto.
      1. Tablas <table> con filas de 2 celdas (clave | valor)  <- patrón real
      2. Listas de definición <dl><dt>clave</dt><dd>valor</dd></dl>  <- fallback
    """
    soup = BeautifulSoup(html, "lxml")
    specs = {}

    # Patrón 1: tablas de 2 columnas
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            # Salteamos la fila de encabezado (todo <th>, ej. "Kategorie |
            # Herstellerangabe") -- solo nos interesan filas de datos con
            # al menos una <td>.
            if not row.find_all("td"):
                continue
            cells = row.find_all(["td", "th"])
            if len(cells) == 2:
                key = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                if key and value:
                    specs[key] = value

    # Patrón 2: definition lists
    for dl in soup.find_all("dl"):
        keys = dl.find_all("dt")
        values = dl.find_all("dd")
        for k, v in zip(keys, values):
            key = k.get_text(strip=True)
            value = v.get_text(strip=True)
            if key and value:
                specs[key] = value

    return specs


def detect_propulsion_type(specs: dict) -> str | None:
    """
    Clasifica el tipo de propulsión usando el campo 'Motorart' -- confirmado
    contra la taxonomía real que usa ADAC en sus filtros (Otto, Diesel,
    Otto (Mild-Hybrid), PlugIn-Hybrid, Elektro, etc.), mapeada a categorías
    estándar en MOTORART_MAP.

    Fallback: si 'Motorart' no vino en las specs (variante rara / campo
    faltante), usa la heurística anterior por palabras clave como red de
    seguridad, para no dejar el campo vacío.
    """
    motorart = specs.get("Motorart", "").strip().lower()
    if motorart in MOTORART_MAP:
        return MOTORART_MAP[motorart]

    # Fallback heurístico
    joined = " ".join(specs.keys()).lower()
    has_battery = any(k in joined for k in ["batterie", "akku", "reichweite elektrisch"])
    has_fuel = any(k in joined for k in ["kraftstoff", "hubraum", "tankvolumen"])
    if has_battery and has_fuel:
        return "PHEV"
    if has_battery and not has_fuel:
        return "BEV"
    if has_fuel:
        return "ICE"
    return None
