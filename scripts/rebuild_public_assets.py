from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from canonical_metrics import (
    average,
    build_explorer_row,
    canonicalize_corpus_row,
    chi_square_2x2,
    classify_source,
    cohens_h,
    compute_risks,
    official_categories_for_slug,
    p_value_df1,
    parse_bool,
    parse_int,
)
DATA = BASE / 'data'
DOCS = BASE / 'docs'
DASHBOARD = BASE / 'dashboard'

CORPUS_V3 = DATA / 'corpus_v3_parsed.csv'
CORPUS_FAST = DATA / 'corpus_fast.csv'
P0_AUDITED = DATA / 'period_zero' / 'p0_audited.json'

CORPUS_FAST_FIELDS = [
    'period_slug',
    'period_label',
    'url',
    'date_value',
    'month',
    'rubric',
    'slug_text',
    'official_slug',
    'official_categories',
    'audit_bucket',
    'audited',
    'actual_title',
    'source_count',
    'official_source_count',
    'non_official_source_count',
    'likely_parket',
    'balance_risk',
    'excerpt',
]

PERIOD_META = {
    'p0': {
        'slug': 'pre_matsuka_white_list',
        'label': 'До Мацуки, коли Укрінформ був у Білому списку',
        'dates': '2023-05-01 to 2023-10-31',
        'imi_status': 'White List',
    },
    'p1': {
        'slug': 'before_exclusion_matsuka',
        'label': 'Перед виключенням за керівництва Олексія Мацуки',
        'dates': '2023-11-09 to 2024-04-25',
        'imi_status': 'Excluded',
    },
    'p2': {
        'slug': 'before_reinclusion_after_departure',
        'label': 'Перед повторним включенням після відходу Олексія Мацуки',
        'dates': '2025-07-01 to 2025-12-15',
        'imi_status': 'Returned to White List',
    },
}


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )


def load_two_period_rows() -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    raw_rows: list[dict[str, str]] = []
    audited_rows: list[dict[str, object]] = []

    with CORPUS_V3.open(newline='', encoding='utf-8') as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            canonical = canonicalize_corpus_row(row)
            raw_rows.append(canonical)

            if not parse_bool(canonical['audited']):
                continue

            period_code = 'p1' if canonical['period_slug'] == PERIOD_META['p1']['slug'] else 'p2'
            audited_rows.append(
                {
                    'period': period_code,
                    'period_slug': canonical['period_slug'],
                    'period_label': canonical['period_label'],
                    'url': canonical['url'],
                    'date': canonical['date_value'],
                    'month': canonical['month'],
                    'rubric': canonical['rubric'],
                    'title': canonical.get('actual_title') or '',
                    'official_slug': parse_bool(canonical['official_slug']),
                    'source_count': parse_int(canonical['source_count'], default=-1),
                    'official_source_count': parse_int(canonical['official_source_count'], default=-1),
                    'non_official_source_count': parse_int(canonical['non_official_source_count'], default=-1),
                    'likely_parket': parse_bool(canonical['likely_parket']),
                    'balance_risk': parse_bool(canonical['balance_risk']),
                    'excerpt': canonical.get('excerpt', ''),
                }
            )

    return raw_rows, audited_rows


def load_period_zero_rows() -> list[dict[str, object]]:
    payload = json.loads(P0_AUDITED.read_text(encoding='utf-8'))
    rows: list[dict[str, object]] = []

    for row in payload:
        if not row.get('audited'):
            continue

        sources = [item.strip() for item in str(row.get('sources', '')).split(';') if item.strip()]
        official_count = sum(1 for source in sources if classify_source(source) == 'official')
        non_official_count = len(sources) - official_count
        is_official = bool(official_categories_for_slug(row.get('slug', '')))
        source_count = int(row.get('sc', 0) or 0)
        likely_parket, balance_risk = compute_risks(is_official, source_count, non_official_count)

        rows.append(
            {
                'period': 'p0',
                'period_slug': PERIOD_META['p0']['slug'],
                'period_label': PERIOD_META['p0']['label'],
                'url': row['url'],
                'date': row['date'],
                'month': row['month'],
                'rubric': row['rubric'],
                'title': row.get('title') or '',
                'official_slug': is_official,
                'source_count': source_count,
                'official_source_count': official_count,
                'non_official_source_count': non_official_count,
                'likely_parket': likely_parket,
                'balance_risk': balance_risk,
                'excerpt': row.get('sources', ''),
            }
        )

    return rows


def write_corpus_fast(rows: list[dict[str, str]]) -> None:
    with CORPUS_FAST.open('w', encoding='utf-8', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=CORPUS_FAST_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, '') for field in CORPUS_FAST_FIELDS})


def build_explorer_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    explorer_rows: list[dict[str, object]] = []
    for row in rows:
        if row['period'] == 'p0':
            explorer_rows.append(
                {
                    'u': row['url'],
                    't': row['title'],
                    'd': row['date'],
                    'm': row['month'],
                    'r': row['rubric'].replace('rubric-', ''),
                    'p': row['period'],
                    'of': row['official_slug'],
                    'pk': row['likely_parket'],
                    'br': row['balance_risk'],
                    'sc': row['source_count'],
                    'oc': row['official_source_count'],
                    'noc': row['non_official_source_count'],
                    'ex': row['excerpt'],
                }
            )
            continue

        base_row = {
            'url': row['url'],
            'actual_title': row['title'],
            'date_value': row['date'],
            'month': row['month'],
            'rubric': row['rubric'],
            'official_slug': str(row['official_slug']),
            'likely_parket': str(row['likely_parket']),
            'balance_risk': str(row['balance_risk']),
            'source_count': str(row['source_count']),
            'official_source_count': str(row['official_source_count']),
            'non_official_source_count': str(row['non_official_source_count']),
            'excerpt': row['excerpt'],
        }
        item = build_explorer_row(base_row)
        item['p'] = row['period']
        explorer_rows.append(item)

    return sorted(explorer_rows, key=lambda row: (row['d'], row['u']))


def build_graph_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(row['month'], row['rubric'].replace('rubric-', ''), row['period'])].append(row)

    graph_rows = []
    for (month, rubric, period), items in sorted(grouped.items()):
        total = len(items)
        parket = sum(item['likely_parket'] for item in items)
        balance = sum(item['balance_risk'] for item in items)
        graph_rows.append(
            {
                'month': month,
                'rubric': rubric,
                'period': period,
                'total': total,
                'parket': parket,
                'parket_pct': round(parket / total * 100, 2),
                'balance': balance,
                'balance_pct': round(balance / total * 100, 2),
                'avg_sources': round(average(item['source_count'] for item in items), 2),
            }
        )

    return graph_rows


def pairwise_metric(a: list[dict[str, object]], b: list[dict[str, object]], key: str) -> dict[str, object]:
    success_a = sum(item[key] for item in a)
    success_b = sum(item[key] for item in b)
    fail_a = len(a) - success_a
    fail_b = len(b) - success_b
    rate_a = success_a / len(a)
    rate_b = success_b / len(b)
    chi = chi_square_2x2(success_a, fail_a, success_b, fail_b)

    return {
        'n_a': len(a),
        'n_b': len(b),
        'count_a': success_a,
        'count_b': success_b,
        'pct_a': round(rate_a * 100, 2),
        'pct_b': round(rate_b * 100, 2),
        'pp_diff': round((rate_a - rate_b) * 100, 2),
        'chi_square': round(chi, 4),
        'p_value': p_value_df1(chi),
        'cohens_h': round(abs(cohens_h(rate_a, rate_b)), 4),
    }


def aggregate_period(rows: list[dict[str, object]]) -> dict[str, object]:
    total = len(rows)
    parket = sum(item['likely_parket'] for item in rows)
    balance = sum(item['balance_risk'] for item in rows)
    return {
        'n_total': total,
        'parket_total': parket,
        'parket_pct_total': round(parket / total * 100, 2),
        'balance_total': balance,
        'balance_pct_total': round(balance / total * 100, 2),
        'avg_sources_total': round(average(item['source_count'] for item in rows), 2),
    }


def build_stats(all_rows: list[dict[str, object]]) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    p0 = [row for row in all_rows if row['period'] == 'p0']
    p1 = [row for row in all_rows if row['period'] == 'p1']
    p2 = [row for row in all_rows if row['period'] == 'p2']
    p0_no_ato = [row for row in p0 if row['rubric'] != 'rubric-ato']
    p1_no_ato = [row for row in p1 if row['rubric'] != 'rubric-ato']
    p2_no_ato = [row for row in p2 if row['rubric'] != 'rubric-ato']

    two_period = {
        'parser_version': 'canonical_v4',
        'date': date.today().isoformat(),
        'description': 'Unified official-slug classifier + improved source parsing + distinct parket/balance formulas',
        'scenarios': {
            'with_ato': {
                'parket': pairwise_metric(p1, p2, 'likely_parket'),
                'balance': pairwise_metric(p1, p2, 'balance_risk'),
                'avg_sources': {
                    'p1': round(average(item['source_count'] for item in p1), 2),
                    'p2': round(average(item['source_count'] for item in p2), 2),
                },
            },
            'without_ato': {
                'parket': pairwise_metric(p1_no_ato, p2_no_ato, 'likely_parket'),
                'balance': pairwise_metric(p1_no_ato, p2_no_ato, 'balance_risk'),
                'avg_sources': {
                    'p1': round(average(item['source_count'] for item in p1_no_ato), 2),
                    'p2': round(average(item['source_count'] for item in p2_no_ato), 2),
                },
            },
        },
        'historical_versions': {
            'v1': 'substring slug matching and limited source extraction',
            'v2': 'expanded source patterns but legacy official/balance logic',
            'v3': 'word-boundary slug classifier',
            'v4': 'single canonical layer used for all published assets',
        },
    }

    three_period = {
        'parser_version': 'canonical_v4',
        'date': date.today().isoformat(),
        'note': 'Period 0 uses stored extracted sources from p0_audited.json, reclassified with the canonical official/non-official rules.',
        'periods': {
            'P0_pre_matsuka': {
                **PERIOD_META['p0'],
                **aggregate_period(p0),
                'n_no_ato': len(p0_no_ato),
                'parket_no_ato': sum(item['likely_parket'] for item in p0_no_ato),
                'parket_pct_no_ato': round(sum(item['likely_parket'] for item in p0_no_ato) / len(p0_no_ato) * 100, 2),
                'balance_no_ato': sum(item['balance_risk'] for item in p0_no_ato),
                'balance_pct_no_ato': round(sum(item['balance_risk'] for item in p0_no_ato) / len(p0_no_ato) * 100, 2),
                'avg_sources_no_ato': round(average(item['source_count'] for item in p0_no_ato), 2),
            },
            'P1_matsuka': {
                **PERIOD_META['p1'],
                **aggregate_period(p1),
                'n_no_ato': len(p1_no_ato),
                'parket_no_ato': sum(item['likely_parket'] for item in p1_no_ato),
                'parket_pct_no_ato': round(sum(item['likely_parket'] for item in p1_no_ato) / len(p1_no_ato) * 100, 2),
                'balance_no_ato': sum(item['balance_risk'] for item in p1_no_ato),
                'balance_pct_no_ato': round(sum(item['balance_risk'] for item in p1_no_ato) / len(p1_no_ato) * 100, 2),
                'avg_sources_no_ato': round(average(item['source_count'] for item in p1_no_ato), 2),
            },
            'P2_after_departure': {
                **PERIOD_META['p2'],
                **aggregate_period(p2),
                'n_no_ato': len(p2_no_ato),
                'parket_no_ato': sum(item['likely_parket'] for item in p2_no_ato),
                'parket_pct_no_ato': round(sum(item['likely_parket'] for item in p2_no_ato) / len(p2_no_ato) * 100, 2),
                'balance_no_ato': sum(item['balance_risk'] for item in p2_no_ato),
                'balance_pct_no_ato': round(sum(item['balance_risk'] for item in p2_no_ato) / len(p2_no_ato) * 100, 2),
                'avg_sources_no_ato': round(average(item['source_count'] for item in p2_no_ato), 2),
            },
        },
        'pairwise_no_ato': {
            'P0_vs_P1': {
                'parket': pairwise_metric(p0_no_ato, p1_no_ato, 'likely_parket'),
                'balance': pairwise_metric(p0_no_ato, p1_no_ato, 'balance_risk'),
            },
            'P0_vs_P2': {
                'parket': pairwise_metric(p0_no_ato, p2_no_ato, 'likely_parket'),
                'balance': pairwise_metric(p0_no_ato, p2_no_ato, 'balance_risk'),
            },
            'P1_vs_P2': {
                'parket': pairwise_metric(p1_no_ato, p2_no_ato, 'likely_parket'),
                'balance': pairwise_metric(p1_no_ato, p2_no_ato, 'balance_risk'),
            },
        },
    }

    dashboard_numbers = {
        'generated_at': date.today().isoformat(),
        'total': len(p1_no_ato) + len(p2_no_ato),
        'p1_total': len(p1_no_ato),
        'p2_total': len(p2_no_ato),
        'p1_parket': round(sum(item['likely_parket'] for item in p1_no_ato) / len(p1_no_ato) * 100, 2),
        'p2_parket': round(sum(item['likely_parket'] for item in p2_no_ato) / len(p2_no_ato) * 100, 2),
        'p1_balance': round(sum(item['balance_risk'] for item in p1_no_ato) / len(p1_no_ato) * 100, 2),
        'p2_balance': round(sum(item['balance_risk'] for item in p2_no_ato) / len(p2_no_ato) * 100, 2),
        'p1_avg_src': round(average(item['source_count'] for item in p1_no_ato), 2),
        'p2_avg_src': round(average(item['source_count'] for item in p2_no_ato), 2),
        'p_parket': two_period['scenarios']['without_ato']['parket']['p_value'],
        'd_parket': two_period['scenarios']['without_ato']['parket']['cohens_h'],
        'p_balance': two_period['scenarios']['without_ato']['balance']['p_value'],
        'scale': round((len(p1) + len(p2)) / 100),
    }

    return two_period, three_period, dashboard_numbers


def main() -> None:
    raw_two_period_rows, two_period_audited = load_two_period_rows()
    period_zero_rows = load_period_zero_rows()
    all_public_rows = sorted(period_zero_rows + two_period_audited, key=lambda row: (row['date'], row['url']))

    write_corpus_fast(raw_two_period_rows)

    public_explorer = build_explorer_rows(all_public_rows)
    dashboard_explorer = build_explorer_rows(two_period_audited)
    write_json(DATA / 'explorer_data.json', public_explorer)
    write_json(DOCS / 'explorer_data.json', public_explorer)
    write_json(DASHBOARD / 'explorer_data.json', dashboard_explorer)

    public_graph = build_graph_rows(all_public_rows)
    dashboard_graph = build_graph_rows(two_period_audited)
    write_json(DOCS / 'graph_data.json', public_graph)
    write_json(DASHBOARD / 'graph_data.json', dashboard_graph)

    two_period_stats, three_period_stats, dashboard_numbers = build_stats(all_public_rows)
    write_json(DATA / 'statistical_tests_v3.json', two_period_stats)
    write_json(DATA / 'statistical_tests_v3_three_periods.json', three_period_stats)
    write_json(DATA / 'dashboard_numbers.json', dashboard_numbers)

    print(f'Wrote {CORPUS_FAST}')
    print(f'Wrote {DATA / "explorer_data.json"} and public/dashboard copies')
    print(f'Wrote {DOCS / "graph_data.json"} and {DASHBOARD / "graph_data.json"}')
    print(f'Wrote {DATA / "statistical_tests_v3.json"}')
    print(f'Wrote {DATA / "statistical_tests_v3_three_periods.json"}')
    print(f'Wrote {DATA / "dashboard_numbers.json"}')


if __name__ == '__main__':
    main()
