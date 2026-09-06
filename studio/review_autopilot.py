import json
from .autopilot import queue_action, set_action_status


def _first(obj, *names):
    for n in names:
        if isinstance(obj, dict) and obj.get(n) not in (None, ''):
            return obj.get(n)
    return None


class ReviewAutopilot:
    def __init__(self, wb, ai):
        self.wb = wb
        self.ai = ai

    @staticmethod
    def normalize(review):
        text = _first(review, 'text', 'pros', 'cons', 'userText') or ''
        if not text and isinstance(review, dict):
            parts = [str(review.get(k) or '').strip() for k in ('text','pros','cons')]
            text = ' | '.join(x for x in parts if x)
        rating = _first(review, 'productValuation', 'valuation', 'rating', 'stars') or 0
        try: rating = int(rating)
        except Exception: rating = 0
        return {
            'id': str(_first(review, 'id', 'feedbackId', 'feedback_id') or ''),
            'nm_id': str(_first(review, 'nmId', 'nmID', 'nm_id') or ''),
            'rating': rating,
            'text': str(text or '').strip(),
            'raw': review,
        }

    def _raw_text(self, prompt, timeout=90):
        if hasattr(self.ai, 'raw_text'):
            return self.ai.raw_text(prompt, timeout)
        if hasattr(self.ai, '_call'):
            return self.ai._call(prompt, timeout)
        raise RuntimeError('AI-провайдер не поддерживает классификацию отзывов')

    def classify(self, review):
        r = self.normalize(review)
        prompt = f'''Ты модератор отзывов маркетплейса. Верни только JSON: {{"sentiment":"positive|neutral|negative","risk":"low|medium|high","needs_human":true|false,"reason":"кратко"}}.
Оценка: {r['rating']}/5. Текст: {r['text']}. Высокий риск ставь для угроз, юридических претензий, безопасности товара, здоровья, возвратов денег, обвинений в подделке или если контекст неоднозначен.'''
        text = self._raw_text(prompt, 90)
        if text.startswith('```'):
            text = text.strip('`')
            if text.lower().startswith('json'): text = text[4:].strip()
        try:
            data = json.loads(text)
        except Exception:
            data = {'sentiment':'neutral','risk':'medium','needs_human':True,'reason':'AI не вернул валидный JSON'}
        return {**r, **data}

    def prepare(self, reviews, auto_answer_min_rating=4):
        out = []
        for raw in reviews:
            item = self.classify(raw)
            reply = self.ai.review_reply(item['text'], item['rating'])
            item['reply'] = reply
            safe_auto = (
                item['rating'] >= int(auto_answer_min_rating) and
                str(item.get('risk','medium')).lower() == 'low' and
                not bool(item.get('needs_human')) and
                bool(item.get('id'))
            )
            item['safe_auto'] = safe_auto
            out.append(item)
        return out

    def queue(self, prepared):
        ids = []
        for p in prepared:
            action_type = 'review_reply'
            risk = 'low' if p.get('safe_auto') else ('high' if p.get('risk') == 'high' else 'medium')
            reason = f"Отзыв {p.get('rating',0)}/5; {p.get('sentiment','')}; {p.get('reason','')}"
            ids.append(queue_action('WB', p.get('id'), action_type, p, reason, risk))
        return ids

    def execute(self, payload):
        fid = str(payload.get('id') or '')
        reply = str(payload.get('reply') or '').strip()
        if not fid or not reply:
            raise RuntimeError('Не хватает ID отзыва или текста ответа')
        return {'feedback_id': fid, 'sent': bool(self.wb.answer_review(fid, reply)), 'reply': reply}
