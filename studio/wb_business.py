from datetime import datetime, timedelta, timezone


class WBBusiness:
    """Higher-level WB analytics built on top of studio.connectors.WB.

    Uses the current Finance API sales-report endpoint and Promotion API v3 statistics.
    The methods deliberately do not change bids or campaign state.
    """

    FINANCE = 'https://finance-api.wildberries.ru'

    def __init__(self, wb):
        self.wb = wb

    @staticmethod
    def _date(days):
        return (datetime.now(timezone.utc) - timedelta(days=max(int(days), 0))).date().isoformat()

    @staticmethod
    def _today():
        return datetime.now(timezone.utc).date().isoformat()

    @staticmethod
    def _money(value):
        if value in (None, ''):
            return 0.0
        try:
            return float(str(value).replace(' ', '').replace(',', '.'))
        except Exception:
            return 0.0

    @staticmethod
    def _first(row, *names):
        for name in names:
            if name in row and row.get(name) not in (None, ''):
                return row.get(name)
        return None

    def finance_rows(self, days=30, limit=100000):
        """Get one page of the current WB Finance API detailed sales report.

        Finance API is rate-limited to one request per minute per seller, so the desktop
        app intentionally requests a large page and reports whether another page may exist.
        """
        payload = {
            'dateFrom': self._date(days),
            'dateTo': self._today(),
            'limit': min(max(int(limit), 1), 100000),
            'rrdId': 0,
            'period': 'weekly',
            'fields': None,
        }
        data = self.wb._request(
            'POST', self.FINANCE + '/api/finance/v1/sales-reports/detailed',
            json=payload,
        )
        if isinstance(data, list):
            rows = data
        elif isinstance(data, dict):
            rows = data.get('data') or data.get('rows') or data.get('items') or []
            if isinstance(rows, dict):
                rows = rows.get('rows') or rows.get('items') or []
        else:
            rows = []
        return rows if isinstance(rows, list) else []

    def finance_summary(self, rows):
        summary = {
            'rows': len(rows),
            'gross': 0.0,
            'payout': 0.0,
            'logistics': 0.0,
            'storage': 0.0,
            'acceptance': 0.0,
            'penalties': 0.0,
            'other_adjustments': 0.0,
            'commission_estimate': 0.0,
            'by_nm': {},
        }
        for row in rows:
            if not isinstance(row, dict):
                continue
            gross = self._money(self._first(
                row, 'retailPriceWithdiscRub', 'retailPriceWithDiscRub',
                'retailAmount', 'retailPrice', 'priceWithDisc'
            ))
            payout = self._money(self._first(
                row, 'ppvzForPay', 'forPay', 'supplierPayout', 'sellerPayout'
            ))
            logistics = self._money(self._first(
                row, 'deliveryRub', 'deliveryAmount', 'logisticsAmount', 'deliveryCost'
            ))
            storage = self._money(self._first(
                row, 'storageFee', 'storageRub', 'storageAmount'
            ))
            acceptance = self._money(self._first(
                row, 'acceptance', 'acceptanceRub', 'acceptanceAmount'
            ))
            penalty = self._money(self._first(
                row, 'penalty', 'penaltyRub', 'penalties'
            ))
            other = self._money(self._first(
                row, 'additionalPayment', 'rebillLogisticCost', 'otherAmount'
            ))

            summary['gross'] += gross
            summary['payout'] += payout
            summary['logistics'] += abs(logistics)
            summary['storage'] += abs(storage)
            summary['acceptance'] += abs(acceptance)
            summary['penalties'] += abs(penalty)
            summary['other_adjustments'] += other

            nm = self._first(row, 'nmId', 'nmID', 'nm_id')
            if nm not in (None, '', 0, '0'):
                key = str(nm)
                bucket = summary['by_nm'].setdefault(key, {
                    'gross': 0.0, 'payout': 0.0, 'logistics': 0.0,
                    'storage': 0.0, 'acceptance': 0.0, 'penalties': 0.0,
                    'rows': 0,
                })
                bucket['gross'] += gross
                bucket['payout'] += payout
                bucket['logistics'] += abs(logistics)
                bucket['storage'] += abs(storage)
                bucket['acceptance'] += abs(acceptance)
                bucket['penalties'] += abs(penalty)
                bucket['rows'] += 1

        # WB's detailed report can contain many operation types. This value is therefore
        # explicitly an estimate rather than a claim about a single commission field.
        known_direct = summary['logistics'] + summary['storage'] + summary['acceptance'] + summary['penalties']
        summary['commission_estimate'] = max(0.0, summary['gross'] - summary['payout'] - known_direct)
        return summary

    @staticmethod
    def campaign_ids(groups):
        ids = []

        def walk(value):
            if isinstance(value, dict):
                for k, v in value.items():
                    lk = str(k).lower()
                    if lk in ('advertid', 'advert_id'):
                        try:
                            ids.append(int(v))
                        except Exception:
                            pass
                    elif lk == 'id' and isinstance(v, (int, str)):
                        # promotion/count often nests campaign ids in lists; only accept
                        # positive numeric ids to avoid status/type values.
                        try:
                            n = int(v)
                            if n > 1000:
                                ids.append(n)
                        except Exception:
                            pass
                    else:
                        walk(v)
            elif isinstance(value, list):
                for item in value:
                    walk(item)

        walk(groups)
        # Preserve order, remove duplicates.
        return list(dict.fromkeys(ids))

    def ad_stats(self, groups=None, days=30):
        groups = groups if groups is not None else self.wb.campaign_groups()
        ids = self.campaign_ids(groups)[:50]
        if not ids:
            return {'campaigns': 0, 'spend': 0.0, 'sales': 0.0, 'orders': 0, 'views': 0, 'clicks': 0, 'drr': 0.0, 'rows': []}
        data = self.wb._request(
            'GET', self.wb.ADVERT + '/adv/v3/fullstats',
            params={
                'ids': ','.join(str(x) for x in ids),
                'beginDate': self._date(min(int(days), 31)),
                'endDate': self._today(),
            },
        )
        rows = data if isinstance(data, list) else (data.get('data') or data.get('items') or []) if isinstance(data, dict) else []
        spend = sales = 0.0
        orders = views = clicks = 0
        for r in rows if isinstance(rows, list) else []:
            if not isinstance(r, dict):
                continue
            spend += self._money(r.get('sum'))
            sales += self._money(r.get('sum_price'))
            try: orders += int(r.get('orders') or 0)
            except Exception: pass
            try: views += int(r.get('views') or 0)
            except Exception: pass
            try: clicks += int(r.get('clicks') or 0)
            except Exception: pass
        return {
            'campaigns': len(ids),
            'spend': spend,
            'sales': sales,
            'orders': orders,
            'views': views,
            'clicks': clicks,
            'drr': (spend / sales * 100.0) if sales else 0.0,
            'rows': rows if isinstance(rows, list) else [],
        }
