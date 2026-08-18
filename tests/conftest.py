import pytest
from sqlalchemy.orm import Session
from app.core.database import SessionLocal, init_db
from app.seed.run_seed import check_and_seed


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    check_and_seed()


@pytest.fixture
def db_session() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
