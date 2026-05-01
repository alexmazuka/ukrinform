from __future__ import annotations

import ast
import json
import math
import re
from typing import Iterable


OFFICIAL_PATTERNS = {
    'Президент / ОП': {
        'exact': ['zelenskij', 'zelensky', 'prezident', 'opu', 'yermak', 'ermak'],
        'prefix': ['zelensk', 'prezident', 'ofis-prezidenta', 'yermak', 'ermak'],
    },
    'Уряд / Кабмін': {
        'exact': [
            'kabmin', 'kabminu', 'kabministr', 'uryad', 'uryadu', 'urad', 'uradu',
            'uradi', 'uradova', 'uradovij', 'smygal', 'shmygal',
            'premyer', 'premier', 'svyrydenko', 'svyridenko',
        ],
        'prefix': [
            'kabmin', 'uryad', 'urad', 'smygal', 'shmygal',
            'premyer', 'premier', 'svyriden', 'svyryden',
        ],
    },
    'Парламент': {
        'exact': [
            'rada', 'radoyu', 'radoju', 'verhovna', 'verhovnoyu', 'verhovnoju',
            'nardep', 'nardepy', 'deputat', 'deputaty', 'komitet', 'stefancuk',
        ],
        'prefix': ['verhovn', 'nardep', 'stefancuk'],
    },
    'Міністерства': {
        'exact': [
            'ministr', 'ministra', 'ministry', 'ministrom', 'ministerstvo',
            'ministerstva', 'mzs', 'mvs', 'minfin', 'minekonom', 'minoboroni',
            'mincifri', 'minkult', 'minstratehprom', 'minekoenergo',
            'umerov', 'umerova', 'kuleba', 'kulebu', 'sybiha', 'shmygal',
            'shmyhalja', 'fedorov', 'fedorova',
        ],
        'prefix': [
            'ministr', 'ministerstv', 'minoboron', 'minekonom', 'minfin',
            'mincifr', 'minkult', 'minstrateh', 'umerov', 'kuleb', 'sybih',
            'fedorov',
        ],
    },
    'Силовий блок': {
        'exact': [
            'genshtab', 'zsu', 'sbu', 'gur', 'dpsu', 'dsns', 'syrskij', 'sirskij',
            'syrskogo', 'sirskogo', 'zaluzhnij', 'zaluzhnogo', 'budanov', 'budanova',
        ],
        'prefix': ['genshtab', 'zaluzhn', 'syrsk', 'sirsk', 'budanov'],
        'multi_word': ['sili-oboroni', 'syl-oborony'],
    },
    'Регіональна влада': {
        'exact': ['ova', 'kmva', 'kmda', 'oblrada', 'miskrada'],
        'prefix': ['oblrada', 'miskrada'],
    },
    'Держструктури / держкомпанії': {
        'exact': [
            'ukrzaliznicia', 'ukrzaliznycia', 'ukrenergo', 'naftogaz', 'oschadbank',
            'pryvatbank', 'pension', 'nbu', 'nabu', 'sap',
        ],
        'prefix': ['ukrzaliznic', 'ukrzaliznyc', 'ukrenergo', 'naftogaz'],
    },
}

OFFICIAL_ENTITY_MARKERS = {
    'президент', 'офіс президента', 'опу', 'єрмак', 'ермак',
    'уряд', 'кабмін', 'кабінет міністрів', 'прем’єр', "прем'єр", 'шмигаль',
    'верховна рада', 'нардеп', 'депутат', 'комітет', 'стефанчук',
    'міністр', 'міністерство', 'мзс', 'мвс', 'мінфін', 'мінекономіки',
    'міноборони', 'мінцифри', 'мінкульт', 'умєров', 'кулеба', 'сибіга',
    'генштаб', 'зсу', 'сбу', 'гур', 'дпсу', 'дснс', 'сили оборони',
    'сирський', 'залужний', 'буданов',
    'ова', 'кмва', 'кмда', 'облрада', 'міськрада', 'мер',
    'укрзалізниця', 'укренерго', 'нафтогаз', 'фонд держмайна',
    'пенсійний фонд', 'податкова', 'митниця', 'нбу', 'набу', 'сап',
}

REPORTING_VERBS = (
    'заявив', 'заявила', 'повідомив', 'повідомила', 'сказав', 'сказала',
    'наголосив', 'наголосила', 'зауважив', 'зауважила', 'додав', 'додала',
    'підкреслив', 'підкреслила', 'відзначив', 'відзначила', 'розповів',
    'розповіла', 'написав', 'написала', 'зазначив', 'зазначила',
)

PERSON_RE = re.compile(
    r'([А-ЯІЇЄҐA-Z][^.!?\n]{1,90}?)\s+(?:' + '|'.join(REPORTING_VERBS) + r')\b'
)
LEADING_RE = re.compile(
    r'(?:За словами|За даними|Як повідомив|Як повідомила|Як повідомили|'
    r'Як зазначив|Як зазначила|Повідомляє)\s+([^,.;:\n]{1,90})'
)
HEADLINE_SRC_RE = re.compile(r'\s[—–-]\s*([А-ЯІЇЄҐA-Z][А-ЯІЇЄҐа-яіїєґA-Za-z\s]{2,60}?)\s*$')
PRO_CE_RE = re.compile(
    r'[Пп]ро це (?:повідомляє|повідомили|йдеться\s+(?:в|у)|'
    r'зазначається\s+(?:в|у)|сказано\s+(?:в|у)|(?:розповів|розповіла))\s+'
    r'([А-ЯІЇЄҐA-Z][^.!?\n]{2,80})'
)
AS_TRANSMITS_RE = re.compile(
    r'[Яя]к (?:передає|передають|пише|пишуть|повідомляє|повідомляють)\s+'
    r'Укрінформ,?\s*про це\s+([А-ЯІЇЄҐA-Z][^.!?\n]{2,70})'
)
IN_ORG_RE = re.compile(
    r'(?:повідомили|зазначили|уточнили|наголосили|підкреслили|'
    r'сказали|вважають|додали)\s+(?:в|у|на)\s+([А-ЯІЇЄҐA-Z][^.!?\n]{2,50})'
)
OG_SRC_RE = re.compile(r'[—–]\s*([А-ЯІЇЄҐA-Z][^.!?\n—–]{2,60}?)\s*\.?$')


def parse_bool(value: object) -> bool:
    return str(value).strip().lower() == 'true'


def parse_int(value: object, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_categories(value: object) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    for loader in (json.loads, ast.literal_eval):
        try:
            data = loader(text)
        except Exception:
            continue
        if isinstance(data, list):
            return [str(item) for item in data if str(item).strip()]
    return [item for item in text.split('|') if item]


def slug_from_url(url: str) -> str:
    tail = url.rstrip('/').split('/')[-1].replace('.html', '')
    return tail.split('-', 1)[1] if '-' in tail else tail


def official_categories_for_slug(slug: str) -> list[str]:
    words = [word for word in re.split(r'[-_.]', slug.lower()) if word]
    if not words:
        return []

    matched: list[str] = []
    low_slug = slug.lower()
    for category, patterns in OFFICIAL_PATTERNS.items():
        if any(word in patterns.get('exact', []) for word in words):
            matched.append(category)
            continue
        prefix_match = any(
            len(prefix) >= 5 and word.startswith(prefix)
            for word in words
            for prefix in patterns.get('prefix', [])
        )
        if prefix_match:
            matched.append(category)
            continue
        if any(pattern in low_slug for pattern in patterns.get('multi_word', [])):
            matched.append(category)
    return matched


def normalize_entity(text: str) -> str:
    cleaned = re.sub(r'\s+', ' ', text.replace('\xa0', ' ')).strip(' ,;:.!?"“”«»()[]—–-')
    if len(cleaned.split()) > 10 or len(cleaned) < 3:
        return ''
    lowered = cleaned.lower()
    if lowered in {'він', 'вона', 'вони', 'це', 'там', 'тут'}:
        return ''
    return cleaned


def classify_source(entity: str) -> str:
    lowered = entity.lower()
    if any(marker in lowered for marker in OFFICIAL_ENTITY_MARKERS):
        return 'official'
    return 'non_official'


def extract_sources_v2(title: str, og_description: str, body_text: str) -> tuple[int, int, int, list[str]]:
    sources: dict[str, str] = {}

    def remember(raw: str) -> None:
        entity = normalize_entity(raw)
        if entity and entity not in sources:
            sources[entity] = classify_source(entity)

    for raw in PERSON_RE.findall(body_text):
        remember(raw)
    for raw in LEADING_RE.findall(body_text):
        remember(raw)

    headline_match = HEADLINE_SRC_RE.search(title)
    if headline_match:
        remember(headline_match.group(1))

    for raw in PRO_CE_RE.findall(body_text):
        remember(raw)
    for raw in AS_TRANSMITS_RE.findall(body_text):
        remember(raw)
    for raw in IN_ORG_RE.findall(body_text):
        remember(raw)

    if og_description:
        og_match = OG_SRC_RE.search(og_description)
        if og_match:
            entity = normalize_entity(og_match.group(1))
            if entity and 'укрінформ' not in entity.lower() and entity not in sources:
                sources[entity] = classify_source(entity)

    official_count = sum(source_type == 'official' for source_type in sources.values())
    non_official_count = sum(source_type == 'non_official' for source_type in sources.values())
    return len(sources), official_count, non_official_count, list(sources.keys())


def compute_risks(is_official: bool, source_count: int, non_official_count: int) -> tuple[bool, bool]:
    likely_parket = is_official and source_count <= 1 and non_official_count == 0
    balance_risk = is_official and non_official_count == 0
    return likely_parket, balance_risk


def canonicalize_corpus_row(row: dict[str, str]) -> dict[str, str]:
    official_categories = official_categories_for_slug(row.get('slug_text', ''))
    is_official = parse_bool(row.get('official_v3')) or bool(official_categories)
    source_count = parse_int(
        row.get('sc_v2'),
        default=parse_int(row.get('source_count'), default=-1),
    )
    official_source_count = parse_int(
        row.get('oc_v2'),
        default=parse_int(row.get('official_source_count'), default=-1),
    )
    non_official_source_count = parse_int(
        row.get('noc_v2'),
        default=parse_int(row.get('non_official_source_count'), default=-1),
    )
    likely_parket, balance_risk = compute_risks(
        is_official,
        source_count,
        non_official_source_count,
    )

    output = dict(row)
    output['official_slug'] = str(is_official)
    output['official_categories'] = json.dumps(official_categories, ensure_ascii=False)
    output['source_count'] = str(source_count)
    output['official_source_count'] = str(official_source_count)
    output['non_official_source_count'] = str(non_official_source_count)
    output['likely_parket'] = str(likely_parket)
    output['balance_risk'] = str(balance_risk)
    return output


def build_explorer_row(row: dict[str, str]) -> dict[str, object]:
    return {
        'u': row['url'],
        't': row.get('actual_title') or slug_from_url(row['url']).replace('-', ' '),
        'd': row['date_value'],
        'm': row['month'],
        'r': row['rubric'].replace('rubric-', ''),
        'of': parse_bool(row['official_slug']),
        'pk': parse_bool(row['likely_parket']),
        'br': parse_bool(row['balance_risk']),
        'sc': parse_int(row['source_count'], default=-1),
        'oc': parse_int(row['official_source_count'], default=-1),
        'noc': parse_int(row['non_official_source_count'], default=-1),
        'ex': row.get('excerpt', ''),
    }


def chi_square_2x2(success_a: int, fail_a: int, success_b: int, fail_b: int) -> float:
    total = success_a + fail_a + success_b + fail_b
    denominator = (success_a + fail_a) * (success_b + fail_b) * (success_a + success_b) * (fail_a + fail_b)
    if not denominator:
        return 0.0
    numerator = total * (success_a * fail_b - fail_a * success_b) ** 2
    return numerator / denominator


def p_value_df1(chi_square_value: float) -> float:
    return math.erfc(math.sqrt(chi_square_value / 2.0))


def cohens_h(rate_a: float, rate_b: float) -> float:
    return 2 * math.asin(math.sqrt(rate_a)) - 2 * math.asin(math.sqrt(rate_b))


def average(values: Iterable[int]) -> float:
    values = list(values)
    if not values:
        return 0.0
    return sum(values) / len(values)
