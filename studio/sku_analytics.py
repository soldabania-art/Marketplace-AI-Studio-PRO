def _money(value):
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def sales_by_nm(rows):
    out = {}
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        nm = row.get('nmId') or row.get('nmID') or row.get('nm_id')
        if nm in (None, '', 0, '0'):
            continue
        key = str(nm)
        bucket = out.setdefault(key, {'units':0,'returns':0,'gross':0.0,'payout':0.0})
        amount = _money(row.get('finishedPrice') or row.get('priceWithDisc'))
        payout = _money(row.get('forPay'))
        sale_id = str(row.get('saleID') or row.get('saleId') or '')
        is_return = sale_id.upper().startswith('R') or amount < 0 or payout < 0
        if is_return:
            bucket['returns'] += 1
        else:
            bucket['units'] += 1
        bucket['gross'] += amount
        bucket['payout'] += payout
    return out


def sku_profitability(products, finance_by_nm, sales_by_nm_data, ad_spend, cogs):
    result = []
    wb_products = {str(p.get('external_id')): p for p in products if str(p.get('marketplace')) == 'WB'}
    keys = set(wb_products) | set(finance_by_nm or {}) | set(sales_by_nm_data or {})
    total_gross = sum(max(_money((sales_by_nm_data.get(k) or {}).get('gross')), 0) for k in keys)
    for nm in keys:
        p = wb_products.get(nm, {})
        f = (finance_by_nm or {}).get(nm, {})
        s = (sales_by_nm_data or {}).get(nm, {})
        units = int(s.get('units') or 0)
        returns = int(s.get('returns') or 0)
        gross = _money(s.get('gross') or f.get('gross'))
        payout = _money(f.get('payout'))
        cogs_unit = _money((cogs or {}).get(nm))
        cogs_total = cogs_unit * units
        ad_share = (_money(ad_spend) * max(gross, 0) / total_gross) if total_gross > 0 else 0.0
        profit = payout - cogs_total - ad_share
        margin = profit / gross * 100.0 if gross else 0.0
        stock = _money(p.get('stock'))
        result.append({
            'nm': nm,
            'name': p.get('name',''),
            'units': units,
            'returns': returns,
            'gross': gross,
            'payout': payout,
            'cogs_unit': cogs_unit,
            'cogs_total': cogs_total,
            'ad_share': ad_share,
            'profit': profit,
            'margin': margin,
            'stock': stock,
        })
    result.sort(key=lambda x: x['profit'])
    return result
