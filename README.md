# adac-catalog-scraper

Scraper + base de datos estructurada para el catálogo de vehículos de
[ADAC Autokatalog](https://www.adac.de/rund-ums-fahrzeug/autokatalog/marken-modelle/)
(Alemania). Prueba de concepto construida para evaluar la viabilidad de un
proyecto de extracción de datos a gran escala: marca → modelo → generación →
variante, con ficha técnica completa por variante.

## Por qué este proyecto

Antes de cotizar un trabajo de scraping a gran escala, investigué a mano la
estructura real del sitio (inspección de HTML, verificación de protecciones
anti-bot, chequeo de `robots.txt`) recorriendo **las 4 capas completas** de
la jerarquía: marca → modelo → generación → variante con ficha técnica.
Confirmé que **ninguna de las 4 tiene protección anti-bot agresiva** (sin
Cloudflare challenge, sin captcha, sin bloqueo de IP) — todo el contenido,
incluida la ficha técnica completa de cada variante (motor, consumo,
medidas, seguridad, garantías), se sirve como HTML plano en tablas
estándar, sin depender de JavaScript del lado del cliente. Este repo es la
prueba de esa investigación llevada a código funcional y probado.

## Qué resuelve

- **Scraping respetuoso**: rate limiting con pausas variables, reintentos
  con backoff exponencial, verificación de `robots.txt` antes de cada
  request, User-Agent identificable.
- **Modelo de datos flexible**: los campos técnicos varían según el tipo de
  propulsión (motor a combustión / híbrido enchufable / eléctrico). En vez
  de columnas fijas (que dejarían decenas de NULLs según el tipo), se usa un
  esquema clave-valor (`variant_specs`) — **se conserva cualquier campo que
  aparezca, sin necesidad de tocar el esquema cuando el sitio agrega uno
  nuevo.**
- **Tres formatos de salida**: SQLite (consultable directo), CSV (formato
  "long/tidy", una fila por campo técnico) y JSON (anidado por
  marca/modelo/generación/variante).
- **Reejecutable**: pensado para correr periódicamente (el caso de uso real
  es 1-2 veces al año) sin duplicar datos — usa `UPSERT` en toda la cadena.

## Estructura del proyecto

```
adac-scraper/
├── main.py                  # orquestador (CLI)
├── scraper/
│   ├── fetcher.py            # HTTP + rate limiting + robots.txt
│   ├── parser.py              # extracción con BeautifulSoup
│   ├── database.py            # esquema SQLite + upserts
│   └── export.py              # exportación a CSV/JSON
├── fixtures/                 # HTML de muestra para tests sin red
├── test_pipeline.py          # test de punta a punta contra las fixtures
└── output/                   # DB y exports generados (gitignored)
```

## Cómo correrlo

```bash
pip install -r requirements.txt

# Test completo sin red (usa fixtures/)
python test_pipeline.py

# Scraping real (necesita internet sin restricciones)
python main.py --brand audi --limit 2 --variant-limit 5   # demo rápida
python main.py --brand audi --limit 2                     # 2 modelos, todas sus variantes
python main.py --brand audi                                # marca completa (puede ser lento: cientos de variantes)
python main.py --export                                    # exporta lo scrapeado a CSV/JSON
```

## Estado actual / próximos pasos

Esto es una **prueba de concepto**, no el producto final, pero cubre las 4
capas completas de la jerarquía y está confirmado contra HTML real de
adac.de en cada nivel:

- [x] Parsing de listado de marca → modelos
- [x] Parsing de modelo → generaciones (con rango de años)
- [x] Parsing de generación → variantes (tabla con +200 variantes en
      algunos casos, confirmado con Audi A4 B9 2. Facelift: 92 variantes
      solo en la carrocería Avant)
- [x] Parsing de variante → ficha técnica completa (motor, medidas,
      carrocería, seguridad, garantías, precios — 7 secciones distintas
      confirmadas, todas en tablas de 2 columnas)
- [x] Clasificación de tipo de propulsión vía el campo real "Motorart"
      (ICE, MHEV, HEV, PHEV, BEV, FCEV), con fallback heurístico
- [x] Esquema de base de datos clave-valor para specs variables (no
      hardcodea columnas — soporta cualquier campo nuevo sin migración)
- [x] Exportación a SQLite/CSV/JSON
- [x] Rate limiting, reintentos, respeto de robots.txt
- [x] Suite de tests (`test_pipeline.py`) cubriendo las 4 capas contra
      fixtures reconstruidas de HTML real

Pendiente para un proyecto de producción a escala completa (no bloqueante
para cotizar, son ajustes de volumen/operación):

- [ ] Medir tiempo real de ejecución a escala completa: con rate limiting
      responsable (1.5-3s entre requests) y cientos de variantes por
      generación en marcas grandes (VW, Mercedes, BMW), una corrida
      completa de todas las marcas puede tardar horas — hay que
      dimensionar esto con el cliente antes de cotizar un precio fijo.
- [ ] Decidir si conviene paralelizar con múltiples workers (respetando
      igual el rate limit total) para acortar el tiempo de ejecución en
      corridas grandes.

## Notas técnicas

- El fetcher respeta `robots.txt` automáticamente (usa
  `urllib.robotparser`) y aborta cualquier ruta no permitida.
- Las pausas entre requests son aleatorias (1.5–3s) para no generar un
  patrón de tráfico perfectamente regular.
- Ante un `403`, el fetcher no reintenta agresivamente — lo reporta y sigue
  con la siguiente URL, para no arriesgar un bloqueo de IP más amplio.
