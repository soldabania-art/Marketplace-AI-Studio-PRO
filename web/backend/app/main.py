from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .account_router import router as account_router
from .admin_router import router as admin_router
from .config import get_settings
from .db import Base, engine
from .router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


settings = get_settings()
app = FastAPI(
    title=settings.app_name,
    version="0.3.0",
    description="Backend for Marketplace AI Studio Cloud",
    lifespan=lifespan,
)

allowed_origins = {
    "http://localhost:3000",
    "https://marketplace-ai-studio-pro.vercel.app",
    settings.frontend_url.rstrip("/"),
}
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(origin for origin in allowed_origins if origin),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "marketplace-ai-studio-api", "version": "0.3.0"}


app.include_router(account_router, prefix="/api/v1", tags=["account"])
app.include_router(admin_router, prefix="/api/v1", tags=["admin"])
app.include_router(api_router, prefix="/api/v1")
