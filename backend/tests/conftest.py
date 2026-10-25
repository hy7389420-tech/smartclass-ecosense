from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL
from sqlalchemy.orm import Session, sessionmaker

from app.database import create_database_engine, get_db
from app.main import app
from app.models import Base


@pytest.fixture
def session_factory(tmp_path) -> Iterator[sessionmaker[Session]]:
    database_url = URL.create(
        "sqlite",
        database=str(tmp_path / "api_test.db"),
    ).render_as_string(hide_password=False)
    engine = create_database_engine(database_url)
    Base.metadata.create_all(engine)
    test_session = sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
    yield test_session
    engine.dispose()


@pytest.fixture
def client(session_factory: sessionmaker[Session]) -> Iterator[TestClient]:

    def override_get_db():
        with session_factory.begin() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()
