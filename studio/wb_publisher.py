import json
from .core import products
from .autopilot import save_card_version, queue_action


class WBPublisher:
    """Prepare and execute WB card writes using verified Content API methods.

    The update endpoint overwrites the product card. We therefore start from the last
    synchronized raw WB card and only replace fields AI is allowed to own: title and
    description. Characteristics, dimensions and sizes are preserved verbatim.
    Media is handled separately because WB exposes separate media endpoints.
    """

    UPDATE_FIELDS = ('nmID', 'vendorCode', 'brand', 'title', 'description', 'dimensions', 'characteristics', 'sizes', 'kizMarked')

    def __init__(self, wb):
        self.wb = wb

    @staticmethod
    def _local_product(nm_id):
        nm_id = str(nm_id)
        for row in products():
            if str(row['marketplace']) == 'WB' and str(row['external_id']) == nm_id:
                raw = json.loads(row['raw_json'] or '{}')
                return raw.get('raw') or raw
        return None

    @staticmethod
    def _title(ai_card):
        titles = ai_card.get('title_variants') or []
        if isinstance(titles, list) and titles:
            return str(titles[0]).strip()
        return str(ai_card.get('title') or '').strip()

    def prepare_update(self, nm_id, ai_card):
        current = self._local_product(nm_id)
        if not current:
            raise RuntimeError('Не найдена синхронизированная исходная карточка WB. Сначала обновите каталог.')
        payload = {k: current.get(k) for k in self.UPDATE_FIELDS if k in current}
        payload['nmID'] = int(nm_id)
        title = self._title(ai_card)
        description = str(ai_card.get('description') or '').strip()
        if title:
            payload['title'] = title
        if description:
            payload['description'] = description
        missing = [k for k in ('vendorCode', 'dimensions', 'characteristics', 'sizes') if k not in payload]
        if missing:
            raise RuntimeError('Исходная карточка неполная для безопасной перезаписи: ' + ', '.join(missing))
        old_media = current.get('mediaFiles') or current.get('photos') or []
        return {'payload': payload, 'current': current, 'old_media': old_media}

    def publish(self, nm_id, ai_card, image_paths=None):
        prepared = self.prepare_update(nm_id, ai_card)
        current = prepared['current']
        before_ver = save_card_version('WB', nm_id, current, prepared['old_media'], 'before_publish')
        result = {'before_version': before_ver, 'text_update': None, 'media': []}
        result['text_update'] = self.wb.update_card(prepared['payload'])
        for idx, path in enumerate(image_paths or [], start=1):
            result['media'].append(self.wb.upload_media_file(nm_id, path, idx))
        after_ver = save_card_version('WB', nm_id, ai_card, image_paths or [], 'published')
        result['after_version'] = after_ver
        return result

    def queue_publish(self, nm_id, ai_card, image_paths=None, reason='AI-карточка готова к публикации'):
        prepared = self.prepare_update(nm_id, ai_card)
        return queue_action('WB', nm_id, 'publish_card', {
            'card': ai_card,
            'images': [str(x) for x in (image_paths or [])],
            'prepared_payload': prepared['payload'],
        }, reason, 'high')
