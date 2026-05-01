from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from canonical_metrics import official_categories_for_slug, slug_from_url

DOCS_EXPLORER = BASE / "docs" / "explorer_data.json"
REPORT_MD = BASE / "CLASSIFICATION_AUDIT_79505.md"
REPORT_JSON = BASE / "data" / "classification_audit_79505.json"

FOREIGN_MARKERS = (
    "rf",
    "rosii",
    "rosia",
    "рос",
    "dnr",
    "lnr",
    "g7",
    "obse",
    "ssha",
    "nimecc",
    "britan",
    "franc",
    "polsh",
    "cheh",
    "marokko",
)


def pct(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return round(numerator / denominator * 100, 2)


def load_rows() -> list[dict[str, object]]:
    return json.loads(DOCS_EXPLORER.read_text(encoding="utf-8"))


def foreignish(row: dict[str, object]) -> bool:
    text = f"{row['t']} {row['u']}".lower()
    return any(marker in text for marker in FOREIGN_MARKERS)


def minister_foreignish(row: dict[str, object]) -> bool:
    text = f"{row['t']} {row['u']}".lower()
    return foreignish(row) and ("ministr" in text or "міністр" in text)


def keyword_buckets(rows: list[dict[str, object]]) -> dict[str, int]:
    title_rows = [row for row in rows if row["pk"] and row["sc"] == 0]
    return {
        "zvedennya": sum("зведення" in row["t"].lower() for row in title_rows),
        "za_dobu": sum("за добу" in row["t"].lower() for row in title_rows),
        "ova_or_kmva": sum(
            any(marker in row["t"].lower() for marker in ("ова", "кмва", "кмда", "міськрада"))
            for row in title_rows
        ),
        "zsu_or_genshtab_or_sbu": sum(
            any(marker in row["t"].lower() for marker in ("зсу", "генштаб", "сбу", "сили оборони"))
            for row in title_rows
        ),
        "president_or_rada": sum(
            any(marker in row["t"].lower() for marker in ("президент", "зеленський", "рада"))
            for row in title_rows
        ),
    }


def top_category_counts(rows: list[dict[str, object]], key: str | None = None) -> Counter:
    counts: Counter = Counter()
    for row in rows:
        if key and not row[key]:
            continue
        categories = official_categories_for_slug(slug_from_url(row["u"]))
        for category in categories:
            counts[category] += 1
    return counts


def sample_rows(rows: list[dict[str, object]], predicate, limit: int = 8) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for row in rows:
        if predicate(row):
            output.append(
                {
                    "date": row["d"],
                    "period": row["p"],
                    "rubric": row["r"],
                    "title": row["t"],
                    "url": row["u"],
                    "sc": row["sc"],
                    "oc": row["oc"],
                    "noc": row["noc"],
                }
            )
            if len(output) >= limit:
                break
    return output


def main() -> None:
    rows = load_rows()

    by_period = {}
    for period in ("p0", "p1", "p2"):
        items = [row for row in rows if row["p"] == period]
        by_period[period] = {
            "n": len(items),
            "official": sum(row["of"] for row in items),
            "parket": sum(row["pk"] for row in items),
            "balance": sum(row["br"] for row in items),
            "parket_sc_distribution": dict(Counter(row["sc"] for row in items if row["pk"]).most_common()),
            "balance_sc_distribution": dict(Counter(row["sc"] for row in items if row["br"]).most_common()),
        }

    rubric_totals = Counter(row["r"] for row in rows)
    rubric_parket = Counter(row["r"] for row in rows if row["pk"])
    rubric_balance = Counter(row["r"] for row in rows if row["br"])

    suspicious_counts = {
        "pk_sc_0": sum(row["pk"] and row["sc"] == 0 for row in rows),
        "pk_sc_1": sum(row["pk"] and row["sc"] == 1 for row in rows),
        "pk_ato": sum(row["pk"] and row["r"] == "ato" for row in rows),
        "pk_regions_sc_0": sum(row["pk"] and row["r"] == "regions" and row["sc"] == 0 for row in rows),
        "pk_foreignish": sum(row["pk"] and foreignish(row) for row in rows),
        "pk_foreignish_sc_0": sum(row["pk"] and foreignish(row) and row["sc"] == 0 for row in rows),
        "pk_minister_foreignish": sum(row["pk"] and minister_foreignish(row) for row in rows),
        "official_false_oc_gt_0": sum((not row["of"]) and row["oc"] > 0 for row in rows),
        "official_true_oc_0": sum(row["of"] and row["oc"] == 0 for row in rows),
        "official_true_sc_0": sum(row["of"] and row["sc"] == 0 for row in rows),
    }

    consistency = {
        "pk_without_of": sum(row["pk"] and not row["of"] for row in rows),
        "br_without_of": sum(row["br"] and not row["of"] for row in rows),
        "pk_with_noc_gt_0": sum(row["pk"] and row["noc"] > 0 for row in rows),
        "pk_with_sc_gt_1": sum(row["pk"] and row["sc"] > 1 for row in rows),
        "br_with_noc_gt_0": sum(row["br"] and row["noc"] > 0 for row in rows),
    }

    payload = {
        "total_rows": len(rows),
        "total_official": sum(row["of"] for row in rows),
        "total_parket": sum(row["pk"] for row in rows),
        "total_balance": sum(row["br"] for row in rows),
        "consistency": consistency,
        "by_period": by_period,
        "rubric_parket": {
            rubric: {
                "parket": rubric_parket[rubric],
                "total": rubric_totals[rubric],
                "parket_pct": pct(rubric_parket[rubric], rubric_totals[rubric]),
            }
            for rubric, _ in rubric_parket.most_common()
        },
        "rubric_balance": {
            rubric: {
                "balance": rubric_balance[rubric],
                "total": rubric_totals[rubric],
                "balance_pct": pct(rubric_balance[rubric], rubric_totals[rubric]),
            }
            for rubric, _ in rubric_balance.most_common()
        },
        "derived_slug_categories": {
            "official_all": dict(top_category_counts(rows).most_common()),
            "parket_only": dict(top_category_counts(rows, "pk").most_common()),
            "balance_only": dict(top_category_counts(rows, "br").most_common()),
        },
        "suspicious_counts": suspicious_counts,
        "pk_sc0_keyword_buckets": keyword_buckets(rows),
        "samples": {
            "pk_sc0_foreignish": sample_rows(rows, lambda row: row["pk"] and row["sc"] == 0 and foreignish(row)),
            "pk_ato": sample_rows(rows, lambda row: row["pk"] and row["r"] == "ato"),
            "pk_regions_sc0": sample_rows(rows, lambda row: row["pk"] and row["r"] == "regions" and row["sc"] == 0),
            "official_false_oc_gt0": sample_rows(rows, lambda row: (not row["of"]) and row["oc"] > 0),
            "pk_minister_foreignish": sample_rows(rows, lambda row: row["pk"] and minister_foreignish(row)),
        },
    }

    REPORT_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Audit of 79,505 Classified Articles",
        "",
        "Generated from `docs/explorer_data.json`.",
        "",
        "## Totals",
        "",
        f"- Audited articles: `{payload['total_rows']:,}`",
        f"- `official=True`: `{payload['total_official']:,}` (`{pct(payload['total_official'], payload['total_rows'])}%`)",
        f"- `parket=True`: `{payload['total_parket']:,}` (`{pct(payload['total_parket'], payload['total_rows'])}%`)",
        f"- `balance=True`: `{payload['total_balance']:,}` (`{pct(payload['total_balance'], payload['total_rows'])}%`)",
        "",
        "## Internal Consistency",
        "",
    ]
    for key, value in consistency.items():
        lines.append(f"- `{key}`: `{value}`")

    lines.extend(
        [
            "",
            "## Period Summary",
            "",
            "| Period | N | Official | Parket | Balance |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for period in ("p0", "p1", "p2"):
        item = by_period[period]
        lines.append(
            f"| `{period}` | `{item['n']:,}` | `{item['official']:,}` | `{item['parket']:,}` | `{item['balance']:,}` |"
        )

    lines.extend(
        [
            "",
            "## Main Risk Buckets",
            "",
            f"- `parket` with `source_count=0`: `{suspicious_counts['pk_sc_0']:,}` (`{pct(suspicious_counts['pk_sc_0'], payload['total_parket'])}%` of all `parket`)",
            f"- `parket` with `source_count=1`: `{suspicious_counts['pk_sc_1']:,}` (`{pct(suspicious_counts['pk_sc_1'], payload['total_parket'])}%` of all `parket`)",
            f"- `parket` inside `ATO`: `{suspicious_counts['pk_ato']:,}`",
            f"- `parket` in `regions` with `source_count=0`: `{suspicious_counts['pk_regions_sc_0']:,}`",
            f"- `parket` in foreign-context titles/URLs: `{suspicious_counts['pk_foreignish']:,}`",
            f"- `parket` in foreign-context titles/URLs with `source_count=0`: `{suspicious_counts['pk_foreignish_sc_0']:,}`",
            f"- `parket` in foreign-context minister titles/URLs: `{suspicious_counts['pk_minister_foreignish']:,}`",
            f"- `official=False` but `official_source_count>0`: `{suspicious_counts['official_false_oc_gt_0']:,}`",
            f"- `official=True` but `official_source_count=0`: `{suspicious_counts['official_true_oc_0']:,}`",
            f"- `official=True` and `source_count=0`: `{suspicious_counts['official_true_sc_0']:,}`",
            "",
            "## `parket` by Rubric",
            "",
            "| Rubric | Parket | Total | Parket % |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    for rubric, item in payload["rubric_parket"].items():
        lines.append(f"| `{rubric}` | `{item['parket']:,}` | `{item['total']:,}` | `{item['parket_pct']}%` |")

    lines.extend(
        [
            "",
            "## Derived Official Categories from URL Slugs",
            "",
            "| Category | Official | Parket | Balance |",
            "| --- | ---: | ---: | ---: |",
        ]
    )
    all_categories = payload["derived_slug_categories"]["official_all"]
    parket_categories = payload["derived_slug_categories"]["parket_only"]
    balance_categories = payload["derived_slug_categories"]["balance_only"]
    for category, total in sorted(all_categories.items(), key=lambda item: item[1], reverse=True):
        lines.append(
            f"| {category} | `{total:,}` | `{parket_categories.get(category, 0):,}` | `{balance_categories.get(category, 0):,}` |"
        )

    lines.extend(
        [
            "",
            "## `parket` with `source_count=0`: simple title heuristics",
            "",
        ]
    )
    for key, value in payload["pk_sc0_keyword_buckets"].items():
        lines.append(f"- `{key}`: `{value:,}`")

    for sample_name, sample_items in payload["samples"].items():
        lines.extend(
            [
                "",
                f"## Sample: {sample_name}",
                "",
                "| Date | Period | Rubric | sc | oc | noc | Title |",
                "| --- | --- | --- | ---: | ---: | ---: | --- |",
            ]
        )
        for row in sample_items:
            title = str(row["title"]).replace("|", "/")
            lines.append(
                f"| `{row['date']}` | `{row['period']}` | `{row['rubric']}` | `{row['sc']}` | `{row['oc']}` | `{row['noc']}` | [{title}]({row['url']}) |"
            )

    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Wrote {REPORT_MD}")
    print(f"Wrote {REPORT_JSON}")


if __name__ == "__main__":
    main()
