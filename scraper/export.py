"""
export.py
Exporta el contenido de la base SQLite a CSV y JSON, con las specs
clave-valor "aplanadas" en un JSON anidado (para JSON) y en filas largas
(para CSV, formato long/tidy -- una fila por cada campo técnico).
"""

import csv
import json
import sqlite3
from pathlib import Path

from .database import get_connection


def _fetch_full_catalog(conn: sqlite3.Connection) -> list[dict]:
    query = """
    SELECT
        b.name AS brand,
        m.name AS model,
        g.name AS generation,
        g.year_from,
        g.year_to,
        v.name AS variant,
        v.propulsion_type,
        v.source_url,
        vs.field_key,
        vs.field_value
    FROM brands b
    JOIN models m ON m.brand_id = b.id
    JOIN generations g ON g.model_id = m.id
    LEFT JOIN variants v ON v.generation_id = g.id
    LEFT JOIN variant_specs vs ON vs.variant_id = v.id
    ORDER BY b.name, m.name, g.name, v.name, vs.field_key
    """
    return [dict(row) for row in conn.execute(query).fetchall()]


def export_csv(db_path: str, out_path: str) -> None:
    conn = get_connection(db_path)
    rows = _fetch_full_catalog(conn)
    conn.close()

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        print(f"Sin datos para exportar (DB vacía: {db_path})")
        return

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"CSV exportado: {out_path} ({len(rows)} filas)")


def export_json(db_path: str, out_path: str) -> None:
    """Exporta en formato anidado: marca -> modelo -> generación -> variante -> specs{}"""
    conn = get_connection(db_path)

    brands = conn.execute("SELECT * FROM brands").fetchall()
    result = []

    for brand in brands:
        brand_dict = {"brand": brand["name"], "models": []}
        models = conn.execute("SELECT * FROM models WHERE brand_id = ?", (brand["id"],)).fetchall()

        for model in models:
            model_dict = {"model": model["name"], "generations": []}
            gens = conn.execute("SELECT * FROM generations WHERE model_id = ?", (model["id"],)).fetchall()

            for gen in gens:
                gen_dict = {
                    "generation": gen["name"],
                    "year_from": gen["year_from"],
                    "year_to": gen["year_to"],
                    "variants": [],
                }
                variants = conn.execute(
                    "SELECT * FROM variants WHERE generation_id = ?", (gen["id"],)
                ).fetchall()

                for variant in variants:
                    specs_rows = conn.execute(
                        "SELECT field_key, field_value FROM variant_specs WHERE variant_id = ?",
                        (variant["id"],),
                    ).fetchall()
                    specs = {r["field_key"]: r["field_value"] for r in specs_rows}

                    gen_dict["variants"].append({
                        "variant": variant["name"],
                        "propulsion_type": variant["propulsion_type"],
                        "specs": specs,
                    })

                model_dict["generations"].append(gen_dict)
            brand_dict["models"].append(model_dict)
        result.append(brand_dict)

    conn.close()

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"JSON exportado: {out_path}")
