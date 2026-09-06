import json


def _raw(product):
    raw = product.get('raw_json') if isinstance(product, dict) else None
    if not raw:
        return {}
    try:
        return json.loads(raw) if isinstance(raw, str) else dict(raw)
    except Exception:
        return {}


def score_product(product):
    p = dict(product)
    raw = _raw(p)
    name = (p.get('name') or '').strip()
    desc = (raw.get('description') or raw.get('descriptionShort') or '').strip()
    vendor = (p.get('sku') or raw.get('vendorCode') or '').strip()
    photos = raw.get('photos') or []
    chars = raw.get('characteristics') or []

    score = 100
    issues = []
    if len(name) < 25:
        score -= 18; issues.append('короткий заголовок')
    elif len(name) > 140:
        score -= 10; issues.append('слишком длинный заголовок')
    if not desc:
        score -= 24; issues.append('нет описания')
    elif len(desc) < 300:
        score -= 12; issues.append('короткое описание')
    if not photos:
        score -= 18; issues.append('нет фото в API-данных')
    elif len(photos) < 4:
        score -= 8; issues.append('мало фото')
    if not chars:
        score -= 14; issues.append('не заполнены характеристики')
    elif len(chars) < 5:
        score -= 6; issues.append('мало характеристик')
    if not vendor:
        score -= 8; issues.append('нет артикула продавца')
    score = max(0, min(100, score))
    grade = 'A' if score >= 85 else 'B' if score >= 70 else 'C' if score >= 50 else 'D'
    return {
        'marketplace': p.get('marketplace',''), 'nm': str(p.get('external_id') or ''), 'sku': vendor,
        'name': name, 'score': score, 'grade': grade, 'issues': issues,
        'description': desc, 'raw': raw,
    }


def batch_score(products):
    rows = [score_product(dict(p)) for p in products]
    return sorted(rows, key=lambda x: (x['score'], x['name']))


def optimization_payload(row):
    return {
        'marketplace': row.get('marketplace'),
        'nmID': row.get('nm'),
        'sku': row.get('sku'),
        'current_title': row.get('name'),
        'current_description': row.get('description'),
        'quality_score': row.get('score'),
        'detected_issues': row.get('issues'),
        'characteristics': row.get('raw',{}).get('characteristics') or [],
    }
