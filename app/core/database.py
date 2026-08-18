from typing import Generator
from sqlalchemy import create_engine, text
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
    import app.models.invitation  # noqa

    # Create enum type & schema migrations if not exist
    with engine.begin() as conn:
        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'userstatus') THEN
                    CREATE TYPE userstatus AS ENUM ('INVITED', 'ACTIVE', 'SUSPENDED', 'DEACTIVATED');
                END IF;
            END$$;
        """))
        
        # Add columns if missing
        conn.execute(text("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='status') THEN
                    ALTER TABLE users ADD COLUMN status userstatus DEFAULT 'ACTIVE' NOT NULL;
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='employees' AND column_name='team_id') THEN
                    ALTER TABLE employees ADD COLUMN team_id VARCHAR(36);
                END IF;
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='employees' AND column_name='primary_manager_id') THEN
                    ALTER TABLE employees ADD COLUMN primary_manager_id VARCHAR(36);
                END IF;
            END$$;
        """))

    Base.metadata.create_all(bind=engine)
