# Corrections Log

## 2026-04-30

This repository now uses a single canonical metrics layer in [`canonical_metrics.py`](/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/canonical_metrics.py) for all rebuilt public assets.

### What was corrected

1. Official source detection in `scripts/audit_full_corpus.py`
   The old audit matched transliterated slug markers against Cyrillic source names inside article text. This systematically undercounted `official_source_count` in `data/corpus_fast.csv`.

2. Official URL classification
   The old substring matcher treated fragments like `mer`, `opu`, or `ova` as official signals even inside unrelated words. The canonical classifier now uses word boundaries and known prefixes.

3. `parket` vs `balance`
   Earlier v2/v3 scripts used the same formula for both metrics. They are now separated:
   - `parket`: official URL + `source_count <= 1` + `non_official_source_count == 0`
   - `balance`: official URL + `non_official_source_count == 0`

4. Public assets split by scope
   The repo had mixed two different products:
   - a three-period public comparison (`79,505` audited articles in `docs/`)
   - a two-period source-audit subset (`51,589` audited articles in `data/corpus_fast.csv` and `dashboard/`)

   The corrected version keeps both visible, but labels them consistently.

### Canonical headline numbers after rebuild

- Three periods, without ATO: `5.80% -> 4.97% -> 4.14%` parket
- Three periods, with ATO: `5.87% -> 5.12% -> 4.67%` parket
- Two-period audited subset, without ATO: `4.97%` vs `4.14%`
- Two-period audited subset, with ATO: `5.12%` vs `4.67%`

### Files regenerated from the canonical layer

- `/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/data/corpus_fast.csv`
- `/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/data/explorer_data.json`
- `/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/docs/explorer_data.json`
- `/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/dashboard/explorer_data.json`
- `/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/docs/graph_data.json`
- `/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/dashboard/graph_data.json`
- `/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/data/statistical_tests_v3.json`
- `/Users/oleksiymatsuka/Desktop/ukrinform-imi-study/data/statistical_tests_v3_three_periods.json`

### Rebuild command

```bash
python3 scripts/rebuild_public_assets.py
```
