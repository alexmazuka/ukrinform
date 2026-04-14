"""
Full Corpus Audit: Parse HTML for ALL unaudited articles.
=========================================================
For each article: fetch HTML, extract title, count sources
(official vs non-official), determine likely_parket and balance_risk.

Processes in batches with concurrent requests. Progress is saved
after each batch so the script can be restarted safely.

Outputs: updates data/corpus_fast.csv in-place with audit results.
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / 'data'
CORPUS_PATH = DATA_DIR / 'corpus_fast.csv'
PROGRESS_PATH = DATA_DIR / 'audit_progress.json'

USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
)

OFFICIAL_CATEGORY_PATTERNS = {
    'Президент / ОП': ['zelensk', 'prezident', 'ofis-prezidenta', 'opu', 'yermak', 'ermak'],
    'Уряд / Кабмін': ['kabmin', 'uryad', 'smygal', 'premyer', 'premier'],
    'Парламент': ['verhovn', 'rada', 'nardep', 'deputat', 'komitet'],
    'Міністерства': ['ministr', 'ministerstvo', 'mzs', 'minoboroni', 'mvs', 'minekonom', 'minfin', 'mon', 'mincifri', 'minkult'],
    'Силовий блок': ['genshtab', 'zsu', 'sbu', 'gur', 'dpsu', 'dsns', 'sili-oboroni', 'armiya'],
    'Регіональна влада': ['ova', 'kmva', 'kmda', 'oblrada', 'miskrada', 'mer'],
    'Держструктури / держкомпанії': ['ukrzaliznic', 'ukrenergo', 'naftogaz', 'fond-derzmajna', 'pensijn', 'podatkov', 'mitnic'],
}

REPORTING_VERBS = (
    'заявив', 'заявила', 'повідомив', 'повідомила', 'сказав', 'сказала', 'наголосив',
    'наголосила', 'зауважив', 'зауважила', 'додав', 'додала', 'підкреслив', 'підкреслила',
    'відзначив', 'відзначила', 'розповів', 'розповіла', 'написав', 'написала', 'зазначив', 'зазначила'
)

PERSON_SOURCE_RE = re.compile(
    r'([А-ЯІЇЄҐA-Z][^.!?\n]{1,90}?)\s+(?:' + '|'.join(REPORTING_VERBS) + r')\b'
)
LEADING_SOURCE_RE = re.compile(
    r'(?:За словами|За даними|Як повідомив|Як повідомила|Як повідомили|Як зазначив|Як зазначила|Повідомляє)\s+'
    r'([^,.;:\n]{1,90})'
)


def normalize_entity(text: str) -> str:
    cleaned = re.sub(r'\s+', ' ', text.replace('\xa0', ' ')).strip(' ,;:.!?"""«»()[]')
    if len(cleaned.split()) > 10:
        return ''
    return cleaned


def extract_sources(text: str) -> tuple[int, int, int]:
    candidates = []
    for raw in PERSON_SOURCE_RE.findall(text):
        entity = normalize_entity(raw)
        if entity:
            candidates.append(entity)
    for raw in LEADING_SOURCE_RE.findall(text):
        entity = normalize_entity(raw)
        if entity:
            candidates.append(entity)
    deduped = []
    seen = set()
    for entity in candidates:
        key = entity.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(entity)
    official = 0
    for entity in deduped:
        low = entity.lower()
        if any(marker in low for markers in OFFICIAL_CATEGORY_PATTERNS.values() for marker in markers):
            official += 1
    return len(deduped), official, max(len(deduped) - official, 0)


def parse_title_and_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, 'html.parser')
    title = ''
    og_title = soup.find('meta', attrs={'property': 'og:title'})
    if og_title and og_title.get('content'):
        title = og_title['content'].strip()
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()

    body = soup.select_one('div.newsText') or soup.find('article')
    text = ''
    if body:
        paragraphs = [p.get_text(' ', strip=True) for p in body.find_all('p') if p.get_text(' ', strip=True)]
        text = '\n'.join(paragraphs) if paragraphs else body.get_text(' ', strip=True)
    text = re.sub(r'\s+', ' ', text).strip()
    return title, text


def fetch_and_audit(url: str, slug_text: str, is_official: bool) -> dict | None:
    """Fetch one article and return audit fields, or None on failure."""
    session = requests.Session()
    session.headers['User-Agent'] = USER_AGENT
    try:
        resp = session.get(url, timeout=12)
        if resp.status_code != 200:
            return None
        title, text = parse_title_and_text(resp.text)
        if not text:
            return None
        source_count, official_count, non_official_count = extract_sources(text)
        return {
            'actual_title': title or slug_text.replace('-', ' '),
            'source_count': source_count,
            'official_source_count': official_count,
            'non_official_source_count': non_official_count,
            'likely_parket': is_official and source_count <= 1 and non_official_count == 0,
            'balance_risk': is_official and non_official_count == 0 and source_count <= 1,
            'excerpt': (text[:320] + '...') if len(text) > 320 else text,
        }
    except Exception:
        return None


def load_progress() -> set[str]:
    if PROGRESS_PATH.exists():
        with open(PROGRESS_PATH) as f:
            return set(json.load(f))
    return set()


def save_progress(audited_urls: set[str]):
    with open(PROGRESS_PATH, 'w') as f:
        json.dump(sorted(audited_urls), f)


def main():
    print("=" * 60)
    print("FULL CORPUS AUDIT: Parsing HTML for all articles")
    print("=" * 60)

    # Load corpus
    rows = []
    fieldnames = None
    with open(CORPUS_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)

    # Find unaudited rows
    already_done = load_progress()
    to_audit = [(i, row) for i, row in enumerate(rows)
                if row['audited'] != 'True' and row['url'] not in already_done]

    print(f"Total rows: {len(rows)}")
    print(f"Already audited: {len(rows) - len(to_audit)}")
    print(f"Need audit: {len(to_audit)}")

    if not to_audit:
        print("Nothing to do!")
        return

    # Process in batches
    BATCH_SIZE = 500
    MAX_WORKERS = 15
    total_success = 0
    total_fail = 0

    for batch_start in range(0, len(to_audit), BATCH_SIZE):
        batch = to_audit[batch_start:batch_start + BATCH_SIZE]
        batch_num = batch_start // BATCH_SIZE + 1
        total_batches = (len(to_audit) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"\n--- Batch {batch_num}/{total_batches} ({len(batch)} articles) ---")

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = {}
            for idx, row in batch:
                is_official = row['official_slug'] == 'True'
                future = executor.submit(
                    fetch_and_audit, row['url'], row['slug_text'], is_official
                )
                futures[future] = (idx, row)

            done_count = 0
            for future in as_completed(futures):
                done_count += 1
                idx, row = futures[future]
                result = future.result()

                if result:
                    rows[idx]['audited'] = 'True'
                    rows[idx]['actual_title'] = result['actual_title']
                    rows[idx]['source_count'] = str(result['source_count'])
                    rows[idx]['official_source_count'] = str(result['official_source_count'])
                    rows[idx]['non_official_source_count'] = str(result['non_official_source_count'])
                    rows[idx]['likely_parket'] = str(result['likely_parket'])
                    rows[idx]['balance_risk'] = str(result['balance_risk'])
                    rows[idx]['excerpt'] = result['excerpt']
                    already_done.add(row['url'])
                    total_success += 1
                else:
                    total_fail += 1

                if done_count % 100 == 0:
                    print(f"  {done_count}/{len(batch)} done")

        # Save progress after each batch
        save_progress(already_done)

        # Save CSV after each batch (crash-safe)
        with open(CORPUS_PATH, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

        print(f"  Batch done. Success: {total_success}, Failed: {total_fail}")
        print(f"  CSV saved. Progress checkpoint saved.")

    # Final stats
    audited_rows = [r for r in rows if r['audited'] == 'True']
    period_stats = defaultdict(lambda: {'total': 0, 'parket': 0, 'balance_risk': 0, 'sources': []})

    for row in audited_rows:
        ps = period_stats[row['period_slug']]
        ps['total'] += 1
        if row['likely_parket'] == 'True':
            ps['parket'] += 1
        if row['balance_risk'] == 'True':
            ps['balance_risk'] += 1
        sc = int(row['source_count']) if row['source_count'] != '-1' else 0
        ps['sources'].append(sc)

    print(f"\n{'=' * 60}")
    print("AUDIT COMPLETE")
    print(f"Total audited: {len(audited_rows)}/{len(rows)}")
    print(f"Failed to fetch: {total_fail}")

    for slug, stats in sorted(period_stats.items()):
        pct_parket = round(stats['parket'] / stats['total'] * 100, 2) if stats['total'] else 0
        pct_risk = round(stats['balance_risk'] / stats['total'] * 100, 2) if stats['total'] else 0
        avg_src = round(sum(stats['sources']) / len(stats['sources']), 2) if stats['sources'] else 0
        print(f"\n  {slug}:")
        print(f"    Audited: {stats['total']}")
        print(f"    Likely parket: {stats['parket']} ({pct_parket}%)")
        print(f"    Balance risk: {stats['balance_risk']} ({pct_risk}%)")
        print(f"    Avg sources: {avg_src}")

    # Cleanup progress file
    if PROGRESS_PATH.exists():
        PROGRESS_PATH.unlink()
    print("\nDone.")


if __name__ == '__main__':
    main()
