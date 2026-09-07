"""Dedicated Marketplace AI Studio background worker.

Production command:
    python -m app.worker

One worker process hosts the lightweight FBO scheduler and the durable database
job consumers. Multiple replicas are safe: FBO uses per-account leases and the
job queue uses PostgreSQL SKIP LOCKED claiming.
"""
import asyncio
import logging
import signal

from . import fbo_jobs  # noqa: F401 - registers durable job handlers
from .fbo_monitor import monitor_forever
from .job_queue import job_worker_forever

logging.basicConfig(level=logging.INFO)
logger=logging.getLogger(__name__)

async def _run()->None:
    stop_event=asyncio.Event(); loop=asyncio.get_running_loop()
    def request_stop():
        logger.info('Worker shutdown requested'); stop_event.set()
    for sig in (signal.SIGINT,signal.SIGTERM):
        try: loop.add_signal_handler(sig,request_stop)
        except NotImplementedError: pass
    logger.info('Marketplace AI Studio worker started')
    tasks=[asyncio.create_task(monitor_forever(stop_event),name='fbo-scheduler'),asyncio.create_task(job_worker_forever(stop_event),name='job-queue')]
    try:
        await asyncio.gather(*tasks)
    finally:
        stop_event.set()
        await asyncio.gather(*tasks,return_exceptions=True)
    logger.info('Marketplace AI Studio worker stopped')

def main()->None:
    try: asyncio.run(_run())
    except KeyboardInterrupt: pass

if __name__=='__main__': main()
