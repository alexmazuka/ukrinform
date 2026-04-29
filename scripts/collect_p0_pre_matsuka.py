"""
Collect Ukrinform articles for Period 0 (pre-Matsuka).
Period: 2023-05-01 → 2023-10-31 (6 months before Matsuka's appointment)
This was when IMI had Ukrinform in the White List (H1 + H2 2023).

Then runs v3 classifier to compute parket rate for direct comparison.
"""
from __future__ import annotations
import csv, json, re, time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / 'data' / 'period_zero'
DATA.mkdir(parents=True, exist_ok=True)

UA = 'Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'

# Period 0 — pre-Matsuka era when Ukrinform was in IMI White List
P0_START = date(2023, 5, 1)
P0_END = date(2023, 10, 31)

PRIMARY_RUBRICS = {
    'rubric-polytics', 'rubric-economy', 'rubric-society',
    'rubric-regions', 'rubric-ato', 'rubric-tymchasovo-okupovani',
    'rubric-vidbudova',
}

# Source detection patterns (v2 from main project)
REPORTING_VERBS = (
    'заявив', 'заявила', 'повідомив', 'повідомила', 'сказав', 'сказала',
    'наголосив', 'наголосила', 'зауважив', 'зауважила', 'додав', 'додала',
    'підкреслив', 'підкреслила', 'відзначив', 'відзначила', 'розповів',
    'розповіла', 'написав', 'написала', 'зазначив', 'зазначила'
)
PERSON_RE = re.compile(r'([А-ЯІЇЄҐA-Z][^.!?\n]{1,90}?)\s+(?:' + '|'.join(REPORTING_VERBS) + r')\b')
LEADING_RE = re.compile(r'(?:За словами|За даними|Як повідомив|Як повідомила|Як повідомили|Як зазначив|Як зазначила|Повідомляє)\s+([^,.;:\n]{1,90})')
HEADLINE_SRC_RE = re.compile(r'\s[—–-]\s*([А-ЯІЇЄҐA-Z][А-ЯІЇЄҐа-яіїєґA-Za-z\s]{2,60}?)\s*$')
PRO_CE_RE = re.compile(r'[Пп]ро це (?:повідомляє|повідомили|йдеться\s+(?:в|у)|зазначається\s+(?:в|у)|сказано\s+(?:в|у)|(?:розповів|розповіла))\s+([А-ЯІЇЄҐA-Z][^.!?\n]{2,80})')
AS_TRANSMITS_RE = re.compile(r'[Яя]к (?:передає|передають|пише|пишуть|повідомляє|повідомляють)\s+Укрінформ,?\s*про це\s+([А-ЯІЇЄҐA-Z][^.!?\n]{2,70})')
IN_ORG_RE = re.compile(r'(?:повідомили|зазначили|уточнили|наголосили|підкреслили|сказали|вважають|додали)\s+(?:в|у|на)\s+([А-ЯІЇЄҐA-Z][^.!?\n]{2,50})')

# v3 word-boundary classification
OFFICIAL_PATTERNS = {
    'Президент / ОП': {'exact':['zelenskij','zelensky','prezident','opu','yermak','ermak'],'prefix':['zelensk','prezident','ofis-prezidenta','yermak','ermak']},
    'Уряд': {'exact':['kabmin','kabminu','kabministr','uryad','uryadu','urad','uradu','uradi','uradova','uradovij','smygal','shmygal','premyer','premier','svyrydenko','svyridenko'],'prefix':['kabmin','uryad','urad','smygal','shmygal','premyer','premier','svyriden','svyryden']},
    'Парламент': {'exact':['rada','radoyu','radoju','verhovna','verhovnoyu','verhovnoju','nardep','nardepy','deputat','deputaty','komitet','stefancuk'],'prefix':['verhovn','nardep','stefancuk']},
    'Міністерства': {'exact':['ministr','ministra','ministry','ministrom','ministerstvo','ministerstva','mzs','mvs','minfin','minekonom','minoboroni','mincifri','minkult','minstratehprom','minekoenergo','umerov','umerova','kuleba','kulebu','sybiha','shmygal','shmyhalja','fedorov','fedorova'],'prefix':['ministr','ministerstv','minoboron','minekonom','minfin','mincifr','minkult','minstrateh','umerov','kuleb','sybih','fedorov']},
    'Силовий блок': {'exact':['genshtab','zsu','sbu','gur','dpsu','dsns','syrskij','sirskij','syrskogo','sirskogo','zaluzhnij','zaluzhnogo','budanov','budanova'],'prefix':['genshtab','zaluzhn','syrsk','sirsk','budanov'],'multi_word':['sili-oboroni','syl-oborony']},
    'Регіональна влада': {'exact':['ova','kmva','kmda','oblrada','miskrada'],'prefix':['oblrada','miskrada']},
    'Держструктури': {'exact':['ukrzaliznicia','ukrzaliznycia','ukrenergo','naftogaz','oschadbank','pryvatbank','pension','nbu','nabu','sap'],'prefix':['ukrzaliznic','ukrzaliznyc','ukrenergo','naftogaz']},
}

def classify_official_v3(slug):
    words = [w for w in re.split(r'[-_.]', slug.lower()) if w]
    if not words: return False
    for cat, p in OFFICIAL_PATTERNS.items():
        if any(w in p.get('exact',[]) for w in words): return True
        for w in words:
            for prefix in p.get('prefix',[]):
                if len(prefix) >= 5 and w.startswith(prefix): return True
        for mw in p.get('multi_word',[]):
            if mw in slug.lower(): return True
    return False

def normalize(t):
    c = re.sub(r'\s+',' ',t.replace('\xa0',' ')).strip(' ,;:.!?"""«»()[]—–-')
    return c if 3 <= len(c) <= 100 and len(c.split()) <= 10 else ''

def extract_sources(title, og_desc, body):
    sources = set()
    for raw in PERSON_RE.findall(body):
        e = normalize(raw)
        if e: sources.add(e)
    for raw in LEADING_RE.findall(body):
        e = normalize(raw)
        if e: sources.add(e)
    m = HEADLINE_SRC_RE.search(title)
    if m:
        e = normalize(m.group(1))
        if e: sources.add(e)
    for raw in PRO_CE_RE.findall(body):
        e = normalize(raw)
        if e: sources.add(e)
    for raw in AS_TRANSMITS_RE.findall(body):
        e = normalize(raw)
        if e: sources.add(e)
    for raw in IN_ORG_RE.findall(body):
        e = normalize(raw)
        if e: sources.add(e)
    if og_desc:
        m = re.search(r'[—–]\s*([А-ЯІЇЄҐA-Z][^.!?\n—–]{2,60}?)\s*\.?$', og_desc)
        if m:
            e = normalize(m.group(1))
            if e and 'укрінформ' not in e.lower(): sources.add(e)
    return list(sources)

def iso_weeks_between(start, end):
    current = start
    weeks = set()
    while current <= end:
        iso = current.isocalendar()
        weeks.add((iso.year, iso.week))
        current += timedelta(days=1)
    return sorted(weeks)

def collect_corpus():
    sess = requests.Session()
    sess.headers['User-Agent'] = UA
    weeks = iso_weeks_between(P0_START, P0_END)
    print(f"Collecting {len(weeks)} weekly sitemaps...")

    records = {}
    for year, week in weeks:
        url = f'https://www.ukrinform.ua/sitemap/{year}/{week:02d}.xml'
        try:
            r = sess.get(url, timeout=15)
            if r.status_code != 200: continue
            root = ET.fromstring(r.text)
            ns = {'sm':'http://www.sitemaps.org/schemas/sitemap/0.9'}
            for url_el in root.findall('sm:url', ns):
                loc = url_el.findtext('sm:loc','',ns).strip()
                lastmod = url_el.findtext('sm:lastmod','',ns).strip()
                if not loc or not lastmod: continue
                rubric_match = re.search(r'ukrinform\.ua/(rubric-[a-z-]+)/', loc)
                if not rubric_match or rubric_match.group(1) not in PRIMARY_RUBRICS: continue
                try:
                    d = date.fromisoformat(lastmod[:10])
                except: continue
                if not (P0_START <= d <= P0_END): continue
                slug = re.sub(r'^\d+-', '', loc.rstrip('/').split('/')[-1].replace('.html',''))
                records[loc] = {
                    'url': loc, 'date': d.isoformat(), 'month': d.strftime('%Y-%m'),
                    'rubric': rubric_match.group(1), 'slug': slug,
                    'official': classify_official_v3(slug),
                }
        except Exception as e:
            print(f"  Error {url}: {e}")
        time.sleep(0.3)

    print(f"Collected: {len(records):,} URLs")
    by_rubric = {}
    by_month = {}
    for r in records.values():
        by_rubric[r['rubric']] = by_rubric.get(r['rubric'],0)+1
        by_month[r['month']] = by_month.get(r['month'],0)+1
    print("By month:", dict(sorted(by_month.items())))
    print("By rubric:", dict(sorted(by_rubric.items())))

    return list(records.values())


def parse_article(rec):
    sess = requests.Session()
    sess.headers['User-Agent'] = UA
    try:
        r = sess.get(rec['url'], timeout=12)
        if r.status_code != 200: return None
        soup = BeautifulSoup(r.text, 'html.parser')
        title_tag = soup.find('meta', attrs={'property':'og:title'})
        title = title_tag['content'].strip() if title_tag and title_tag.get('content') else ''
        desc_tag = soup.find('meta', attrs={'property':'og:description'})
        og_desc = desc_tag['content'].strip() if desc_tag and desc_tag.get('content') else ''
        body = soup.select_one('div.newsText') or soup.find('article')
        if not body: return None
        body_text = re.sub(r'\s+',' ',' '.join(p.get_text(' ',strip=True) for p in body.find_all('p') if p.get_text(' ',strip=True))).strip()
        if len(body_text) < 30: return None
        sources = extract_sources(title, og_desc, body_text)
        sc = len(sources)
        # Classify each source as official/non-official
        OFFICIAL_MARKERS = ['зеленськ','президент','офіс','єрмак','кабмін','уряд','шмигал','премʼєр','премьер','верховн','рада','нардеп','міністр','мзс','мвс','міноборон','генштаб','зсу','сбу','гур','двсу','дсну','сил оборон','ова','кмда','облрада','мер','укрзалізниц','укренерго','нафтогаз']
        official_count = sum(1 for s in sources if any(m in s.lower() for m in OFFICIAL_MARKERS))
        noc = sc - official_count
        official_url = rec['official']
        return {
            'title': title, 'sc': sc, 'oc': official_count, 'noc': noc,
            'parket_v3': official_url and sc <= 1 and noc == 0,
            'balance_v3': official_url and noc == 0 and sc <= 1,
            'sources': '; '.join(sources[:5])
        }
    except: return None


def main():
    records = collect_corpus()

    # Save URL list
    with open(DATA / 'p0_urls.json','w',encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

    print(f"\nAuditing {len(records):,} articles...")
    audited = []
    with ThreadPoolExecutor(max_workers=8) as ex:
        futures = {ex.submit(parse_article, r): r for r in records}
        done = 0
        for f in as_completed(futures):
            done += 1
            if done % 500 == 0: print(f"  {done}/{len(records)}")
            rec = futures[f]
            parsed = f.result()
            if parsed:
                rec.update(parsed)
                rec['audited'] = True
                audited.append(rec)
            else:
                rec['audited'] = False
                audited.append(rec)

    with open(DATA / 'p0_audited.json','w',encoding='utf-8') as f:
        json.dump(audited, f, ensure_ascii=False, indent=2)

    # Stats
    ok = [r for r in audited if r.get('audited')]
    pk = sum(1 for r in ok if r.get('parket_v3'))
    pk_pct = pk/len(ok)*100 if ok else 0
    no_ato = [r for r in ok if r['rubric']!='rubric-ato']
    pk_no = sum(1 for r in no_ato if r.get('parket_v3'))
    pk_no_pct = pk_no/len(no_ato)*100 if no_ato else 0
    avg_src = sum(r.get('sc',0) for r in ok)/len(ok) if ok else 0

    print(f"\n{'='*60}")
    print(f"PERIOD 0 (PRE-MATSUKA, May–Oct 2023) RESULTS")
    print(f"{'='*60}")
    print(f"Collected: {len(records):,}, Audited: {len(ok):,}")
    print(f"Parket (with ATO): {pk}/{len(ok)} = {pk_pct:.2f}%")
    print(f"Parket (no ATO):   {pk_no}/{len(no_ato)} = {pk_no_pct:.2f}%")
    print(f"Avg sources:       {avg_src:.2f}")

if __name__=='__main__':
    main()
