import asyncio
from contextlib import asynccontextmanager
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .account_router import router as account_router
from .agent_router import admin_router as agent_admin_router, router as agent_router
from .admin_router import router as admin_router
from .beginner_router import router as beginner_router
from .card_factory_router import router as card_factory_router
from .config import get_settings
from .db import Base, engine
from .director_router import router as director_router
from .data_health_router import router as data_health_router
from .fbo_monitor import monitor_forever
from .legal_router import router as legal_router
from .marketplace_connections import router as marketplace_router
from .onboarding_router import router as onboarding_router
from .push_router import router as push_router
from .profit_center_router import router as profit_center_router
from .reviews_router import router as reviews_router
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

app=FastAPI(
    title=settings.app_name,
    version='0.31.0',
    description='TROVENDI backend',
    lifespan=lifespan,
    docs_url=(None if settings.is_production else '/docs'),
    redoc_url=(None if settings.is_production else '/redoc'),
    openapi_url=(None if settings.is_production else '/openapi.json'),
)
allowed_origins={'http://localhost:3000','https://trovendi.ru','https://www.trovendi.ru','https://marketplace-ai-studio-pro.vercel.app',settings.frontend_url.rstrip('/')}
app.add_middleware(CORSMiddleware,allow_origins=sorted(x for x in allowed_origins if x),allow_credentials=True,allow_methods=['GET','POST','PATCH','DELETE'],allow_headers=['Authorization','Content-Type'])


@app.middleware('http')
async def security_boundary(request: Request, call_next):
    request_id = str(uuid.uuid4())
    content_length = request.headers.get('content-length')
    if content_length:
        try:
            if int(content_length) > settings.max_request_body_bytes:
                return JSONResponse({'detail':'Request body is too large'},status_code=413,headers={'X-Request-ID':request_id})
        except ValueError:
            return JSONResponse({'detail':'Invalid Content-Length'},status_code=400,headers={'X-Request-ID':request_id})
    response = await call_next(request)
    response.headers['X-Request-ID'] = request_id
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
    response.headers['Cross-Origin-Opener-Policy'] = 'same-origin'
    if request.url.path.startswith('/api/'):
        response.headers['Cache-Control'] = 'no-store, max-age=0'
        response.headers['Pragma'] = 'no-cache'
    if settings.is_production:
        response.headers['Strict-Transport-Security'] = 'max-age=63072000; includeSubDomains; preload'
    return response

@app.get('/health',tags=['system'])
def health(): return {'status':'ok','service':'trovendi-api','version':'0.31.0','environment':settings.environment,'embedded_fbo_monitor':settings.run_fbo_monitor_in_api}

@app.get('/ready',tags=['system'])
def ready():
    try:
        with engine.connect() as connection: connection.execute(text('SELECT 1'))
    except Exception as exc: raise HTTPException(status_code=503,detail='Database is not ready') from exc
    return {'status':'ready','database':'ok','version':'0.31.0'}

app.include_router(account_router,prefix='/api/v1',tags=['account'])
app.include_router(agent_router,prefix='/api/v1')
app.include_router(agent_admin_router,prefix='/api/v1')
app.include_router(admin_router,prefix='/api/v1',tags=['admin'])
app.include_router(beginner_router,prefix='/api/v1')
app.include_router(card_factory_router,prefix='/api/v1')
app.include_router(director_router,prefix='/api/v1')
app.include_router(data_health_router,prefix='/api/v1')
app.include_router(legal_router,prefix='/api/v1',tags=['legal'])
app.include_router(push_router,prefix='/api/v1',tags=['push'])
app.include_router(profit_center_router,prefix='/api/v1')
app.include_router(reviews_router,prefix='/api/v1')
app.include_router(marketplace_router,prefix='/api/v1',tags=['integrations'])
app.include_router(onboarding_router,prefix='/api/v1')
app.include_router(store_router,prefix='/api/v1',tags=['stores'])
app.include_router(seller_data_router,prefix='/api/v1')
app.include_router(smart_fbo_router,prefix='/api/v1')
app.include_router(sync_router,prefix='/api/v1')
app.include_router(api_router,prefix='/api/v1')
