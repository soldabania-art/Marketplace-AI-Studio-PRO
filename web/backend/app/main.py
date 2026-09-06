from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .router import api_router

app = FastAPI(
    title="Marketplace AI Studio API",
    version="0.1.0",
    description="Backend for Marketplace AI Studio Cloud",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://marketplace-ai-studio-pro.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "marketplace-ai-studio-api", "version": "0.1.0"}


app.include_router(api_router, prefix="/api/v1")
