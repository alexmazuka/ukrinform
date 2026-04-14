from __future__ import annotations

import csv
import json
import random
import re
import statistics
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path('/Users/oleksiymatsuka/Desktop/ukrinform-imi-study')
DATA_DIR = BASE_DIR / 'data'
DASHBOARD_DIR = BASE_DIR / 'dashboard'

USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'
)

PERIODS = [
    {
        'slug': 'before_exclusion_matsuka',
        'label': 'Перед виключенням за керівництва Олексія Мацуки',
        'short_label': '09.11.2023-25.04.2024',
        'start': date(2023, 11, 9),
        'end': date(2024, 4, 25),
    },
    {
        'slug': 'before_reinclusion_after_departure',
        'label': 'Перед повторним включенням після відходу Олексія Мацуки',
        'short_label': '01.07.2025-15.12.2025',
        'start': date(2025, 7, 1),
        'end': date(2025, 12, 15),
    },
]

PRIMARY_RUBRICS = {
    'rubric-polytics',
    'rubric-economy',
    'rubric-society',
    'rubric-regions',
    'rubric-ato',
    'rubric-tymchasovo-okupovani',
    'rubric-vidbudova',
}

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
BALANCE_MARKERS = [
    'водночас', 'натомість', 'у відповідь', 'відмовився коментувати', 'відмовилася коментувати',
    'не відповів на запит', 'не відповіла на запит', 'опозиці', 'критик', 'правозахис', 'експерт', 'аналітик'
]


@dataclass
class CorpusRecord:
    period_slug: str
    period_label: str
    url: str
    date_value: str
    month: str
    rubric: str
    slug_text: str
    official_slug: bool
    official_categories: list[str]
    audit_bucket: str = ''
    audited: bool = False
    actual_title: str = ''
    source_count: int = -1
    official_source_count: int = -1
    non_official_source_count: int = -1
    likely_parket: bool = False
    balance_risk: bool = False
    excerpt: str = ''


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)


def requests_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({'User-Agent': USER_AGENT})
    return session


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def rubric_from_url(url: str) -> str:
    parts = urlparse(url).path.strip('/').split('/')
    return parts[0] if parts else 'unknown'


def slug_from_url(url: str) -> str:
    path = urlparse(url).path.strip('/').split('/')
    if len(path) < 2:
        return ''
    tail = path[-1].replace('.html', '')
    return tail.split('-', 1)[1] if '-' in tail else tail


def official_categories_for_slug(slug: str) -> list[str]:
    low = slug.lower()
    categories = []
    for category, patterns in OFFICIAL_CATEGORY_PATTERNS.items():
        if any(pattern in low for pattern in patterns):
            categories.append(category)
    return categories


def iso_weeks_between(start: date, end: date) -> list[tuple[int, int]]:
    current = start
    weeks: set[tuple[int, int]] = set()
    while current <= end:
        iso = current.isocalendar()
        weeks.add((iso.year, iso.week))
        current += timedelta(days=1)
    return sorted(weeks)


def fetch_text(session: requests.Session, url: str, timeout: int = 10) -> str | None:
    for attempt in range(2):
        try:
            response = session.get(url, timeout=timeout)
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.text
        except requests.RequestException:
            if attempt == 1:
                return None
            time.sleep(1)
    return None


def fetch_head(session: requests.Session, url: str, timeout: int = 10) -> str | None:
    for attempt in range(2):
        try:
            with session.get(url, timeout=timeout, stream=True) as response:
                response.raise_for_status()
                chunks = []
                size = 0
                for chunk in response.iter_content(2048):
                    if not chunk:
                        break
                    chunks.append(chunk)
                    size += len(chunk)
                    blob = b''.join(chunks)
                    if b'</head>' in blob.lower() or size >= 65536:
                        encoding = response.encoding or 'utf-8'
                        return blob.decode(encoding, errors='ignore')
                encoding = response.encoding or 'utf-8'
                return b''.join(chunks).decode(encoding, errors='ignore')
        except requests.RequestException:
            if attempt == 1:
                return None
            time.sleep(1)
    return None


def parse_sitemap(xml_text: str) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    items = []
    for url_el in root.findall('sm:url', ns):
        loc = url_el.findtext('sm:loc', default='', namespaces=ns).strip()
        lastmod = url_el.findtext('sm:lastmod', default='', namespaces=ns).strip()
        if loc:
            items.append({'loc': loc, 'lastmod': lastmod})
    return items


def collect_corpus(period: dict[str, object]) -> list[CorpusRecord]:
    session = requests_session()
    records: dict[str, CorpusRecord] = {}
    weeks = iso_weeks_between(period['start'], period['end'])
    for index, (year, week) in enumerate(weeks, start=1):
        if index == 1 or index % 4 == 0:
            print(f"[{period['slug']}] sitemap {index}/{len(weeks)} -> {year}/{week}")
        xml = fetch_text(session, f'https://www.ukrinform.ua/sitemap/{year}/{week}.xml')
        if not xml:
            continue
        for item in parse_sitemap(xml):
            url = item['loc']
            rubric = rubric_from_url(url)
            if rubric not in PRIMARY_RUBRICS:
                continue
            parsed = parse_iso_datetime(item['lastmod'])
            if not parsed:
                continue
            record_date = parsed.date()
            if not (period['start'] <= record_date <= period['end']):
                continue
            slug_text = slug_from_url(url)
            categories = official_categories_for_slug(slug_text)
            records[url] = CorpusRecord(
                period_slug=period['slug'],
                period_label=period['label'],
                url=url,
                date_value=record_date.isoformat(),
                month=record_date.strftime('%Y-%m'),
                rubric=rubric,
                slug_text=slug_text,
                official_slug=bool(categories),
                official_categories=categories,
            )
    return sorted(records.values(), key=lambda item: (item.date_value, item.url))


def normalize_entity(text: str) -> str:
    cleaned = re.sub(r'\s+', ' ', text.replace('\xa0', ' ')).strip(' ,;:.!?"“”«»()[]')
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


def audit_sample(records: list[CorpusRecord], rng_seed: int = 42) -> list[CorpusRecord]:
    rng = random.Random(rng_seed)
    by_period = defaultdict(list)
    for record in records:
        by_period[record.period_slug].append(record)

    audited: list[CorpusRecord] = []
    for period in PERIODS:
        period_records = by_period[period['slug']]
        official = [record for record in period_records if record.official_slug]
        other = [record for record in period_records if not record.official_slug]
        sample = rng.sample(official, min(1400, len(official)))
        sample += rng.sample(other, min(400, len(other)))
        for record in sample:
            record.audit_bucket = 'official' if record.official_slug else 'other'
            audited.append(record)
    return audited


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


def run_audit(records: list[CorpusRecord], max_workers: int = 10) -> None:
    def worker(record: CorpusRecord) -> tuple[CorpusRecord, str | None]:
        session = requests_session()
        html = fetch_text(session, record.url, timeout=12)
        return record, html

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(worker, record): record for record in records}
        for index, future in enumerate(as_completed(futures), start=1):
            if index == 1 or index % 200 == 0:
                print(f"[audit] {index}/{len(records)}")
            record, html = future.result()
            if not html:
                continue
            title, text = parse_title_and_text(html)
            source_count, official_count, non_official_count = extract_sources(text)
            record.audited = True
            record.actual_title = title or record.slug_text.replace('-', ' ')
            record.source_count = source_count
            record.official_source_count = official_count
            record.non_official_source_count = non_official_count
            record.balance_risk = record.official_slug and non_official_count == 0 and source_count <= 1
            record.likely_parket = record.official_slug and source_count <= 1 and non_official_count == 0
            record.excerpt = (text[:320] + '...') if len(text) > 320 else text


def pct(a: int, b: int) -> float:
    return round((a / b) * 100, 2) if b else 0.0


def summarize_full(records: list[CorpusRecord], period: dict[str, object]) -> dict[str, object]:
    items = [record for record in records if record.period_slug == period['slug']]
    return {
        'slug': period['slug'],
        'label': period['label'],
        'short_label': period['short_label'],
        'article_count': len(items),
        'official_slug_share': pct(sum(record.official_slug for record in items), len(items)),
        'median_slug_words': int(statistics.median(len(record.slug_text.split('-')) for record in items)) if items else 0,
    }


def summarize_audit(records: list[CorpusRecord], period_slug: str) -> dict[str, object]:
    items = [record for record in records if record.period_slug == period_slug and record.audited]
    return {
        'period_slug': period_slug,
        'sample_size': len(items),
        'likely_parket_share': pct(sum(record.likely_parket for record in items), len(items)),
        'balance_risk_share': pct(sum(record.balance_risk for record in items), len(items)),
        'single_source_share': pct(sum(record.source_count <= 1 for record in items), len(items)),
        'non_official_source_share': pct(sum(record.non_official_source_count > 0 for record in items), len(items)),
    }


def monthly_rows(records: list[CorpusRecord]) -> list[dict[str, object]]:
    buckets = defaultdict(list)
    for record in records:
        buckets[(record.period_slug, record.month)].append(record)
    rows = []
    for (period_slug, month), items in sorted(buckets.items()):
        rows.append({
            'period_slug': period_slug,
            'month': month,
            'article_count': len(items),
            'official_slug_share': pct(sum(record.official_slug for record in items), len(items)),
        })
    return rows


def rubric_rows(records: list[CorpusRecord]) -> dict[str, list[dict[str, object]]]:
    output = {}
    for period in PERIODS:
        period_items = [record for record in records if record.period_slug == period['slug']]
        groups = defaultdict(list)
        for record in period_items:
            groups[record.rubric].append(record)
        output[period['slug']] = [
            {
                'rubric': rubric,
                'article_count': len(items),
                'official_slug_share': pct(sum(record.official_slug for record in items), len(items)),
            }
            for rubric, items in sorted(groups.items())
        ]
    return output


def category_rows(records: list[CorpusRecord]) -> dict[str, dict[str, int]]:
    output = defaultdict(Counter)
    for record in records:
        for category in record.official_categories:
            output[record.period_slug][category] += 1
    return {period_slug: dict(counter) for period_slug, counter in output.items()}


def high_risk_rows(records: list[CorpusRecord]) -> dict[str, list[dict[str, object]]]:
    output = {}
    for period in PERIODS:
        items = [record for record in records if record.period_slug == period['slug'] and record.audited]
        items.sort(key=lambda item: (int(item.likely_parket), int(item.balance_risk), item.official_source_count), reverse=True)
        output[period['slug']] = [asdict(record) for record in items[:25]]
    return output


def build_dashboard(study: dict[str, object]) -> str:
    payload = json.dumps(study, ensure_ascii=False).replace('</script>', '<\\/script>')
    return """<!DOCTYPE html>
<html lang='uk'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>
<title>Укрінформ: аудит двох періодів</title>
<style>
:root{--bg:#f6efe4;--panel:#fffaf2;--ink:#22303c;--muted:#61707f;--accent:#b24a2e;--accent2:#0a6a6a;--line:#e2d3bf;}*{box-sizing:border-box}body{margin:0;background:linear-gradient(180deg,#efe6d8,var(--bg));color:var(--ink);font-family:Georgia,'Times New Roman',serif}header{padding:40px 24px 24px;border-bottom:1px solid var(--line);background:rgba(255,250,242,.92);position:sticky;top:0}main{max-width:1200px;margin:0 auto;padding:24px}.card{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:18px;box-shadow:0 12px 28px rgba(30,25,20,.05)}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:16px}.section{margin:28px 0}.metric{font-size:2rem;font-weight:700}.muted{color:var(--muted)}table{width:100%;border-collapse:collapse}th,td{padding:10px 12px;border-bottom:1px solid var(--line);text-align:left;vertical-align:top}th{background:#f8efe2}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:18px;background:var(--panel)}.pill{display:inline-block;padding:6px 10px;border-radius:999px;background:#f1ddd5;margin-right:8px}.pill.alt{background:#d9eeee}.bars{display:grid;gap:12px}.bar-row{display:grid;grid-template-columns:260px 1fr;gap:12px;align-items:center}.track{display:grid;grid-template-columns:1fr 1fr;gap:8px}.track>div{background:#ecdfcd;border-radius:999px;overflow:hidden;height:18px}.fill-a{background:var(--accent);height:100%}.fill-b{background:var(--accent2);height:100%}a{color:var(--accent)}@media (max-width:780px){header{position:static}.bar-row{grid-template-columns:1fr}}
</style></head><body>
<header><h1>Укрінформ: аудит двох періодів</h1><p class='muted'>Повний корпус тут означає всі URL з релевантних суспільно-політичних рубрик, отримані з публічних sitemap. Текстовий аудит джерел і ризику «паркету» зроблено на великій стратифікованій вибірці.</p></header>
<main>
<section class='section card'><div id='pills'></div><div id='narrative'></div></section>
<section class='section'><h2>Повний корпус</h2><div class='grid' id='full-cards'></div></section>
<section class='section'><h2>Текстовий аудит вибірки</h2><div class='grid' id='audit-cards'></div></section>
<section class='section'><h2>Порівняння метрик</h2><div class='bars card' id='bars'></div></section>
<section class='section'><h2>Місячна динаміка повного корпусу</h2><div class='table-wrap'><table id='monthly'></table></div></section>
<section class='section'><h2>Рубрики</h2><div class='grid' id='rubrics'></div></section>
<section class='section'><h2>Офіційні категорії в slug/заголовкових маркерах</h2><div class='table-wrap'><table id='cats'></table></div></section>
<section class='section'><h2>Ручний пріоритет на перевірку</h2><div class='grid' id='risk'></div></section>
</main>
<script id='study-data' type='application/json'>__STUDY_JSON__</script>
<script>
const study = JSON.parse(document.getElementById('study-data').textContent);
const fullBySlug = Object.fromEntries(study.full_summary.map(x => [x.slug, x]));
const auditBySlug = Object.fromEntries(study.audit_summary.map(x => [x.period_slug, x]));
const p1 = study.periods[0], p2 = study.periods[1];
const f1 = fullBySlug[p1.slug], f2 = fullBySlug[p2.slug], a1 = auditBySlug[p1.slug], a2 = auditBySlug[p2.slug];
document.getElementById('pills').innerHTML = `<span class="pill">${p1.short_label}</span><span class="pill alt">${p2.short_label}</span>`;
document.getElementById('narrative').innerHTML = study.narrative.map(x => `<p>${x}</p>`).join('');
document.getElementById('full-cards').innerHTML = [
['URL у повному корпусі', `${f1.article_count.toLocaleString('uk-UA')} vs ${f2.article_count.toLocaleString('uk-UA')}`],
['Офіційний маркер у slug', `${f1.official_slug_share}% vs ${f2.official_slug_share}%`],
['Медіанна довжина slug', `${f1.median_slug_words} vs ${f2.median_slug_words}`]
].map(([k,v])=>`<div class="card"><div class="muted">${k}</div><div class="metric">${v}</div></div>`).join('');
document.getElementById('audit-cards').innerHTML = [
['Розмір текстової вибірки', `${a1.sample_size} vs ${a2.sample_size}`],
['Ймовірний паркет у вибірці', `${a1.likely_parket_share}% vs ${a2.likely_parket_share}%`],
['Ризик дисбалансу', `${a1.balance_risk_share}% vs ${a2.balance_risk_share}%`],
['Є неофіційне джерело', `${a1.non_official_source_share}% vs ${a2.non_official_source_share}%`],
['Одне джерело або жодного', `${a1.single_source_share}% vs ${a2.single_source_share}%`]
].map(([k,v])=>`<div class="card"><div class="muted">${k}</div><div class="metric">${v}</div></div>`).join('');
document.getElementById('bars').innerHTML = [
['Офіційний маркер у slug','official_slug_share',f1,f2],
['Ймовірний паркет у вибірці','likely_parket_share',a1,a2],
['Ризик дисбалансу','balance_risk_share',a1,a2],
['Є неофіційне джерело','non_official_source_share',a1,a2]
].map(([label,key,x,y])=>`<div class="bar-row"><div>${label}</div><div class="track"><div><div class="fill-a" style="width:${x[key]}%"></div></div><div><div class="fill-b" style="width:${y[key]}%"></div></div></div></div><div class="muted">${x[key]}% vs ${y[key]}%</div>`).join('');
document.getElementById('monthly').innerHTML = '<tr><th>Період</th><th>Місяць</th><th>URL</th><th>Офіційний маркер</th></tr>' + study.monthly.map(r=>`<tr><td>${fullBySlug[r.period_slug].short_label}</td><td>${r.month}</td><td>${r.article_count}</td><td>${r.official_slug_share}%</td></tr>`).join('');
document.getElementById('rubrics').innerHTML = study.periods.map(p=>`<div class="card"><h3>${p.label}</h3><div class="table-wrap"><table><tr><th>Рубрика</th><th>URL</th><th>Офіційний маркер</th></tr>${(study.rubrics[p.slug]||[]).map(r=>`<tr><td>${r.rubric}</td><td>${r.article_count}</td><td>${r.official_slug_share}%</td></tr>`).join('')}</table></div></div>`).join('');
const catNames = Array.from(new Set([...Object.keys(study.categories[p1.slug]||{}), ...Object.keys(study.categories[p2.slug]||{})])).sort();
document.getElementById('cats').innerHTML = '<tr><th>Категорія</th><th>Перед виключенням</th><th>Перед повторним включенням</th></tr>' + catNames.map(name=>`<tr><td>${name}</td><td>${(study.categories[p1.slug]||{})[name]||0}</td><td>${(study.categories[p2.slug]||{})[name]||0}</td></tr>`).join('');
document.getElementById('risk').innerHTML = study.periods.map(p=>`<div class="card"><h3>${p.label}</h3><div class="table-wrap"><table><tr><th>Дата</th><th>Матеріал</th><th>Джерел</th><th>Офіційних</th><th>Ймовірний паркет</th></tr>${(study.high_risk[p.slug]||[]).map(r=>`<tr><td>${r.date_value}</td><td><a href="${r.url}" target="_blank" rel="noreferrer">${r.actual_title || r.slug_text}</a><div class="muted">${r.rubric}</div></td><td>${r.source_count}</td><td>${r.official_source_count}</td><td>${r.likely_parket ? 'так' : 'ні'}</td></tr>`).join('')}</table></div></div>`).join('');
</script></body></html>""".replace('__STUDY_JSON__', payload)


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def write_methodology() -> None:
    text = (
        '# Методологія\n\n'
        '- Повний корпус: усі URL із публічних sitemap Укрінформу для релевантних суспільно-політичних рубрик.\n'
        '- Період 1: 09.11.2023-25.04.2024.\n'
        '- Період 2: 01.07.2025-15.12.2025.\n'
        '- Повний корпус рахує рубрики, дати та офіційні маркери у slug заголовка.\n'
        '- Текстовий аудит: стратифікована вибірка з офіційних і неофіційних матеріалів.\n'
        '- `likely_parket`: офіційний матеріал, де в тексті виявлено не більш як одне джерело і немає сигналів альтернативної позиції.\n'
        '- Обмеження: це не повна ручна перевірка ІМІ, а швидкий відтворюваний аудит великого корпусу.\n'
    )
    (BASE_DIR / 'METHODOLOGY.md').write_text(text, encoding='utf-8')


def main() -> None:
    ensure_dirs()
    corpus: list[CorpusRecord] = []
    for period in PERIODS:
        period_records = collect_corpus(period)
        print(f"[{period['slug']}] corpus size = {len(period_records)}")
        corpus.extend(period_records)

    audited = audit_sample(corpus)
    run_audit(audited)

    full_summary = [summarize_full(corpus, period) for period in PERIODS]
    audit_summary = [summarize_audit(corpus, period['slug']) for period in PERIODS]
    serializable_periods = [
        {
            'slug': period['slug'],
            'label': period['label'],
            'short_label': period['short_label'],
            'start': period['start'].isoformat(),
            'end': period['end'].isoformat(),
        }
        for period in PERIODS
    ]
    study = {
        'periods': serializable_periods,
        'full_summary': full_summary,
        'audit_summary': audit_summary,
        'monthly': monthly_rows(corpus),
        'rubrics': rubric_rows(corpus),
        'categories': category_rows(corpus),
        'high_risk': high_risk_rows(corpus),
        'narrative': [
            f"Повний корпус URL у релевантних рубриках: {full_summary[0]['article_count']} проти {full_summary[1]['article_count']}.",
            f"Частка офіційних маркерів у slug: {full_summary[0]['official_slug_share']}% проти {full_summary[1]['official_slug_share']}%.",
            f"У текстовому аудиті вибірки частка ймовірного 'паркету' становить {audit_summary[0]['likely_parket_share']}% проти {audit_summary[1]['likely_parket_share']}%.",
            'Якщо другий період не кращий або виглядає не кращим за цими метриками, це послаблює аргумент, що саме перший період був підставою для виключення з білого списку.'
        ],
        'generated_at': datetime.now().isoformat(timespec='seconds'),
    }
    write_json(DATA_DIR / 'corpus_fast.json', [asdict(record) for record in corpus])
    write_json(DATA_DIR / 'study_fast.json', study)
    with (DATA_DIR / 'corpus_fast.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(asdict(corpus[0]).keys()))
        writer.writeheader()
        for record in corpus:
            writer.writerow(asdict(record))
    write_methodology()
    (DASHBOARD_DIR / 'index.html').write_text(build_dashboard(study), encoding='utf-8')
    (BASE_DIR / 'README.txt').write_text('Відкрийте /Users/oleksiymatsuka/Desktop/ukrinform-imi-study/dashboard/index.html\n', encoding='utf-8')
    print('Study complete.')


if __name__ == '__main__':
    main()
