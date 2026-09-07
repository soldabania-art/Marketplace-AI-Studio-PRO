from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
is_sqlite = settings.database_url.startswith("sqlite")
engine_kwargs = {
    "pool_pre_ping": True,
    "connect_args": {"check_same_thread": False} if is_sqlite else {},
}
if not is_sqlite:
    engine_kwargs.update({
        "pool_size": max(1, settings.database_pool_size),
        "max_overflow": max(0, settings.database_max_overflow),
        "pool_timeout": max(1, settings.database_pool_timeout_seconds),
        "pool_recycle": 1800,
    })

engine = create_engine(settings.database_url, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
