"""
test_pipeline.py
Prueba el pipeline completo (parser -> database -> export) contra las
fixtures, SIN necesidad de red. Corré esto para verificar que el proyecto
funciona antes de grabar el video demo o mostrarlo en la propuesta.
"""

import sys
sys.path.insert(0, ".")

from scraper.parser import (
    parse_brand_page, parse_model_page, parse_generation_page,
    parse_variant_specs, detect_propulsion_type,
)
from scraper.database import (
    get_connection, init_db, upsert_brand, upsert_model,
    upsert_generation, upsert_variant, insert_specs,
)
from scraper.export import export_csv, export_json

BASE_URL = "https://www.adac.de"


def main():
    print("=" * 60)
    print("TEST 1: parse_brand_page()")
    print("=" * 60)
    with open("fixtures/audi_brand.html", encoding="utf-8") as f:
        brand_html = f.read()
    models = parse_brand_page(brand_html, BASE_URL)
    assert len(models) == 4, f"Esperaba 4 modelos, encontré {len(models)}"
    for m in models:
        print(f"  ✓ {m['name']:10s} -> {m['url']}")

    print()
    print("=" * 60)
    print("TEST 2: parse_model_page()")
    print("=" * 60)
    with open("fixtures/audi_a4.html", encoding="utf-8") as f:
        model_html = f.read()
    generations = parse_model_page(model_html, BASE_URL)
    assert len(generations) == 4, f"Esperaba 4 generaciones, encontré {len(generations)}"
    for g in generations:
        print(f"  ✓ {g['name']:25s} ({g['year_from']}-{g['year_to']})")

    print()
    print("=" * 60)
    print("TEST 3: parse_generation_page() -- estructura real confirmada")
    print("=" * 60)
    with open("fixtures/audi_a4_b9_generation.html", encoding="utf-8") as f:
        gen_page_html = f.read()
    variant_links = parse_generation_page(gen_page_html, BASE_URL)
    assert len(variant_links) == 3, f"Esperaba 3 variantes, encontré {len(variant_links)}"
    for v in variant_links:
        print(f"  ✓ {v['name']:45s} {v['fuel']:8s} {v['power']}")

    print()
    print("=" * 60)
    print("TEST 4: parse_variant_specs() con nombres de campo REALES")
    print("=" * 60)
    with open("fixtures/audi_a4_variant_real.html", encoding="utf-8") as f:
        real_variant_html = f.read()
    real_specs = parse_variant_specs(real_variant_html)
    real_type = detect_propulsion_type(real_specs)
    print(f"  {len(real_specs)} campos, tipo detectado: {real_type} (vía campo 'Motorart' real)")
    for k, v in real_specs.items():
        print(f"    {k}: {v}")
    assert real_type == "MHEV", f"Esperaba MHEV, obtuve {real_type}"

    print()
    print("=" * 60)
    print("TEST 5: parse_variant_specs() + detect_propulsion_type() (fixtures genéricas)")
    print("=" * 60)
    with open("fixtures/sample_variant_ice.html", encoding="utf-8") as f:
        ice_html = f.read()
    ice_specs = parse_variant_specs(ice_html)
    ice_type = detect_propulsion_type(ice_specs)
    print(f"  ICE  -> {len(ice_specs)} campos, tipo detectado: {ice_type}")
    for k, v in ice_specs.items():
        print(f"           {k}: {v}")
    assert ice_type == "ICE"

    with open("fixtures/sample_variant_bev.html", encoding="utf-8") as f:
        bev_html = f.read()
    bev_specs = parse_variant_specs(bev_html)
    bev_type = detect_propulsion_type(bev_specs)
    print(f"  BEV  -> {len(bev_specs)} campos, tipo detectado: {bev_type}")
    for k, v in bev_specs.items():
        print(f"           {k}: {v}")
    assert bev_type == "BEV"

    print()
    print("=" * 60)
    print("TEST 6: pipeline completo -> SQLite -> CSV/JSON")
    print("=" * 60)
    conn = get_connection("output/test_catalog.db")
    init_db(conn)

    brand_id = upsert_brand(conn, "AUDI", f"{BASE_URL}/.../audi/")
    model_id = upsert_model(conn, brand_id, "A4", f"{BASE_URL}/.../audi/a4/")
    gen_id = upsert_generation(conn, model_id, "A4 B9", 2015, 2018, f"{BASE_URL}/.../b9/")

    variant_id = upsert_variant(conn, gen_id, "2.0 TFSI 190 PS", ice_type, f"{BASE_URL}/.../variant1/")
    insert_specs(conn, variant_id, ice_specs)

    variant2_id = upsert_variant(conn, gen_id, "e-tron 55 quattro", bev_type, f"{BASE_URL}/.../variant2/")
    insert_specs(conn, variant2_id, bev_specs)

    conn.close()
    print("  ✓ Datos insertados en output/test_catalog.db")

    export_csv("output/test_catalog.db", "output/test_catalog.csv")
    export_json("output/test_catalog.db", "output/test_catalog.json")

    print()
    print("=" * 60)
    print("TODOS LOS TESTS PASARON ✓")
    print("=" * 60)


if __name__ == "__main__":
    main()
