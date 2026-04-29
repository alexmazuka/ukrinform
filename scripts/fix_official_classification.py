"""
v3 fix: word-boundary classification of official_slug.

CRITICAL BUG IN v1/v2: substring matching caused 42% false positives.
Examples:
  - 'amerikanskimi' contained 'mer' → flagged as Mayor (false)
  - 'pomerla' contained 'mer' → flagged as Mayor (false)
  - 'propusku' contained 'opu' → flagged as Office of President (false)
  - 'vijskova' contained 'ova' → flagged as Oblast Mil. Admin. (false)

Fix: split slug by hyphens, match against full words or known prefixes.
"""
from __future__ import annotations
import csv, re

BASE = '/Users/oleksiymatsuka/Desktop/ukrinform-imi-study'
INPUT = f'{BASE}/data/corpus_v2_parsed.csv'
OUTPUT = f'{BASE}/data/corpus_v3_parsed.csv'

# v3: structured by category, with word-boundary matching
OFFICIAL_PATTERNS = {
    'Президент / ОП': {
        'exact': ['zelenskij', 'zelensky', 'prezident', 'opu', 'yermak', 'ermak'],
        'prefix': ['zelensk', 'prezident', 'ofis-prezidenta', 'yermak', 'ermak'],
    },
    'Уряд': {
        # Forms of "уряд" (urad, uradu, uryad) and "Кабмін"
        'exact': ['kabmin', 'kabminu', 'kabministr', 'uryad', 'uryadu', 'urad', 'uradu',
                  'uradi', 'uradova', 'uradovij', 'smygal', 'shmygal',
                  'premyer', 'premier', 'svyrydenko', 'svyridenko'],
        'prefix': ['kabmin', 'uryad', 'urad', 'smygal', 'shmygal', 'premyer', 'premier',
                   'svyriden', 'svyryden'],
    },
    'Парламент': {
        'exact': ['rada', 'radoyu', 'radoju', 'verhovna', 'verhovnoyu', 'verhovnoju',
                  'nardep', 'nardepy', 'deputat', 'deputaty', 'komitet', 'stefancuk'],
        'prefix': ['verhovn', 'nardep', 'stefancuk'],
    },
    'Міністерства': {
        'exact': ['ministr', 'ministra', 'ministry', 'ministrom', 'ministerstvo',
                  'ministerstva', 'mzs', 'mvs', 'minfin', 'minekonom', 'minoboroni',
                  'mincifri', 'minkult', 'minstratehprom', 'minekoenergo',
                  'umerov', 'umerova', 'kuleba', 'kulebu', 'sybiha', 'shmygal',
                  'shmyhalja', 'fedorov', 'fedorova'],
        'prefix': ['ministr', 'ministerstv', 'minoboron', 'minekonom', 'minfin',
                   'mincifr', 'minkult', 'minstrateh', 'umerov', 'kuleb', 'sybih',
                   'fedorov'],
    },
    'Силовий блок': {
        'exact': ['genshtab', 'zsu', 'sbu', 'gur', 'dpsu', 'dsns', 'syrskij', 'sirskij',
                  'syrskogo', 'sirskogo', 'zaluzhnij', 'zaluzhnogo', 'budanov', 'budanova'],
        'prefix': ['genshtab', 'zaluzhn', 'syrsk', 'sirsk', 'budanov'],
        'multi_word': ['sili-oboroni', 'syl-oborony'],
    },
    'Регіональна влада': {
        'exact': ['ova', 'kmva', 'kmda', 'oblrada', 'miskrada'],
        'prefix': ['oblrada', 'miskrada'],
    },
    'Держструктури': {
        'exact': ['ukrzaliznicia', 'ukrzaliznycia', 'ukrenergo', 'naftogaz', 'oschadbank',
                  'pryvatbank', 'pension', 'nbu', 'nabu', 'sap'],
        'prefix': ['ukrzaliznic', 'ukrzaliznyc', 'ukrenergo', 'naftogaz'],
    },
}

def classify_official(slug):
    """Word-boundary classification. Returns list of categories."""
    words = [w for w in re.split(r'[-_.]', slug.lower()) if w]
    if not words:
        return []

    matched_categories = []

    for category, patterns in OFFICIAL_PATTERNS.items():
        # Exact word match
        if any(w in patterns.get('exact', []) for w in words):
            matched_categories.append(category)
            continue

        # Prefix match (word starts with marker, marker length >= 5)
        prefix_match = False
        for w in words:
            for p in patterns.get('prefix', []):
                if len(p) >= 5 and w.startswith(p):
                    prefix_match = True
                    break
            if prefix_match:
                break
        if prefix_match:
            matched_categories.append(category)
            continue

        # Multi-word patterns (e.g. "sili-oboroni")
        for mw in patterns.get('multi_word', []):
            if mw in slug.lower():
                matched_categories.append(category)
                break

    return matched_categories


def main():
    rows = list(csv.DictReader(open(INPUT)))

    # Classify with v3
    v1_official = 0
    v3_official = 0
    flipped_to_false = 0
    flipped_to_true = 0

    for r in rows:
        slug = r['slug_text']
        cats = classify_official(slug)
        official_v3 = len(cats) > 0
        official_v1 = r['official_slug'] == 'True'

        if official_v1:
            v1_official += 1
        if official_v3:
            v3_official += 1

        if official_v1 and not official_v3:
            flipped_to_false += 1
        if not official_v1 and official_v3:
            flipped_to_true += 1

        # Add v3 columns
        r['official_v3'] = str(official_v3)
        r['categories_v3'] = '|'.join(cats)

        # Recalculate parket_v3 using v3 official + v2 source counts
        if r.get('sc_v2'):
            sc = int(r['sc_v2'])
            noc = int(r.get('noc_v2', 0))
            r['parket_v3'] = str(official_v3 and sc <= 1 and noc == 0)
            r['balance_v3'] = str(official_v3 and noc == 0 and sc <= 1)
        else:
            r['parket_v3'] = 'False'
            r['balance_v3'] = 'False'

    print(f"=" * 70)
    print(f"V3 CLASSIFICATION FIX")
    print(f"=" * 70)
    print(f"\nV1 official_slug=True: {v1_official:,}")
    print(f"V3 official=True:       {v3_official:,}")
    print(f"  Зменшення: {v1_official - v3_official:,} ({(v1_official-v3_official)/v1_official*100:.1f}%)")
    print(f"\n  Перекинули у False (були хибно офіц.): {flipped_to_false:,}")
    print(f"  Перекинули у True (тепер ловимо краще): {flipped_to_true:,}")

    # Save
    fieldnames = list(rows[0].keys())
    with open(OUTPUT, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"\nSaved: {OUTPUT}")

    # Compute v3 parket rates
    audited = [r for r in rows if r['audited']=='True' and r.get('sc_v2')]
    p1 = [r for r in audited if r['period_slug']=='before_exclusion_matsuka']
    p2 = [r for r in audited if r['period_slug']=='before_reinclusion_after_departure']
    p1_no_ato = [r for r in p1 if r['rubric']!='rubric-ato']
    p2_no_ato = [r for r in p2 if r['rubric']!='rubric-ato']

    print(f"\n{'='*70}")
    print(f"V3 PARKET RATES")
    print(f"{'='*70}")
    for label, arts in [('P1 (Matsuka, with ATO)', p1), ('P2 (after, with ATO)', p2),
                         ('P1 no-ATO', p1_no_ato), ('P2 no-ATO', p2_no_ato)]:
        if not arts: continue
        pk = sum(1 for r in arts if r['parket_v3']=='True')
        print(f"  {label:<30} n={len(arts):>6,} parket={pk/len(arts)*100:>5.2f}% ({pk:,})")

if __name__ == '__main__':
    main()
