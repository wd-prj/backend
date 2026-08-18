from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from app.models.base import Base
    # Import all models to register with Base metadata
    import app.models.user  # noqa
    import app.models.organization  # noqa
    import app.models.leave  # noqa
    import app.models.employee  # noqa
    import app.models.request  # noqa
    import app.models.audit  # noqa

    Base.metadata.create_all(bind=engine)
