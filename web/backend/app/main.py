import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .account_router import router as account_router
from .admin_router import router as admin_router
from .config import get_settings
from .db import Base, engine
from .fbo_monitor import monitor_forever
from .legal_router import router as legal_router
from .marketplace_connections import router as marketplace_router
from .push_router import router as push_router
from .router import api_router
from .seller_data_router import router as seller_data_router
from .smart_fbo_router import router as smart_fbo_router
from .store_router import router as store_router
from .sync_router import router as sync_router

settings=get_settings()

@asynccontextmanager
async def lifespan(app:FastAPI):
    if not settings.is_production: Base.metadata.create_all(bind=engine)
    stop_event=None; monitor_task=None
    if settings.run_fbo_monitor_in_api:
        stop_event=asyncio.Event(); monitor_task=asyncio.create_task(monitor_forever(stop_event)); app.state.fbo_stop_event=stop_event; app.state.fbo_monitor_task=monitor_task
    try: yield
    finally:
        if stop_event is not None and monitor_task is not None: stop_event.set(); await monitor_task

app=FastAPI(title=settings.app_name,version='0.14.0',description='Backend for Marketplace AI Studio Cloud',lifespan=lifespan)
allowed_origins={'http://localhost:3000','https://marketplace-ai-studio-pro.vercel.app',settings.frontend_url.rstrip('/')}
app.add_middleware(CORSMiddleware,allow_origins=sorted(x for x in allowed_origins if x),allow_credentials=True,allow_methods=['GET','POST','PATCH','DELETE'],allow_headers=['*'])

@app.get('/health',tags=['system'])
def health(): return {'status':'ok','service':'marketplace-ai-studio-api','version':'0.14.0','environment':settings.environment,'embedded_fbo_monitor':settings.run_fbo_monitor_in_api}

@app.get('/ready',tags=['system'])
def ready():
    try:
        with engine.connect() as connection: connection.execute(text('SELECT 1'))
    except Exception as exc: raise HTTPException(status_code=503,detail='Database is not ready') from exc
    return {'status':'ready','database':'ok','version':'0.14.0'}

app.include_router(account_router,prefix='/api/v1',tags=['account'])
app.include_router(admin_router,prefix='/api/v1',tags=['admin'])
app.include_router(legal_router,prefix='/api/v1',tags=['legal'])
app.include_router(push_router,prefix='/api/v1',tags=['push'])
app.include_router(marketplace_router,prefix='/api/v1',tags=['integrations'])
app.include_router(store_router,prefix='/api/v1',tags=['stores'])
app.include_router(seller_data_router,prefix='/api/v1')
app.include_router(smart_fbo_router,prefix='/api/v1')
app.include_router(sync_router,prefix='/api/v1')
app.include_router(api_router,prefix='/api/v1')
