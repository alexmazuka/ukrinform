from __future__ import annotations

import csv
import json
import re
import statistics
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path('/Users/oleksiymatsuka/Desktop/ukrinform-imi-study')
DATA_DIR = BASE_DIR / 'data'
DASHBOARD_DIR = BASE_DIR / 'dashboard'

USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
    'AppleWebKit/537.36 (KHTML, like Gecko) '
    'Chrome/124.0 Safari/537.36'
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

EXCLUDED_RUBRICS = {'rubric-presshall'}
PRIMARY_RUBRICS = {
    'rubric-polytics',
    'rubric-economy',
    'rubric-society',
    'rubric-world',
    'rubric-regions',
    'rubric-ato',
    'rubric-tymchasovo-okupovani',
    'rubric-vidbudova',
}

OFFICIAL_CATEGORY_PATTERNS = {
    'Президент / ОП': [
        'зеленськ', 'президент', 'офіс президента', 'опу', 'єрмак'
    ],
    'Уряд / Кабмін': [
        'уряд', 'кабмін', 'кабінет міністрів', 'прем’єр', 'прем\'єр', 'шмигал'
    ],
    'Парламент': [
        'верховн', 'рада', 'нардеп', 'депутат', 'комітет'
    ],
    'Міністерства': [
        'міністр', 'міністерств', 'мзс', 'міноборони', 'мвс', 'мінеконом',
        'мінфін', 'міносвіти', 'мінкульт', 'мінцифри', 'міненерго', 'мо',
    ],
    'Силовий блок': [
        'генштаб', 'зсу', 'сбу', 'гур', 'дпсу', 'нацполі', 'дснс', 'сили оборони'
    ],
    'Регіональна влада': [
        'ова', 'обласн', 'кмва', 'кмда', 'міськрад', 'облрада', 'мер'
    ],
    'Держструктури / держкомпанії': [
        'держ', 'фонд держмайна', 'укренерго', 'укрзалізниц', 'нафтогаз',
        'пенсійний фонд', 'податкова', 'митниц',
    ],
}

OFFICIAL_ENTITY_MARKERS = [
    'президент', 'офіс президента', 'опу', 'кабмін', 'уряд', 'верховна рада',
    'нардеп', 'міністр', 'міністерство', 'мзс', 'міноборони', 'мвс', 'генштаб',
    'зсу', 'сбу', 'гур', 'дпсу', 'дснс', 'нацполіція', 'ова', 'кмва', 'кмда',
    'фонд держмайна', 'укренерго', 'укрзалізниця', 'нафтогаз', 'пенсійний фонд',
    'податкова', 'митниця', 'служба безпеки', 'сили оборони',
]

BALANCE_MARKERS = [
    'водночас', 'натомість', 'у відповідь', 'з іншого боку', 'відмовився коментувати',
    'відмовилася коментувати', 'не відповів на запит', 'не відповіла на запит',
    'опозиці', 'критик', 'правозахис', 'експерт', 'аналітик', 'незалежн',
]

REPORTING_VERBS = (
    'заявив', 'заявила', 'повідомив', 'повідомила', 'сказав', 'сказала',
    'наголосив', 'наголосила', 'зауважив', 'зауважила', 'додав', 'додала',
    'підкреслив', 'підкреслила', 'відзначив', 'відзначила', 'розповів',
    'розповіла', 'написав', 'написала', 'закликав', 'закликала', 'вважає',
    'вважають', 'прокоментував', 'прокоментувала', 'інформує', 'поінформував',
    'поінформувала', 'зазначив', 'зазначила',
)

PERSON_SOURCE_RE = re.compile(
    r'([А-ЯІЇЄҐA-Z][^.!?\n]{1,90}?)\s+(?:' + '|'.join(REPORTING_VERBS) + r')\b'
)
LEADING_SOURCE_RE = re.compile(
    r'(?:За словами|За даними|Як повідомив|Як повідомила|Як повідомили|'
    r'Як зазначив|Як зазначила|Повідомляє|Повідомив|Повідомила)\s+'
    r'([^,.;:\n]{1,90})'
)


@dataclass
class ArticleRecord:
    period_slug: str
    period_label: str
    url: str
    date_published: str
    month: str
    title: str
    description: str
    rubric: str
    word_count: int
    title_source: str
    source_count: int
    official_source_count: int
    non_official_source_count: int
    official_title: bool
    official_categories: list[str]
    attributed_title: bool
    balance_signal: bool
    likely_parket: bool
    balance_risk: bool
    primary_news_subset: bool
    excerpt: str


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)


def iso_weeks_between(start: date, end: date) -> list[tuple[int, int]]:
    current = start
    weeks: set[tuple[int, int]] = set()
    while current <= end:
        iso = current.isocalendar()
        weeks.add((iso.year, iso.week))
        current += timedelta(days=1)
    return sorted(weeks)


def requests_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({'User-Agent': USER_AGENT})
    return session


def fetch_text(session: requests.Session, url: str, timeout: int = 12) -> str | None:
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
            time.sleep(1.2 * (attempt + 1))
    return None


def parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    value = value.strip()
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        pass
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return None


def parse_sitemap(xml_text: str) -> list[dict[str, str]]:
    root = ET.fromstring(xml_text)
    ns = {'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9'}
    items: list[dict[str, str]] = []
    for url_el in root.findall('sm:url', ns):
        loc = url_el.findtext('sm:loc', default='', namespaces=ns).strip()
        lastmod = url_el.findtext('sm:lastmod', default='', namespaces=ns).strip()
        if loc:
            items.append({'loc': loc, 'lastmod': lastmod})
    return items


def rubric_from_url(url: str) -> str:
    path = urlparse(url).path.strip('/').split('/')
    return path[0] if path else 'unknown'


def normalize_entity(text: str) -> str:
    cleaned = re.sub(r'\s+', ' ', text.replace('\xa0', ' ')).strip(' ,;:.!?"“”«»()[]')
    cleaned = re.sub(r'^(що|про|як|коли)\s+', '', cleaned, flags=re.I)
    if len(cleaned.split()) > 10:
        return ''
    if cleaned.lower() in {'він', 'вона', 'вони', 'це', 'там', 'тут'}:
        return ''
    return cleaned


def title_source_from_title(title: str) -> str:
    if ' - ' in title:
        candidate = normalize_entity(title.rsplit(' - ', 1)[1])
        if 1 <= len(candidate.split()) <= 6:
            return candidate
    return ''


def official_categories_for_title(title: str) -> list[str]:
    low = title.lower()
    categories = []
    for category, patterns in OFFICIAL_CATEGORY_PATTERNS.items():
        if any(pattern in low for pattern in patterns):
            categories.append(category)
    return categories


def is_official_entity(entity: str) -> bool:
    low = entity.lower()
    return any(marker in low for marker in OFFICIAL_ENTITY_MARKERS)


def extract_sources(text: str, title_source: str) -> tuple[list[str], int, int]:
    found: list[str] = []
    if title_source:
        found.append(title_source)
    for raw in PERSON_SOURCE_RE.findall(text):
        entity = normalize_entity(raw)
        if entity:
            found.append(entity)
    for raw in LEADING_SOURCE_RE.findall(text):
        entity = normalize_entity(raw)
        if entity:
            found.append(entity)
    deduped: list[str] = []
    seen: set[str] = set()
    for entity in found:
        key = entity.lower()
        if key not in seen:
            seen.add(key)
            deduped.append(entity)
    official_count = sum(1 for entity in deduped if is_official_entity(entity))
    non_official_count = max(len(deduped) - official_count, 0)
    return deduped, official_count, non_official_count


def extract_article_fields(url: str, html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, 'html.parser')
    title = ''
    og_title = soup.find('meta', attrs={'property': 'og:title'})
    if og_title and og_title.get('content'):
        title = og_title['content'].strip()
    if not title and soup.title and soup.title.string:
        title = soup.title.string.strip()

    description = ''
    meta_description = soup.find('meta', attrs={'name': 'description'})
    if meta_description and meta_description.get('content'):
        description = meta_description['content'].strip()

    published = ''
    for script in soup.find_all('script', attrs={'type': 'application/ld+json'}):
        raw = script.string or script.get_text(strip=True)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        payloads = data if isinstance(data, list) else [data]
        for payload in payloads:
            if isinstance(payload, dict) and payload.get('@type') == 'NewsArticle':
                published = payload.get('datePublished', '') or published
                break
        if published:
            break
    if not published:
        meta_published = soup.find('meta', attrs={'property': 'article:published_time'})
        if meta_published and meta_published.get('content'):
            published = meta_published['content'].strip()

    body_text = ''
    body_node = soup.select_one('div.newsText')
    if not body_node:
        body_node = soup.find('article')
    if body_node:
        paragraphs = [
            p.get_text(' ', strip=True)
            for p in body_node.find_all('p')
            if p.get_text(' ', strip=True)
        ]
        if paragraphs:
            body_text = '\n'.join(paragraphs)
        else:
            body_text = body_node.get_text(' ', strip=True)
    body_text = re.sub(r'\s+', ' ', body_text).strip()

    return {
        'title': title,
        'description': description,
        'published': published,
        'text': body_text,
    }


def build_record(period: dict[str, object], url: str, html: str) -> ArticleRecord | None:
    fields = extract_article_fields(url, html)
    title = fields['title']
    if not title:
        return None
    published_dt = parse_iso_datetime(fields['published'])
    if not published_dt:
        return None
    published_date = published_dt.date()
    if not (period['start'] <= published_date <= period['end']):
        return None

    rubric = rubric_from_url(url)
    text = fields['text']
    title_source = title_source_from_title(title)
    official_categories = official_categories_for_title(title)
    official_title = bool(official_categories)
    sources, official_source_count, non_official_source_count = extract_sources(text, title_source)
    source_count = len(sources)

    attributed_title = bool(title_source)
    low_text = text.lower()
    balance_signal = non_official_source_count > 0 or any(marker in low_text for marker in BALANCE_MARKERS)
    primary_news_subset = rubric in PRIMARY_RUBRICS
    likely_parket = (
        primary_news_subset
        and official_title
        and source_count <= 1
        and official_source_count >= 1
        and not balance_signal
    )
    balance_risk = (
        primary_news_subset
        and official_title
        and source_count <= 1
        and non_official_source_count == 0
    )
    excerpt = (text[:320] + '...') if len(text) > 320 else text

    return ArticleRecord(
        period_slug=period['slug'],
        period_label=period['label'],
        url=url,
        date_published=published_date.isoformat(),
        month=published_date.strftime('%Y-%m'),
        title=title,
        description=fields['description'],
        rubric=rubric,
        word_count=len(text.split()),
        title_source=title_source,
        source_count=source_count,
        official_source_count=official_source_count,
        non_official_source_count=non_official_source_count,
        official_title=official_title,
        official_categories=official_categories,
        attributed_title=attributed_title,
        balance_signal=balance_signal,
        likely_parket=likely_parket,
        balance_risk=balance_risk,
        primary_news_subset=primary_news_subset,
        excerpt=excerpt,
    )


def collect_period_entries(session: requests.Session, period: dict[str, object]) -> list[str]:
    urls: dict[str, str] = {}
    weeks = iso_weeks_between(period['start'], period['end'])
    for index, (year, week) in enumerate(weeks, start=1):
        if index == 1 or index % 4 == 0:
            print(f"[{period['slug']}] sitemap week {index}/{len(weeks)} -> {year}/{week}")
        sitemap_url = f'https://www.ukrinform.ua/sitemap/{year}/{week}.xml'
        xml_text = fetch_text(session, sitemap_url)
        if not xml_text:
            continue
        for item in parse_sitemap(xml_text):
            loc = item['loc']
            rubric = rubric_from_url(loc)
            if rubric in EXCLUDED_RUBRICS:
                continue
            urls[loc] = item['lastmod']
    return sorted(urls)


def process_period(session: requests.Session, period: dict[str, object], max_workers: int = 10) -> list[ArticleRecord]:
    urls = collect_period_entries(session, period)
    (DATA_DIR / f"{period['slug']}_urls.json").write_text(
        json.dumps(urls, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    print(f"[{period['slug']}] collected {len(urls)} candidate urls from sitemap")
    records: list[ArticleRecord] = []

    def worker(target_url: str) -> ArticleRecord | None:
        local_session = requests_session()
        html = fetch_text(local_session, target_url)
        if not html:
            return None
        return build_record(period, target_url, html)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(worker, url): url for url in urls}
        for index, future in enumerate(as_completed(futures), start=1):
            record = future.result()
            if record:
                records.append(record)
            if index % 250 == 0:
                print(f"[{period['slug']}] processed {index}/{len(urls)} urls")

    records.sort(key=lambda item: (item.date_published, item.url))
    output_path = DATA_DIR / f"{period['slug']}_articles.json"
    output_path.write_text(
        json.dumps([record.__dict__ for record in records], ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    csv_path = DATA_DIR / f"{period['slug']}_articles.csv"
    with csv_path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0].__dict__.keys()) if records else [])
        if records:
            writer.writeheader()
            for record in records:
                writer.writerow(record.__dict__)
    return records


def percent(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round((numerator / denominator) * 100, 2)


def summarize_period(records: list[ArticleRecord], period: dict[str, object]) -> dict[str, object]:
    if not records:
        return {
            'slug': period['slug'],
            'label': period['label'],
            'short_label': period['short_label'],
            'article_count': 0,
        }

    primary = [record for record in records if record.primary_news_subset]
    article_count = len(records)
    primary_count = len(primary)
    official_title_count = sum(record.official_title for record in primary)
    attributed_title_count = sum(record.attributed_title for record in primary)
    parket_count = sum(record.likely_parket for record in primary)
    balance_risk_count = sum(record.balance_risk for record in primary)
    non_official_source_count = sum(record.non_official_source_count > 0 for record in primary)
    one_source_count = sum(record.source_count <= 1 for record in primary)

    return {
        'slug': period['slug'],
        'label': period['label'],
        'short_label': period['short_label'],
        'article_count': article_count,
        'primary_news_count': primary_count,
        'official_title_share': percent(official_title_count, primary_count),
        'attributed_title_share': percent(attributed_title_count, primary_count),
        'likely_parket_share': percent(parket_count, primary_count),
        'balance_risk_share': percent(balance_risk_count, primary_count),
        'non_official_source_share': percent(non_official_source_count, primary_count),
        'single_source_share': percent(one_source_count, primary_count),
        'median_word_count': int(statistics.median([record.word_count for record in primary])) if primary else 0,
    }


def monthly_breakdown(records: list[ArticleRecord]) -> list[dict[str, object]]:
    buckets: dict[tuple[str, str], list[ArticleRecord]] = defaultdict(list)
    for record in records:
        if record.primary_news_subset:
            buckets[(record.period_slug, record.month)].append(record)

    rows: list[dict[str, object]] = []
    for (period_slug, month), items in sorted(buckets.items()):
        rows.append({
            'period_slug': period_slug,
            'month': month,
            'article_count': len(items),
            'official_title_share': percent(sum(item.official_title for item in items), len(items)),
            'likely_parket_share': percent(sum(item.likely_parket for item in items), len(items)),
            'balance_risk_share': percent(sum(item.balance_risk for item in items), len(items)),
            'non_official_source_share': percent(sum(item.non_official_source_count > 0 for item in items), len(items)),
        })
    return rows


def rubric_breakdown(records: list[ArticleRecord]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[ArticleRecord]] = defaultdict(list)
    for record in records:
        if record.primary_news_subset:
            grouped[record.period_slug].append(record)

    output: dict[str, list[dict[str, object]]] = {}
    for period_slug, items in grouped.items():
        rubric_groups: dict[str, list[ArticleRecord]] = defaultdict(list)
        for item in items:
            rubric_groups[item.rubric].append(item)
        rows = []
        for rubric, rubric_items in sorted(rubric_groups.items()):
            rows.append({
                'rubric': rubric,
                'article_count': len(rubric_items),
                'official_title_share': percent(sum(item.official_title for item in rubric_items), len(rubric_items)),
                'likely_parket_share': percent(sum(item.likely_parket for item in rubric_items), len(rubric_items)),
            })
        output[period_slug] = rows
    return output


def category_counts(records: list[ArticleRecord]) -> dict[str, dict[str, int]]:
    output: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        if not record.primary_news_subset:
            continue
        for category in record.official_categories:
            output[record.period_slug][category] += 1
    return {period_slug: dict(counter) for period_slug, counter in output.items()}


def high_risk_examples(records: list[ArticleRecord], limit: int = 60) -> dict[str, list[dict[str, object]]]:
    output: dict[str, list[dict[str, object]]] = {}
    for period in PERIODS:
        period_records = [
            record for record in records
            if record.period_slug == period['slug'] and record.primary_news_subset
        ]
        period_records.sort(
            key=lambda item: (
                int(item.likely_parket),
                int(item.balance_risk),
                item.official_source_count,
                -item.non_official_source_count,
                item.date_published,
            ),
            reverse=True,
        )
        output[period['slug']] = [record.__dict__ for record in period_records[:limit]]
    return output


def narrative(summary_by_slug: dict[str, dict[str, object]]) -> list[str]:
    first = summary_by_slug['before_exclusion_matsuka']
    second = summary_by_slug['before_reinclusion_after_departure']
    lines = []
    lines.append(
        'Дослідження порівнює два періоди: 09.11.2023-25.04.2024 '
        '(перед виключенням Укрінформу з білого списку ІМІ) та 01.07.2025-15.12.2025 '
        '(період перед повторним включенням до білого списку 16.12.2025).'
    )
    lines.append(
        f"У новинному піднаборі частка матеріалів з офіційним актором у заголовку становила "
        f"{first.get('official_title_share', 0)}% у першому періоді проти "
        f"{second.get('official_title_share', 0)}% у другому."
    )
    lines.append(
        f"Частка евристично позначених як 'ймовірний паркет' матеріалів становила "
        f"{first.get('likely_parket_share', 0)}% у першому періоді та "
        f"{second.get('likely_parket_share', 0)}% у другому."
    )
    lines.append(
        f"Частка матеріалів із хоча б одним неофіційним джерелом становила "
        f"{first.get('non_official_source_share', 0)}% у першому періоді та "
        f"{second.get('non_official_source_share', 0)}% у другому."
    )
    lines.append(
        'Ці показники не є прямою заміною ручної оцінки ІМІ, але дають відтворювану '
        'масову перевірку на всьому доступному корпусі матеріалів, а не на нерозкритій вибірці.'
    )
    return lines


def write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def write_methodology(path: Path) -> None:
    content = (
        '# Методологія дослідження\n\n'
        '## Що порівнюється\n'
        '- Період 1: 09.11.2023-25.04.2024.\n'
        '- Період 2: 01.07.2025-15.12.2025.\n\n'
        '## Джерела\n'
        '- Публічні sitemap Укрінформу.\n'
        '- Публічні сторінки матеріалів Укрінформу.\n'
        '- Публічні тексти ІМІ про білий список і методологію.\n\n'
        '## Як рахується корпус\n'
        '- Для кожного періоду скрипт проходить відповідні тижневі sitemap Укрінформу.\n'
        '- Із кожної знайденої сторінки витягуються дата, заголовок, рубрика, опис і текст статті.\n'
        '- Окремо формується новинний піднабір для суспільно-політичних рубрик.\n\n'
        '## Евристики\n'
        '- official_title: у заголовку є актор державної або силової вертикалі.\n'
        '- likely_parket: офіційний актор у заголовку, не більш як одне джерело, відсутній сигнал альтернативної позиції.\n'
        '- balance_risk: офіційний актор у заголовку і не виявлено неофіційного джерела.\n'
        '- non_official_source_share: у тексті виявлено хоча б одне неофіційне джерело або сторону.\n\n'
        '## Обмеження\n'
        '- Це не ручна оцінка за всіма критеріями ІМІ.\n'
        '- Показник паркету в ІМІ публічно не формалізований окремим індикатором, тому тут використано відтворювану наближену евристику.\n'
        '- Дашборд краще читати як інструмент аудиту корпусу, а не як остаточний юридичний доказ.\n'
    )
    path.write_text(content, encoding='utf-8')


def build_dashboard_html(study: dict[str, object]) -> str:
    payload = json.dumps(study, ensure_ascii=False).replace('</script>', '<\\/script>')
    return """<!DOCTYPE html>
<html lang='uk'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>Укрінформ vs ІМІ: аудит двох періодів</title>
  <style>
    :root {
      --bg: #f5efe4;
      --panel: #fffaf2;
      --ink: #22303c;
      --muted: #60707f;
      --accent: #b24a2e;
      --accent2: #0a6a6a;
      --line: #e2d4bf;
    }
    * { box-sizing: border-box; }
    body { margin: 0; background: linear-gradient(180deg, #efe6d8, var(--bg)); color: var(--ink); font-family: Georgia, 'Times New Roman', serif; }
    header { padding: 40px 24px 24px; border-bottom: 1px solid var(--line); background: rgba(255,250,242,0.92); position: sticky; top: 0; backdrop-filter: blur(10px); }
    main { max-width: 1240px; margin: 0 auto; padding: 24px; }
    h1, h2, h3 { margin: 0 0 12px; }
    p { line-height: 1.55; }
    .lede { max-width: 920px; color: var(--muted); }
    .section { margin: 28px 0; }
    .card { background: var(--panel); border: 1px solid var(--line); border-radius: 18px; padding: 18px; box-shadow: 0 12px 28px rgba(30, 25, 20, 0.05); }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; }
    .metric { font-size: 2rem; font-weight: 700; margin: 6px 0; }
    .muted { color: var(--muted); }
    .pills { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 10px; }
    .pill { display: inline-block; padding: 6px 10px; border-radius: 999px; background: #f1ddd5; font-size: 0.92rem; }
    .pill.alt { background: #d9eeee; }
    .bars { display: grid; gap: 14px; }
    .bar-row { display: grid; grid-template-columns: 240px 1fr; gap: 12px; align-items: center; }
    .track { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }
    .track > div { background: #ecdfcd; border-radius: 999px; overflow: hidden; height: 18px; }
    .fill-a { background: var(--accent); height: 100%; }
    .fill-b { background: var(--accent2); height: 100%; }
    .legend { display: flex; gap: 12px; font-size: 0.92rem; margin: 10px 0 18px; color: var(--muted); }
    .dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; margin-right: 6px; }
    .table-wrap { overflow: auto; border: 1px solid var(--line); border-radius: 18px; background: var(--panel); }
    table { width: 100%; border-collapse: collapse; font-size: 0.95rem; }
    th, td { padding: 12px 14px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
    th { background: #f8efe2; }
    a { color: var(--accent); }
    .small { font-size: 0.9rem; }
    @media (max-width: 780px) {
      .bar-row { grid-template-columns: 1fr; }
      header { position: static; }
    }
  </style>
</head>
<body>
  <header>
    <h1>Укрінформ vs ІМІ: аудит двох періодів</h1>
    <p class='lede'>Локальний дашборд для порівняння періоду перед виключенням Укрінформу з білого списку ІМІ та періоду перед повторним включенням. Усі числа нижче побудовані на повному доступному корпусі матеріалів, зібраному через sitemap та сторінки статей.</p>
  </header>
  <main>
    <section class='section card'>
      <div class='pills' id='period-pills'></div>
      <div id='narrative'></div>
    </section>

    <section class='section'>
      <h2>Ключові цифри</h2>
      <div class='grid' id='summary-cards'></div>
    </section>

    <section class='section'>
      <h2>Порівняння метрик</h2>
      <div class='legend'>
        <span><span class='dot' style='background:var(--accent)'></span>Період перед виключенням</span>
        <span><span class='dot' style='background:var(--accent2)'></span>Період перед повторним включенням</span>
      </div>
      <div class='card bars' id='comparison-bars'></div>
    </section>

    <section class='section'>
      <h2>Місячна динаміка</h2>
      <div class='table-wrap'><table id='monthly-table'></table></div>
    </section>

    <section class='section'>
      <h2>Рубрики</h2>
      <div class='grid' id='rubric-grids'></div>
    </section>

    <section class='section'>
      <h2>Офіційні категорії в заголовках</h2>
      <div class='table-wrap'><table id='category-table'></table></div>
    </section>

    <section class='section'>
      <h2>Приклади матеріалів з високим ризиком</h2>
      <p class='small muted'>Це не вирок окремим текстам, а список матеріалів, які за евристикою варто читати першими в ручному аудиті.</p>
      <div class='grid' id='risk-grids'></div>
    </section>

    <section class='section card small muted'>
      <strong>Що важливо пам'ятати:</strong> дашборд не відтворює ручну експертну оцінку ІМІ 1:1. Він дає перевірювану масову альтернативу на всьому корпусі, тоді як публічна вибірка ІМІ для білого списку не розкрита повністю.
    </section>
  </main>

  <script id='study-data' type='application/json'>__STUDY_JSON__</script>
  <script>
    const study = JSON.parse(document.getElementById('study-data').textContent);
    const summaryBySlug = Object.fromEntries(study.summary.map(item => [item.slug, item]));
    const first = summaryBySlug.before_exclusion_matsuka;
    const second = summaryBySlug.before_reinclusion_after_departure;

    document.getElementById('period-pills').innerHTML = study.periods.map((period, idx) =>
      `<span class="pill ${idx === 1 ? 'alt' : ''}">${period.short_label}</span>`
    ).join('');

    document.getElementById('narrative').innerHTML = study.narrative.map(line => `<p>${line}</p>`).join('');

    const cards = [
      ['Матеріалів у корпусі', `${first.article_count.toLocaleString('uk-UA')} vs ${second.article_count.toLocaleString('uk-UA')}`],
      ['Новинний піднабір', `${first.primary_news_count.toLocaleString('uk-UA')} vs ${second.primary_news_count.toLocaleString('uk-UA')}`],
      ['Офіційний актор у заголовку', `${first.official_title_share}% vs ${second.official_title_share}%`],
      ['Ймовірний паркет', `${first.likely_parket_share}% vs ${second.likely_parket_share}%`],
      ['Ризик дисбалансу', `${first.balance_risk_share}% vs ${second.balance_risk_share}%`],
      ['Є неофіційне джерело', `${first.non_official_source_share}% vs ${second.non_official_source_share}%`],
      ['Одне джерело або жодного', `${first.single_source_share}% vs ${second.single_source_share}%`],
      ['Медіанна довжина тексту', `${first.median_word_count} vs ${second.median_word_count} слів`],
    ];
    document.getElementById('summary-cards').innerHTML = cards.map(([label, value]) => `
      <div class="card"><div class="muted">${label}</div><div class="metric">${value}</div></div>
    `).join('');

    const metricLabels = [
      ['official_title_share', 'Офіційний актор у заголовку'],
      ['likely_parket_share', 'Ймовірний паркет'],
      ['balance_risk_share', 'Ризик дисбалансу'],
      ['non_official_source_share', 'Є неофіційне джерело'],
      ['single_source_share', 'Одне джерело або жодного'],
    ];
    document.getElementById('comparison-bars').innerHTML = metricLabels.map(([key, label]) => `
      <div class="bar-row">
        <div>${label}</div>
        <div class="track">
          <div><div class="fill-a" style="width:${first[key]}%"></div></div>
          <div><div class="fill-b" style="width:${second[key]}%"></div></div>
        </div>
      </div>
      <div class="small muted">${first[key]}% vs ${second[key]}%</div>
    `).join('');

    const monthlyHeader = `<tr><th>Період</th><th>Місяць</th><th>Матеріалів</th><th>Офіційний заголовок</th><th>Ймовірний паркет</th><th>Ризик дисбалансу</th><th>Є неофіційне джерело</th></tr>`;
    const monthlyRows = study.monthly.map(row => `
      <tr>
        <td>${summaryBySlug[row.period_slug].short_label}</td>
        <td>${row.month}</td>
        <td>${row.article_count}</td>
        <td>${row.official_title_share}%</td>
        <td>${row.likely_parket_share}%</td>
        <td>${row.balance_risk_share}%</td>
        <td>${row.non_official_source_share}%</td>
      </tr>
    `).join('');
    document.getElementById('monthly-table').innerHTML = monthlyHeader + monthlyRows;

    document.getElementById('rubric-grids').innerHTML = study.periods.map((period, idx) => {
      const rows = (study.rubrics[period.slug] || []).map(row => `
        <tr><td>${row.rubric}</td><td>${row.article_count}</td><td>${row.official_title_share}%</td><td>${row.likely_parket_share}%</td></tr>
      `).join('');
      return `
        <div class="card">
          <h3>${period.label}</h3>
          <div class="table-wrap"><table><tr><th>Рубрика</th><th>Матеріалів</th><th>Офіційний заголовок</th><th>Ймовірний паркет</th></tr>${rows}</table></div>
        </div>
      `;
    }).join('');

    const categories = Array.from(new Set([
      ...Object.keys(study.official_categories.before_exclusion_matsuka || {}),
      ...Object.keys(study.official_categories.before_reinclusion_after_departure || {}),
    ])).sort();
    document.getElementById('category-table').innerHTML = '<tr><th>Категорія</th><th>Перед виключенням</th><th>Перед повторним включенням</th></tr>' +
      categories.map(category => `
        <tr>
          <td>${category}</td>
          <td>${(study.official_categories.before_exclusion_matsuka || {})[category] || 0}</td>
          <td>${(study.official_categories.before_reinclusion_after_departure || {})[category] || 0}</td>
        </tr>
      `).join('');

    document.getElementById('risk-grids').innerHTML = study.periods.map(period => {
      const rows = (study.high_risk_examples[period.slug] || []).slice(0, 25).map(row => `
        <tr>
          <td>${row.date_published}</td>
          <td><a href="${row.url}" target="_blank" rel="noreferrer">${row.title}</a><div class="small muted">${row.rubric}</div></td>
          <td>${row.source_count}</td>
          <td>${row.official_source_count}</td>
          <td>${row.likely_parket ? 'так' : 'ні'}</td>
        </tr>
      `).join('');
      return `
        <div class="card">
          <h3>${period.label}</h3>
          <div class="table-wrap"><table><tr><th>Дата</th><th>Матеріал</th><th>Джерел</th><th>Офіційних</th><th>Ймовірний паркет</th></tr>${rows}</table></div>
        </div>
      `;
    }).join('');
  </script>
</body>
</html>
""".replace('__STUDY_JSON__', payload)


def main() -> None:
    ensure_dirs()
    session = requests_session()
    all_records: list[ArticleRecord] = []
    period_summaries: list[dict[str, object]] = []

    for period in PERIODS:
        print(f"Collecting {period['slug']} ...")
        records = process_period(session, period)
        print(f"Collected {len(records)} records for {period['slug']}")
        all_records.extend(records)
        period_summaries.append(summarize_period(records, period))

    summaries_by_slug = {summary['slug']: summary for summary in period_summaries}
    study = {
        'periods': PERIODS,
        'summary': period_summaries,
        'monthly': monthly_breakdown(all_records),
        'rubrics': rubric_breakdown(all_records),
        'official_categories': category_counts(all_records),
        'high_risk_examples': high_risk_examples(all_records),
        'narrative': narrative(summaries_by_slug),
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'sources': {
            'imi_methodology': 'https://imi.org.ua/monitorings/metodolohiia-otsinky-profesiynosti-ta-vidpovidal-nosti-onlayn-media-i28289',
            'imi_exclusion': 'https://imi.org.ua/news/bilyj-spysok-11-media-shho-staly-najyakisnishymy-i60964',
            'imi_reinclusion': 'https://imi.org.ua/monitorings/bilyj-spysok-imi-za-druge-pivrichchya-2025-roku-uvijshly-17-media',
        },
    }

    write_json(DATA_DIR / 'study.json', study)
    write_methodology(BASE_DIR / 'METHODOLOGY.md')
    (BASE_DIR / 'README.txt').write_text(
        'Відкрийте файл dashboard/index.html у браузері. Дані лежать у папці data/.\n',
        encoding='utf-8',
    )
    (DASHBOARD_DIR / 'study.json').write_text(
        json.dumps(study, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    (DASHBOARD_DIR / 'index.html').write_text(build_dashboard_html(study), encoding='utf-8')
    print('Study complete.')


if __name__ == '__main__':
    main()
