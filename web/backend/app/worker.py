"""Dedicated TROVENDI background worker.

Production command:
    python -m app.worker

One worker process hosts lightweight schedulers and durable database job
consumers. Multiple replicas are safe through leases and PostgreSQL SKIP LOCKED.
"""
import asyncio
import logging
import signal

from . import fbo_jobs  # noqa: F401 - registers durable job handlers
from . import marketplace_sync  # noqa: F401 - registers marketplace sync handlers
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
    logger.info('TROVENDI worker started')
    tasks=[asyncio.create_task(monitor_forever(stop_event),name='fbo-scheduler'),asyncio.create_task(job_worker_forever(stop_event),name='job-queue')]
    try:
        await asyncio.gather(*tasks)
    finally:
        stop_event.set()
        await asyncio.gather(*tasks,return_exceptions=True)
    logger.info('TROVENDI worker stopped')

def main()->None:
    try: asyncio.run(_run())
    except KeyboardInterrupt: pass

if __name__=='__main__': main()
