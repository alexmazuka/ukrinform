"""
Improved source parser — v2.
Addresses methodological limitation found in audit (Apr 19, 2026).

New patterns captured:
1. HEADLINE source: "— Генштаб" / "- МЗС Франції" at end of title
2. "Про це повідомляє X" / "Про це йдеться в Y"
3. "Як передає Укрінформ, про це X повідомили..."
4. "повідомили в Y" / "зазначили в Y" / "уточнили в Z"
5. OG description source (meta tag often has cleaner source attribution)

Runs on full corpus, produces new parquet classification.
"""
from __future__ import annotations
import csv, json, re, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parent.parent
CSV = BASE / 'data' / 'corpus_fast.csv'
OUT = BASE / 'data' / 'corpus_v2_parsed.csv'
PROGRESS = BASE / 'data' / 'reparse_progress.json'

UA = 'Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'

# ==== EXISTING PATTERNS (from v1) ====
REPORTING_VERBS = (
    'заявив', 'заявила', 'повідомив', 'повідомила', 'сказав', 'сказала',
    'наголосив', 'наголосила', 'зауважив', 'зауважила', 'додав', 'додала',
    'підкреслив', 'підкреслила', 'відзначив', 'відзначила', 'розповів',
    'розповіла', 'написав', 'написала', 'зазначив', 'зазначила'
)
PERSON_RE = re.compile(r'([А-ЯІЇЄҐA-Z][^.!?\n]{1,90}?)\s+(?:' + '|'.join(REPORTING_VERBS) + r')\b')
LEADING_RE = re.compile(r'(?:За словами|За даними|Як повідомив|Як повідомила|Як повідомили|Як зазначив|Як зазначила|Повідомляє)\s+([^,.;:\n]{1,90})')

# ==== NEW PATTERNS (v2) ====
# 1. Headline source: "... — Author" or "... - Author" at end
HEADLINE_SRC_RE = re.compile(r'\s[—–-]\s*([А-ЯІЇЄҐA-Z][А-ЯІЇЄҐа-яіїєґA-Za-z\s]{2,60}?)\s*$')

# 2. "Про це повідомляє/йдеться/зазначає X"
PRO_CE_RE = re.compile(
    r'[Пп]ро це (?:повідомляє|повідомили|йдеться\s+(?:в|у)|зазначається\s+(?:в|у)|сказано\s+(?:в|у)|(?:розповів|розповіла))\s+([А-ЯІЇЄҐA-Z][^.!?\n]{2,80})'
)

# 3. "Як передає X, про це Y повідомили/заявили..."
AS_TRANSMITS_RE = re.compile(
    r'[Яя]к (?:передає|передають|пише|пишуть|повідомляє|повідомляють)\s+Укрінформ,?\s*про це\s+([А-ЯІЇЄҐA-Z][^.!?\n]{2,70})'
)

# 4. "повідомили/зазначили/уточнили в X"
IN_ORG_RE = re.compile(
    r'(?:повідомили|зазначили|уточнили|наголосили|підкреслили|сказали|вважають|додали)\s+(?:в|у|на)\s+([А-ЯІЇЄҐA-Z][^.!?\n]{2,50})'
)

# 5. OG description ending dash-source: "... — Name" (Ukrinform puts source in og:desc too)
OG_SRC_RE = re.compile(r'[—–]\s*([А-ЯІЇЄҐA-Z][^.!?\n—–]{2,60}?)\s*\.?$')

OFFICIAL_MARKERS = {
    'Президент / ОП': ['zelensk','prezident','ofis-prezidenta','opu','yermak','ermak','єрмак','зеленськ'],
    'Уряд / Кабмін': ['kabmin','uryad','smygal','premyer','premier','шмигал','кабмін','уряд','прем\'єр'],
    'Парламент': ['verhovn','rada','nardep','deputat','komitet','верховна рада','нардеп','парламент'],
    'Міністерства': ['ministr','ministerstvo','mzs','minoboroni','mvs','minekonom','minfin','mon','mincifri',
                    'міністр','міноборон','мзс','мвс','мінфін','мінекономіки','кулеба','сибіга','умєров'],
    'Силовий блок': ['genshtab','zsu','sbu','gur','dpsu','dsns','sili-oboroni',
                    'генштаб','зсу','сбу','гур','сили оборони','сирськ'],
    'Регіональна влада': ['ova','kmva','kmda','oblrada','miskrada','mer','ова','кмда','облрада','мер'],
    'Держструктури': ['ukrzaliznic','ukrenergo','naftogaz','fond-derzmajna','pensijn','podatkov','mitnic',
                     'укрзалізниц','укренерго','нафтогаз','фонд держмайна','національний банк','нбу']
}
ALL_OFFICIAL = [m for lst in OFFICIAL_MARKERS.values() for m in lst]


def normalize(t):
    c = re.sub(r'\s+', ' ', t.replace('\xa0', ' ')).strip(' ,;:.!?"""«»()[]—–-')
    if len(c.split()) > 10 or len(c) < 3: return ''
    return c


def classify_source(text):
    """Return 'official' / 'non_official' / None."""
    t = text.lower()
    if any(m in t for m in ALL_OFFICIAL):
        return 'official'
    return 'non_official'


def extract_sources_v2(title, og_desc, body):
    """Returns (total, official, non_official, extracted_list)."""
    sources = {}  # normalized -> type

    # V1 patterns (in body)
    for raw in PERSON_RE.findall(body):
        e = normalize(raw)
        if e and e not in sources:
            sources[e] = classify_source(e)
    for raw in LEADING_RE.findall(body):
        e = normalize(raw)
        if e and e not in sources:
            sources[e] = classify_source(e)

    # V2.1: Headline source (after em-dash)
    m = HEADLINE_SRC_RE.search(title)
    if m:
        e = normalize(m.group(1))
        if e and e not in sources:
            sources[e] = classify_source(e)

    # V2.2: "Про це повідомляє"
    for raw in PRO_CE_RE.findall(body):
        e = normalize(raw)
        if e and e not in sources:
            sources[e] = classify_source(e)

    # V2.3: "Як передає Укрінформ, про це X"
    for raw in AS_TRANSMITS_RE.findall(body):
        e = normalize(raw)
        if e and e not in sources:
            sources[e] = classify_source(e)

    # V2.4: "повідомили в X"
    for raw in IN_ORG_RE.findall(body):
        e = normalize(raw)
        if e and e not in sources:
            sources[e] = classify_source(e)

    # V2.5: OG description source
    if og_desc:
        m = OG_SRC_RE.search(og_desc)
        if m:
            e = normalize(m.group(1))
            # Skip if it's just "Укрінформ"
            if e and 'укрінформ' not in e.lower() and e not in sources:
                sources[e] = classify_source(e)

    official = sum(1 for t in sources.values() if t == 'official')
    non_official = sum(1 for t in sources.values() if t == 'non_official')
    return len(sources), official, non_official, list(sources.keys())


def is_official_url(url):
    slug = url.rstrip('/').split('/')[-1].lower()
    return any(m in slug for m in ALL_OFFICIAL if not any(c in m for c in 'абвгґдеєжзиіїйклмнопрстуфхцчшщьюя'))


def parse_article(url):
    sess = requests.Session()
    sess.headers['User-Agent'] = UA
    try:
        r = sess.get(url, timeout=12)
        if r.status_code != 200: return None
        soup = BeautifulSoup(r.text, 'html.parser')

        title_tag = soup.find('meta', attrs={'property': 'og:title'})
        title = title_tag['content'].strip() if title_tag and title_tag.get('content') else ''

        desc_tag = soup.find('meta', attrs={'property': 'og:description'})
        og_desc = desc_tag['content'].strip() if desc_tag and desc_tag.get('content') else ''

        body = soup.select_one('div.newsText') or soup.find('article')
        if not body: return None
        body_text = ' '.join(p.get_text(' ', strip=True) for p in body.find_all('p') if p.get_text(' ', strip=True))
        body_text = re.sub(r'\s+', ' ', body_text).strip()

        if len(body_text) < 30: return None

        sc, oc, noc, extracted = extract_sources_v2(title, og_desc, body_text)
        off_url = is_official_url(url)
        return {
            'sc_v2': sc, 'oc_v2': oc, 'noc_v2': noc,
            'parket_v2': off_url and sc <= 1 and noc == 0,
            'balance_v2': off_url and noc == 0 and sc <= 1,
            'sources_v2': '; '.join(extracted[:5])
        }
    except Exception:
        return None


def load_progress():
    if PROGRESS.exists():
        return json.load(open(PROGRESS))
    return {}


def save_progress(data):
    with open(PROGRESS, 'w') as f:
        json.dump(data, f)


def main():
    rows = list(csv.DictReader(open(CSV)))
    audited = [r for r in rows if r['audited'] == 'True']

    print(f"Reparse v2 on {len(audited):,} audited articles")

    progress = load_progress()
    todo = [r for r in audited if r['url'] not in progress]
    print(f"Already done: {len(progress)}, To process: {len(todo)}")

    if not todo:
        print("All done!")
        return

    BATCH = 500
    for batch_start in range(0, len(todo), BATCH):
        batch = todo[batch_start:batch_start + BATCH]
        batch_num = batch_start // BATCH + 1
        total_batches = (len(todo) + BATCH - 1) // BATCH
        print(f"\nBatch {batch_num}/{total_batches} ({len(batch)} articles)")

        with ThreadPoolExecutor(max_workers=12) as ex:
            futures = {ex.submit(parse_article, r['url']): r for r in batch}
            done = 0
            for f in as_completed(futures):
                done += 1
                rec = futures[f]
                parsed = f.result()
                if parsed:
                    progress[rec['url']] = parsed
                if done % 100 == 0:
                    print(f"  {done}/{len(batch)}")

        save_progress(progress)
        print(f"  Saved. Total parsed: {len(progress):,}")

    # Generate final CSV with v2 columns
    print("\nWriting output CSV...")
    fieldnames = list(rows[0].keys()) + ['sc_v2', 'oc_v2', 'noc_v2', 'parket_v2', 'balance_v2', 'sources_v2']
    with open(OUT, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            if r['url'] in progress:
                p = progress[r['url']]
                r.update({k: str(v) for k, v in p.items()})
            w.writerow(r)

    # Final stats
    rows_v2 = list(csv.DictReader(open(OUT)))
    matched = [r for r in rows_v2 if r.get('sc_v2')]
    p1 = [r for r in matched if r['period_slug'] == 'before_exclusion_matsuka']
    p2 = [r for r in matched if r['period_slug'] == 'before_reinclusion_after_departure']
    p1_no_ato = [r for r in p1 if r['rubric'] != 'rubric-ato']
    p2_no_ato = [r for r in p2 if r['rubric'] != 'rubric-ato']

    def pct(arts):
        if not arts: return 'N/A'
        pk = sum(1 for r in arts if r.get('parket_v2') == 'True')
        return f"{pk/len(arts)*100:.2f}% ({pk}/{len(arts)})"

    print(f"\n{'='*60}")
    print(f"V2 PARSER RESULTS")
    print(f"{'='*60}")
    print(f"Successfully reparsed: {len(matched):,}/{len(audited):,}")
    print(f"\nWith ATO:")
    print(f"  P1 parket: {pct(p1)}")
    print(f"  P2 parket: {pct(p2)}")
    print(f"\nWithout ATO:")
    print(f"  P1 parket: {pct(p1_no_ato)}")
    print(f"  P2 parket: {pct(p2_no_ato)}")

    # Average sources
    for label, arts in [('P1', p1), ('P2', p2), ('P1 no-ATO', p1_no_ato), ('P2 no-ATO', p2_no_ato)]:
        avg = sum(int(r['sc_v2']) for r in arts if r.get('sc_v2')) / len(arts) if arts else 0
        print(f"  {label} avg sources: {avg:.2f}")


if __name__ == '__main__':
    main()
