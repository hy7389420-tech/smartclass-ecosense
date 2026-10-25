from pathlib import Path

import pytest
from sqlalchemy import URL, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app import database
from app.models import Base, ClassGroup, Department, Student, User

EXPECTED_TABLES = {
    "activity_windows",
    "alerts",
    "attendance_records",
    "audit_logs",
    "cameras",
    "classes",
    "classrooms",
    "departments",
    "faculty",
    "faculty_class_assignments",
    "insights",
    "lectures",
    "presence_events",
    "students",
    "suggestion_decisions",
    "suggestions",
    "system_settings",
    "users",
}


def make_sqlite_engine(path: Path | None = None):
    if path is None:
        return database.create_database_engine("sqlite://")
    url = URL.create("sqlite", database=str(path))
    return database.create_database_engine(url.render_as_string(hide_password=False))


def add_department_and_class(session: Session) -> ClassGroup:
    department = Department(name="Engineering")
    session.add(department)
    session.flush()
    class_group = ClassGroup(
        department_id=department.id,
        name="B.Tech",
        section="A",
        year=1,
    )
    session.add(class_group)
    session.flush()
    return class_group


def test_all_models_create_on_sqlite() -> None:
    engine = make_sqlite_engine()
    try:
        Base.metadata.create_all(engine)

        assert EXPECTED_TABLES == set(inspect(engine).get_table_names())
        assert inspect(engine).get_foreign_keys("presence_events")
        assert {
            index["name"] for index in inspect(engine).get_indexes("presence_events")
        } >= {
            "ix_presence_events_lecture_timestamp",
            "ix_presence_events_lecture_student",
        }
    finally:
        engine.dispose()


def test_student_code_must_be_unique() -> None:
    engine = make_sqlite_engine()
    Base.metadata.create_all(engine)
    make_session = sessionmaker(engine)
    try:
        with make_session.begin() as session:
            class_group = add_department_and_class(session)
            session.add(
                Student(
                    student_code="STUDENT_A",
                    roll_no="1",
                    name="Student A",
                    class_id=class_group.id,
                )
            )

        with pytest.raises(IntegrityError), make_session.begin() as session:
            session.add(
                Student(
                    student_code="STUDENT_A",
                    roll_no="2",
                    name="Duplicate Student",
                    class_id=1,
                )
            )
    finally:
        engine.dispose()


def test_sqlite_foreign_keys_are_enforced() -> None:
    engine = make_sqlite_engine()
    Base.metadata.create_all(engine)
    make_session = sessionmaker(engine)
    try:
        with pytest.raises(IntegrityError), make_session.begin() as session:
            session.add(
                Student(
                    student_code="ORPHAN",
                    roll_no="1",
                    name="Orphan Student",
                    class_id=987654,
                )
            )
    finally:
        engine.dispose()


def test_initial_migration_runs_on_a_fresh_database(tmp_path: Path) -> None:
    database_file = tmp_path / "migration_test.db"
    engine = make_sqlite_engine(database_file)
    config_path = Path(__file__).parents[1] / "alembic.ini"
    from alembic.config import Config

    from alembic import command

    config = Config(str(config_path))
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")

            assert EXPECTED_TABLES <= set(inspect(connection).get_table_names())
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
    finally:
        engine.dispose()


def test_student_user_mapping_is_unique_and_allows_unmapped_users() -> None:
    engine = make_sqlite_engine()
    Base.metadata.create_all(engine)
    make_session = sessionmaker(engine)
    try:
        with make_session.begin() as session:
            class_group = add_department_and_class(session)
            student = Student(
                student_code="STUDENT_A",
                roll_no="1",
                name="Student A",
                class_id=class_group.id,
            )
            session.add(student)
            session.flush()
            session.add_all(
                [
                    User(
                        email="unmapped-a@example.test",
                        password_hash="hash",
                        role="STUDENT",
                    ),
                    User(
                        email="unmapped-b@example.test",
                        password_hash="hash",
                        role="STUDENT",
                    ),
                    User(
                        email="mapped-a@example.test",
                        password_hash="hash",
                        role="STUDENT",
                        student_id=student.id,
                    ),
                ]
            )

        with pytest.raises(IntegrityError), make_session.begin() as session:
            session.add(
                User(
                    email="mapped-b@example.test",
                    password_hash="hash",
                    role="STUDENT",
                    student_id=1,
                )
            )
    finally:
        engine.dispose()


def test_student_mapping_migration_keeps_existing_users_unmapped(
    tmp_path: Path,
) -> None:
    database_file = tmp_path / "existing_user_migration.db"
    engine = make_sqlite_engine(database_file)
    config_path = Path(__file__).parents[1] / "alembic.ini"
    from alembic.config import Config

    from alembic import command

    config = Config(str(config_path))
    try:
        with engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "564597f82c24")
            connection.execute(
                text(
                    "INSERT INTO users "
                    "(id, email, password_hash, role, is_active, created_at) "
                    "VALUES (1, 'legacy@example.test', 'hash', 'STUDENT', 1, "
                    "'2026-01-01 00:00:00')"
                )
            )
            connection.commit()
            command.upgrade(config, "head")

            row = connection.execute(
                text(
                    "SELECT student_id, token_version FROM users "
                    "WHERE email = 'legacy@example.test'"
                )
            ).one()
            assert row == (None, 0)
    finally:
        engine.dispose()


def test_demo_seed_is_repeatable(monkeypatch) -> None:
    from scripts import seed_demo

    engine = make_sqlite_engine()
    Base.metadata.create_all(engine)
    monkeypatch.setattr(database, "SessionLocal", sessionmaker(engine))
    try:
        first_ids = seed_demo.seed_demo()
        second_ids = seed_demo.seed_demo()

        assert first_ids == second_ids
        with database.SessionLocal() as session:
            assert len(session.scalars(select(Student)).all()) == 5
    finally:
        engine.dispose()
