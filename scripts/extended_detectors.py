"""
Extended quality detectors for IMI-aligned analysis.
=====================================================
Three additional metrics beyond source counting:

1. fact_comment_ratio  — does the article mix facts and opinions clearly?
2. promo_risk          — signs of hidden advertising ("джинса")
3. hate_speech_risk    — signs of hate speech, stereotyping, sexism

All detectors are:
  - Algorithmic (fully reproducible, no black box)
  - Conservative (flag only clear signals, not guesses)
  - Transparent (every flagged article shows WHICH pattern triggered)
  - Imperfect by design — we disclose false-positive rates openly

These proxy metrics DO NOT replace expert review.
They give objective signals that any reader can verify by opening the article.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 1. FACT vs COMMENT RATIO
# ---------------------------------------------------------------------------

# Phrases that signal a personal opinion / evaluation (not fact)
OPINION_MARKERS = [
    r'\bна його думку\b', r'\bна її думку\b', r'\bна їхню думку\b',
    r'\bна думку\b', r'\bна погляд\b', r'\bна переконання\b',
    r'\bвважає\b', r'\bвважають\b', r'\bпереконаний\b', r'\bпереконана\b',
    r'\bза оцінкою\b', r'\bза словами\b', r'\bна думку експертів\b',
    r'\bкомментує\b', r'\bкоментує\b', r'\bоцінює\b',
    r'\bна думку аналітиків\b', r'\bза прогнозами\b',
]

# Phrases that signal a verifiable fact (document, figure, official statement)
FACT_MARKERS = [
    r'\bповідомляється\b', r'\bйдеться\b', r'\bзазначається\b',
    r'\bнаголошується\b', r'\bпідкреслюється\b', r'\bвідповідно до\b',
    r'\bзгідно з\b', r'\bза даними\b', r'\bстатистика\b', r'\bдані показують\b',
    r'\b\d+[\s\xa0]%\b', r'\bмільярд\b', r'\bмільйон\b', r'\bтисяч\b',
    r'\bдокумент\b', r'\bзакон\b', r'\bпостанова\b', r'\bнаказ\b',
    r'\bрішення\b', r'\bзвіт\b', r'\bдослідження\b',
]

_OPINION_RE = re.compile('|'.join(OPINION_MARKERS), re.IGNORECASE)
_FACT_RE = re.compile('|'.join(FACT_MARKERS), re.IGNORECASE)


def analyze_fact_comment(text: str) -> dict:
    """
    Returns:
      opinion_signals: count of opinion-marker matches
      fact_signals: count of fact-marker matches
      mixed_score: ratio — higher = more balanced fact/opinion mix
      flag: True if article is almost pure opinion with no fact anchors
    """
    opinion_count = len(_OPINION_RE.findall(text))
    fact_count = len(_FACT_RE.findall(text))
    total = opinion_count + fact_count

    # Flag: many opinions, almost no facts
    flag = opinion_count >= 3 and fact_count == 0

    mixed_score = round(fact_count / total, 2) if total > 0 else 0.0

    return {
        'opinion_signals': opinion_count,
        'fact_signals': fact_count,
        'fact_ratio': mixed_score,
        'opinion_without_facts': flag,
    }


# ---------------------------------------------------------------------------
# 2. PROMO RISK ("джинса" — hidden advertising)
# ---------------------------------------------------------------------------

PROMO_SIGNALS = [
    # Commercial superlatives
    r'\bлідер ринку\b', r'\bлідер галузі\b', r'\bнайкращ\w+\b',
    r'\bунікальн\w+\b', r'\bексклюзивн\w+\b', r'\bбезпрецедентн\w+\b',
    r'\bінновацій\w+\b', r'\bпередов\w+\b',
    # Commercial calls to action
    r'\bзамовити\b', r'\bзареєструватись\b', r'\bприєднатись\b',
    r'\bдізнатись більше\b', r'\bперейти за посиланням\b',
    r'\bофіційний сайт\b', r'\bсайт компанії\b',
    # Branded content signals
    r'\bпартнерський матеріал\b', r'\bрекламний матеріал\b',
    r'\bна правах реклами\b', r'\bспонсорський матеріал\b',
    # Patterns of one-sided praise (company name + only positive verbs)
    r'\bуспішно\b', r'\bефективно\b', r'\bзначно збільшив\b',
    r'\bрекордн\w+\b', r'\bвражаюч\w+\b',
]

_PROMO_RE = re.compile('|'.join(PROMO_SIGNALS), re.IGNORECASE)

# Commercial URL pattern in article body
COMMERCIAL_URL_RE = re.compile(r'https?://(?!ukrinform|interfax|unian|pravda|mil\.gov|president\.gov|cabinet\.gov|rada\.gov)\S+')


def analyze_promo_risk(text: str, url: str = '') -> dict:
    """
    Returns:
      promo_signals: count of promotional language matches
      has_commercial_cta: bool — explicit call to action found
      risk_level: LOW / MEDIUM / HIGH
      triggered_patterns: list of matched phrases (for transparency)
    """
    matches = _PROMO_RE.findall(text)
    signal_count = len(matches)

    # Deduplicate for display
    triggered = list(dict.fromkeys(m.lower().strip() for m in matches))[:5]

    # Explicit CTA check
    cta_patterns = ['замовити', 'зареєструватись', 'приєднатись',
                    'дізнатись більше', 'перейти за посиланням']
    has_cta = any(p in text.lower() for p in cta_patterns)

    if signal_count >= 5 or has_cta:
        risk = 'HIGH'
    elif signal_count >= 2:
        risk = 'MEDIUM'
    else:
        risk = 'LOW'

    return {
        'promo_signal_count': signal_count,
        'has_commercial_cta': has_cta,
        'promo_risk': risk,
        'promo_triggered': triggered,
    }


# ---------------------------------------------------------------------------
# 3. HATE SPEECH / STEREOTYPING / SEXISM RISK
# ---------------------------------------------------------------------------

# Hate speech markers (ethnicity, religion, social groups)
HATE_SIGNALS = [
    # Dehumanization
    r'\bтварин\w+\b(?=.{0,30}(?:люди|особи|громадяни))',
    r'\bбидло\b', r'\bзрадник\w*\b', r'\bколаборант\w*\b(?!\s+(?:засуджен|викрит))',
    # Ethnic/religious stereotyping
    r'\bвсі\s+(?:євреї|цигани|мусульмани|католики)\b',
    r'\b(?:жид|жиди)\b',
    # Calls for violence
    r'\bзнищити\b.{0,20}\b(?:їх|їхній|всіх)\b',
    r'\bліквідувати\b.{0,20}\bнаселення\b',
]

# Sexism markers
SEXISM_SIGNALS = [
    r'\bжінки не здатн\w+\b', r'\bслабка стать\b', r'\bжіноча логіка\b',
    r'\bмісце жінки\b', r'\bбабська\b', r'\bдівчачий\b(?=.{0,20}(?:страх|плач|капризи))',
    r'\bсексуальн\w+\s+(?:об\'єкт|привабливість)\b',
    # Describing women by appearance in professional contexts
    r'\b(депутатка|міністерка|генеральна|директорка|президентка).{0,50}(красив|струнк|привабл|елегантн)\w+\b',
]

_HATE_RE = re.compile('|'.join(HATE_SIGNALS), re.IGNORECASE)
_SEXISM_RE = re.compile('|'.join(SEXISM_SIGNALS), re.IGNORECASE)


def analyze_hate_speech(text: str) -> dict:
    """
    Returns:
      hate_signals: count of potential hate speech markers
      sexism_signals: count of potential sexism markers
      hate_risk: LOW / MEDIUM / HIGH
      note: always LOW unless clear pattern detected (conservative approach)
    """
    hate_matches = _HATE_RE.findall(text)
    sexism_matches = _SEXISM_RE.findall(text)

    hate_count = len(hate_matches)
    sexism_count = len(sexism_matches)

    if hate_count >= 2 or sexism_count >= 2:
        risk = 'HIGH'
    elif hate_count >= 1 or sexism_count >= 1:
        risk = 'MEDIUM'
    else:
        risk = 'LOW'

    return {
        'hate_signal_count': hate_count,
        'sexism_signal_count': sexism_count,
        'hate_speech_risk': risk,
    }


# ---------------------------------------------------------------------------
# COMBINED: run all detectors on one article
# ---------------------------------------------------------------------------

def analyze_article(text: str, url: str = '', is_official: bool = False,
                    source_count: int = 0, non_official_count: int = 0) -> dict:
    """Run all detectors and return combined result."""
    result = {}
    result.update(analyze_fact_comment(text))
    result.update(analyze_promo_risk(text, url))
    result.update(analyze_hate_speech(text))

    # IMI-aligned composite flag: article raises quality concern
    # True if ANY of the key IMI criteria show a problem
    has_quality_concern = (
        result['promo_risk'] in ('MEDIUM', 'HIGH') or
        result['hate_speech_risk'] in ('MEDIUM', 'HIGH') or
        result['opinion_without_facts'] or
        (is_official and source_count <= 1 and non_official_count == 0)
    )
    result['quality_concern'] = has_quality_concern

    return result


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    sample_parket = """
    Президент Зеленський провів нараду з членами Кабінету міністрів.
    Обговорювалися питання оборони та економіки. Зеленський наголосив на важливості
    єдності. Пресслужба Офісу Президента повідомила про результати наради.
    """

    sample_promo = """
    Компанія "Лідер Груп" — беззаперечний лідер ринку нерухомості.
    Унікальна пропозиція! Ексклюзивні апартаменти за безпрецедентними цінами.
    Зареєструйтесь на сайті компанії та дізнайтесь більше про акції.
    """

    sample_balanced = """
    За даними Міністерства фінансів, ВВП зріс на 3.5%.
    Водночас аналітики МВФ вважають, що реальний показник нижчий.
    Згідно зі звітом НБУ, інфляція склала 8.2%. Опозиція відмовилась коментувати дані.
    """

    print("=== PARKET ARTICLE ===")
    print(analyze_article(sample_parket, is_official=True, source_count=1, non_official_count=0))

    print("\n=== PROMO ARTICLE ===")
    print(analyze_article(sample_promo))

    print("\n=== BALANCED ARTICLE ===")
    print(analyze_article(sample_balanced, is_official=False, source_count=3, non_official_count=2))
