from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import URL
from sqlalchemy.orm import Session, sessionmaker

from app.database import create_database_engine, get_db
from app.main import app
from app.models import Base, User
from app.services.auth import (
    create_access_token,
    hash_password,
    login_rate_limiter,
)

TEST_ADMIN_PASSWORD_HASH = hash_password("test-admin-password")


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
    login_rate_limiter.clear("testclient")

    def override_get_db():
        with session_factory.begin() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as test_client:
            with session_factory.begin() as session:
                admin = User(
                    email="test-admin@example.test",
                    password_hash=TEST_ADMIN_PASSWORD_HASH,
                    role="ADMIN",
                    is_active=True,
                )
                session.add(admin)
                session.flush()
                access_token = create_access_token(admin)
            test_client.headers["Authorization"] = f"Bearer {access_token}"
            yield test_client
    finally:
        app.dependency_overrides.clear()
        login_rate_limiter.clear("testclient")
