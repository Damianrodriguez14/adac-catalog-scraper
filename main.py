"""
main.py
Orquesta el scraping completo: marca -> modelos -> generaciones -> (variantes).

Uso:
    python main.py --brand audi                # scrapea una marca completa
    python main.py --brand audi --limit 2       # solo los primeros 2 modelos (demo rápida)
    python main.py --export                     # exporta lo que ya está en la DB a CSV/JSON

Este script está pensado para correr en TU máquina (no en un sandbox con red
restringida) porque necesita salir a internet libremente hacia adac.de.
"""

import argparse
import logging
import sys

sys.path.insert(0, "scraper")

from scraper.fetcher import Fetcher, RobotsBlocked, BASE_URL
from scraper.parser import (
    parse_brand_page, parse_model_page, parse_generation_page,
    parse_variant_specs, detect_propulsion_type,
)
from scraper.database import (
    get_connection, init_db, upsert_brand, upsert_model,
    upsert_generation, upsert_variant, insert_specs,
)
from scraper.export import export_csv, export_json

log = logging.getLogger("main")


def scrape_brand(
    brand_slug: str,
    limit: int | None = None,
    db_path: str = "output/catalog.db",
    variant_limit: int | None = None,
):
    fetcher = Fetcher()
    conn = get_connection(db_path)
    init_db(conn)

    brand_url = f"{BASE_URL}/rund-ums-fahrzeug/autokatalog/marken-modelle/{brand_slug}/"
    log.info("Descargando marca: %s", brand_url)

    try:
        html = fetcher.get(brand_url)
    except RobotsBlocked as e:
        log.error(str(e))
        return

    if html is None:
        log.error("No se pudo descargar la página de marca. Abortando.")
        return

    brand_id = upsert_brand(conn, brand_slug.upper(), brand_url)
    models = parse_brand_page(html, BASE_URL)
    log.info("Encontrados %d modelos para %s", len(models), brand_slug)

    if limit:
        models = models[:limit]
        log.info("Modo demo: limitando a %d modelos", limit)

    for model in models:
        log.info("  Modelo: %s -> %s", model["name"], model["url"])
        model_id = upsert_model(conn, brand_id, model["name"], model["url"])

        try:
            model_html = fetcher.get(model["url"])
        except RobotsBlocked as e:
            log.warning("  Saltando modelo (robots.txt): %s", e)
            continue

        if model_html is None:
            log.warning("  No se pudo descargar %s, se sigue con el próximo", model["url"])
            continue

        generations = parse_model_page(model_html, BASE_URL)
        log.info("  %d generaciones encontradas", len(generations))

        for gen in generations:
            gen_id = upsert_generation(
                conn, model_id, gen["name"], gen["year_from"], gen["year_to"], gen["url"]
            )
            log.info("    Generación: %s (%s-%s)", gen["name"], gen["year_from"], gen["year_to"])

            try:
                gen_html = fetcher.get(gen["url"])
            except RobotsBlocked as e:
                log.warning("    Saltando generación (robots.txt): %s", e)
                continue

            if gen_html is None:
                log.warning("    No se pudo descargar %s, se sigue con la próxima", gen["url"])
                continue

            variant_links = parse_generation_page(gen_html, BASE_URL)
            log.info("    %d variantes encontradas", len(variant_links))

            if variant_limit:
                variant_links = variant_links[:variant_limit]
                log.info("    Modo demo: limitando a %d variantes", variant_limit)

            for vlink in variant_links:
                try:
                    variant_html = fetcher.get(vlink["url"])
                except RobotsBlocked as e:
                    log.warning("      Saltando variante (robots.txt): %s", e)
                    continue

                if variant_html is None:
                    log.warning("      No se pudo descargar %s", vlink["url"])
                    continue

                specs = parse_variant_specs(variant_html)
                propulsion = detect_propulsion_type(specs)
                variant_id = upsert_variant(conn, gen_id, vlink["name"], propulsion, vlink["url"])
                insert_specs(conn, variant_id, specs)
                log.info("      Variante: %s [%s] (%d campos)", vlink["name"], propulsion, len(specs))

    conn.close()
    log.info("Listo. Datos guardados en %s", db_path)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    ap = argparse.ArgumentParser(description="Scraper del catálogo ADAC")
    ap.add_argument("--brand", help="slug de marca, ej: audi, vw, bmw")
    ap.add_argument("--limit", type=int, help="límite de modelos a scrapear (para demo rápida)")
    ap.add_argument("--variant-limit", type=int, help="límite de variantes por generación (para demo rápida)")
    ap.add_argument("--export", action="store_true", help="exporta la DB actual a CSV/JSON")
    ap.add_argument("--db", default="output/catalog.db", help="ruta a la base SQLite")
    args = ap.parse_args()

    if args.export:
        export_csv(args.db, "output/catalog.csv")
        export_json(args.db, "output/catalog.json")
    elif args.brand:
        scrape_brand(args.brand, limit=args.limit, db_path=args.db, variant_limit=args.variant_limit)
    else:
        ap.print_help()
