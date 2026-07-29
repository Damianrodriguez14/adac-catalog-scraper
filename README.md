## How to run it

```bash
pip install -r requirements.txt

# Full test with no network needed (uses fixtures/)
python test_pipeline.py

# Real scraping (needs unrestricted internet access)
python main.py --brand audi --limit 2 --variant-limit 5   # quick demo
python main.py --brand audi --limit 2                     # 2 models, all their variants
python main.py --brand audi                                # full brand (can be slow: hundreds of variants)
python main.py --export                                    # exports scraped data to CSV/JSON
```

## Current status / next steps

This is a **proof of concept**, not the final product, but it covers
all 4 layers of the hierarchy and has been confirmed against real
adac.de HTML at every level:

- [x] Brand listing → models parsing
- [x] Model → generations parsing (with year range)
- [x] Generation → variants parsing (table with 200+ variants in some
      cases, confirmed with Audi A4 B9 2nd Facelift: 92 variants just
      in the Avant body style)
- [x] Variant → full technical spec sheet parsing (engine, dimensions,
      body, safety, warranties, pricing — 7 distinct sections
      confirmed, all in 2-column tables)
- [x] Propulsion type classification via the real "Motorart" field
      (ICE, MHEV, HEV, PHEV, BEV, FCEV), with heuristic fallback
- [x] Key-value database schema for variable specs (no hardcoded
      columns — supports any new field with no migration needed)
- [x] Export to SQLite/CSV/JSON
- [x] Rate limiting, retries, robots.txt compliance
- [x] Test suite (`test_pipeline.py`) covering all 4 layers against
      fixtures reconstructed from real HTML

Pending for a full-scale production project (not blocking for quoting,
these are volume/operations adjustments):

- [ ] Measure real execution time at full scale: with responsible rate
      limiting (1.5-3s between requests) and hundreds of variants per
      generation for large brands (VW, Mercedes, BMW), a full run
      across all brands could take hours — this needs to be sized with
      the client before quoting a fixed price.
- [ ] Decide whether to parallelize with multiple workers (while still
      respecting the overall rate limit) to shorten execution time on
      large runs.

## Technical notes

- The fetcher automatically respects `robots.txt` (uses
  `urllib.robotparser`) and aborts any disallowed path.
- Delays between requests are randomized (1.5–3s) to avoid generating
  a perfectly regular traffic pattern.
- On a `403`, the fetcher doesn't retry aggressively — it reports it
  and moves on to the next URL, to avoid risking a broader IP block.