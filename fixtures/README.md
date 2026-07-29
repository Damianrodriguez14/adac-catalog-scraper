# Fixtures

Estas son páginas HTML reales descargadas de adac.de (vía fetch), usadas para
desarrollar y probar el parser sin golpear el sitio en cada corrida de tests.

- `audi_brand.html` — listado de modelos de la marca Audi
- `audi_a4.html` — página del modelo A4 con sus generaciones (Baureihengenerationen)

Para producción, el scraper baja estas páginas en vivo con `requests`.
