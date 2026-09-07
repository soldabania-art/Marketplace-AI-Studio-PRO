"""Dedicated Marketplace AI Studio background worker.

Run separately from the HTTP API in production:
    python -m app.worker

The current worker hosts FBO monitoring. Additional queues/jobs will move behind
this process instead of being executed in request handlers.
"""

import asyncio
import logging
import signal

from .fbo_monitor import monitor_forever

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _run() -> None:
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_stop() -> None:
        logger.info('Worker shutdown requested')
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, request_stop)
        except NotImplementedError:
            # Windows event loops do not always support add_signal_handler.
            pass

    logger.info('Marketplace AI Studio worker started')
    await monitor_forever(stop_event)
    logger.info('Marketplace AI Studio worker stopped')


def main() -> None:
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
