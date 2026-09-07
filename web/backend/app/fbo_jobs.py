import logging

from .fbo_monitor import process_group_job
from .job_queue import register_handler

logger = logging.getLogger(__name__)


@register_handler('fbo.poll')
async def handle_fbo_poll(payload: dict) -> None:
    scope = str(payload.get('scope') or '')
    identifier = str(payload.get('id') or '')
    if scope not in {'store', 'legacy-user'} or not identifier:
        raise ValueError('Invalid FBO poll job payload')
    stats = await process_group_job((scope, identifier))
    logger.info('FBO poll job finished scope=%s id=%s stats=%s', scope, identifier, stats)
