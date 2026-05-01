# Data Version Note

## Canonical State

As of `2026-04-30`, published assets are rebuilt from a single canonical metrics layer:

- shared code: [`canonical_metrics.py`](/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/canonical_metrics.py)
- rebuild entrypoint: [`scripts/rebuild_public_assets.py`](/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/scripts/rebuild_public_assets.py)
- correction log: [`CORRECTIONS.md`](/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/CORRECTIONS.md)

## Active Research Layers

### Three-period public layer

Used by `docs/` and `data/explorer_data.json`.

| Period | Dates | Audited |
| --- | --- | ---: |
| `P0` | 2023-05-01 -> 2023-10-31 | 27,916 |
| `P1` | 2023-11-09 -> 2024-04-25 | 26,342 |
| `P2` | 2025-07-01 -> 2025-12-15 | 25,247 |

Total: `79,505` audited articles.

### Two-period source-audit layer

Used by `data/corpus_fast.csv` and `dashboard/`.

| Stage | Count |
| --- | ---: |
| Collected URLs | 51,667 |
| Audited HTML | 51,589 |
| Unavailable during audit | 78 |
| No ATO subset | 39,230 |

## Current Definitions

- `parket`: official URL + `source_count <= 1` + `non_official_source_count == 0`
- `balance`: official URL + `non_official_source_count == 0`

These formulas are now applied consistently across rebuilt JSON and CSV outputs.

## Why This Note Exists

Earlier repository states mixed:

- a three-period public comparison in `docs/`
- a two-period audit corpus in `README`, `VERSION_NOTE`, and `dashboard/`
- multiple parser/classifier versions with inconsistent formulas

This note marks the point where those branches were made explicit instead of being conflated.
