"""
database.py
Esquema SQLite para el catálogo de vehículos.

Diseño clave: los campos técnicos ("Technische Daten") varían según el tipo
de propulsión (ICE / PHEV / BEV) -- un motor a combustión tiene "Hubraum"
(cilindrada) y "Kraftstoffverbrauch" (consumo de combustible), mientras que
un eléctrico tiene "Batteriekapazität" (capacidad de batería) y "Reichweite"
(autonomía). En vez de crear una columna por cada campo posible (lo que
generaría decenas de columnas vacías según el tipo), usamos un modelo
clave-valor (EAV: Entity-Attribute-Value) para la tabla de specs.

Esto cumple el requisito del cliente real: "conserve todos los campos,
no codifique las columnas".
"""

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS brands (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    source_url TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    brand_id INTEGER NOT NULL REFERENCES brands(id),
    name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    UNIQUE(brand_id, name)
);

CREATE TABLE IF NOT EXISTS generations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    model_id INTEGER NOT NULL REFERENCES models(id),
    name TEXT NOT NULL,
    year_from INTEGER,
    year_to INTEGER,
    source_url TEXT NOT NULL,
    UNIQUE(model_id, name)
);

CREATE TABLE IF NOT EXISTS variants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    generation_id INTEGER NOT NULL REFERENCES generations(id),
    name TEXT NOT NULL,
    propulsion_type TEXT,          -- 'ICE' | 'PHEV' | 'BEV' | NULL si no se pudo determinar
    source_url TEXT NOT NULL,
    scraped_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(generation_id, name)
);

-- Modelo clave-valor: acá vive la flexibilidad de campos variables por tipo
CREATE TABLE IF NOT EXISTS variant_specs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    variant_id INTEGER NOT NULL REFERENCES variants(id),
    field_key TEXT NOT NULL,       -- ej. 'Leistung', 'Hubraum', 'Batteriekapazität'
    field_value TEXT NOT NULL,     -- se guarda como texto; casteo queda para el consumidor de la data
    UNIQUE(variant_id, field_key)
);

CREATE INDEX IF NOT EXISTS idx_models_brand ON models(brand_id);
CREATE INDEX IF NOT EXISTS idx_generations_model ON generations(model_id);
CREATE INDEX IF NOT EXISTS idx_variants_generation ON variants(generation_id);
CREATE INDEX IF NOT EXISTS idx_specs_variant ON variant_specs(variant_id);
"""


def get_connection(db_path: str = "output/catalog.db") -> sqlite3.Connection:
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()


def upsert_brand(conn: sqlite3.Connection, name: str, source_url: str) -> int:
    conn.execute(
        "INSERT INTO brands (name, source_url) VALUES (?, ?) "
        "ON CONFLICT(name) DO UPDATE SET source_url = excluded.source_url",
        (name, source_url),
    )
    conn.commit()
    return conn.execute("SELECT id FROM brands WHERE name = ?", (name,)).fetchone()["id"]


def upsert_model(conn: sqlite3.Connection, brand_id: int, name: str, source_url: str) -> int:
    conn.execute(
        "INSERT INTO models (brand_id, name, source_url) VALUES (?, ?, ?) "
        "ON CONFLICT(brand_id, name) DO UPDATE SET source_url = excluded.source_url",
        (brand_id, name, source_url),
    )
    conn.commit()
    return conn.execute(
        "SELECT id FROM models WHERE brand_id = ? AND name = ?", (brand_id, name)
    ).fetchone()["id"]


def upsert_generation(
    conn: sqlite3.Connection, model_id: int, name: str,
    year_from: int | None, year_to: int | None, source_url: str
) -> int:
    conn.execute(
        "INSERT INTO generations (model_id, name, year_from, year_to, source_url) "
        "VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(model_id, name) DO UPDATE SET "
        "year_from = excluded.year_from, year_to = excluded.year_to, source_url = excluded.source_url",
        (model_id, name, year_from, year_to, source_url),
    )
    conn.commit()
    return conn.execute(
        "SELECT id FROM generations WHERE model_id = ? AND name = ?", (model_id, name)
    ).fetchone()["id"]


def upsert_variant(
    conn: sqlite3.Connection, generation_id: int, name: str,
    propulsion_type: str | None, source_url: str
) -> int:
    conn.execute(
        "INSERT INTO variants (generation_id, name, propulsion_type, source_url) "
        "VALUES (?, ?, ?, ?) "
        "ON CONFLICT(generation_id, name) DO UPDATE SET "
        "propulsion_type = excluded.propulsion_type, source_url = excluded.source_url",
        (generation_id, name, propulsion_type, source_url),
    )
    conn.commit()
    return conn.execute(
        "SELECT id FROM variants WHERE generation_id = ? AND name = ?", (generation_id, name)
    ).fetchone()["id"]


def insert_specs(conn: sqlite3.Connection, variant_id: int, specs: dict[str, str]) -> None:
    rows = [(variant_id, k, v) for k, v in specs.items()]
    conn.executemany(
        "INSERT INTO variant_specs (variant_id, field_key, field_value) VALUES (?, ?, ?) "
        "ON CONFLICT(variant_id, field_key) DO UPDATE SET field_value = excluded.field_value",
        rows,
    )
    conn.commit()
