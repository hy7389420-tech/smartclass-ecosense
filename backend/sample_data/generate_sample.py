from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    ClassGroup,
    Classroom,
    Department,
    Lecture,
    PresenceEvent,
    Student,
)
from app.services.attendance import finalize_attendance

SAMPLE_DEPARTMENT = "Phase 7 Simulated Department"
SAMPLE_CLASS_NAME = "Simulated B.Tech"
SAMPLE_CLASS_SECTION = "P7"
SAMPLE_ROOM = "Phase 7 Simulated Room"
SAMPLE_SUBJECT = "Simulated Presence Lecture"
STUDENT_COUNT = 60
LECTURE_COUNT = 8
SPIKE_LECTURE_INDEX = 7
NORMAL_EXIT_COUNT = 1
SPIKE_EXIT_COUNT = 7


def generate_sample_data(
    session: Session, base_date: date | None = None
) -> dict[str, int]:
    timezone = ZoneInfo(get_settings().local_timezone)
    sample_date = base_date or datetime.now(timezone).date()
    department = _get_or_create_department(session)
    class_group = _get_or_create_class(session, department.id)
    classroom = _get_or_create_classroom(session)
    students = _get_or_create_students(session, class_group.id)
    lecture_ids: list[int] = []

    for index in range(LECTURE_COUNT):
        lecture_date = sample_date - timedelta(days=LECTURE_COUNT - index)
        local_start = datetime.combine(lecture_date, time(10, 0), tzinfo=timezone)
        start = local_start.astimezone(UTC)
        end = (local_start + timedelta(hours=1)).astimezone(UTC)
        lecture = session.scalar(
            select(Lecture).where(
                Lecture.classroom_id == classroom.id,
                Lecture.class_id == class_group.id,
                Lecture.subject == SAMPLE_SUBJECT,
                Lecture.start_time == start,
            )
        )
        if lecture is None:
            lecture = Lecture(
                classroom_id=classroom.id,
                class_id=class_group.id,
                subject=SAMPLE_SUBJECT,
                start_time=start,
                end_time=end,
                status="completed",
            )
            session.add(lecture)
            session.flush()
            _add_lecture_events(
                session,
                lecture,
                students,
                local_start,
                timezone,
                SPIKE_EXIT_COUNT if index == SPIKE_LECTURE_INDEX else NORMAL_EXIT_COUNT,
            )
            session.flush()
            finalize_attendance(session, lecture, now=end)
        lecture_ids.append(lecture.id)

    return {
        "department_id": department.id,
        "class_id": class_group.id,
        "classroom_id": classroom.id,
        "student_count": len(students),
        "lecture_count": len(lecture_ids),
        "spike_lecture_id": lecture_ids[SPIKE_LECTURE_INDEX],
    }


def _get_or_create_department(session: Session) -> Department:
    department = session.scalar(
        select(Department).where(Department.name == SAMPLE_DEPARTMENT)
    )
    if department is None:
        department = Department(name=SAMPLE_DEPARTMENT)
        session.add(department)
        session.flush()
    return department


def _get_or_create_class(session: Session, department_id: int) -> ClassGroup:
    class_group = session.scalar(
        select(ClassGroup).where(
            ClassGroup.department_id == department_id,
            ClassGroup.name == SAMPLE_CLASS_NAME,
            ClassGroup.section == SAMPLE_CLASS_SECTION,
            ClassGroup.year == 1,
        )
    )
    if class_group is None:
        class_group = ClassGroup(
            department_id=department_id,
            name=SAMPLE_CLASS_NAME,
            section=SAMPLE_CLASS_SECTION,
            year=1,
        )
        session.add(class_group)
        session.flush()
    return class_group


def _get_or_create_classroom(session: Session) -> Classroom:
    classroom = session.scalar(select(Classroom).where(Classroom.name == SAMPLE_ROOM))
    if classroom is None:
        classroom = Classroom(name=SAMPLE_ROOM, capacity=STUDENT_COUNT)
        session.add(classroom)
        session.flush()
    return classroom


def _get_or_create_students(session: Session, class_id: int) -> list[Student]:
    students = []
    for index in range(1, STUDENT_COUNT + 1):
        code = f"P7_SIM_STUDENT_{index:02}"
        student = session.scalar(select(Student).where(Student.student_code == code))
        if student is None:
            student = Student(
                student_code=code,
                roll_no=str(index),
                name=f"Simulated Student {index:02}",
                class_id=class_id,
            )
            session.add(student)
        elif student.class_id != class_id:
            raise ValueError(
                f"Sample student code {code} is already assigned to another class."
            )
        students.append(student)
    session.flush()
    return students


def _add_lecture_events(
    session: Session,
    lecture: Lecture,
    students: list[Student],
    local_start: datetime,
    timezone: ZoneInfo,
    exit_count: int,
) -> None:
    events = [
        PresenceEvent(
            client_event_id=f"p7-{lecture.id}-{student.id}-entry",
            lecture_id=lecture.id,
            classroom_id=lecture.classroom_id,
            student_id=student.id,
            student_code_raw=student.student_code,
            event_type="ENTRY",
            timestamp_utc=local_start.astimezone(UTC),
            confidence=1.0,
            source="simulated",
            flagged_for_review=False,
            review_status="not_required",
            presence_confirmed=True,
        )
        for student in students
    ]
    for index, student in enumerate(students[:exit_count]):
        events.extend(
            (
                PresenceEvent(
                    client_event_id=f"p7-{lecture.id}-{student.id}-exit",
                    lecture_id=lecture.id,
                    classroom_id=lecture.classroom_id,
                    student_id=student.id,
                    student_code_raw=student.student_code,
                    event_type="EXIT",
                    timestamp_utc=(
                        local_start + timedelta(minutes=25, seconds=index)
                    ).astimezone(UTC),
                    confidence=1.0,
                    source="simulated",
                    flagged_for_review=False,
                    review_status="not_required",
                    presence_confirmed=True,
                ),
                PresenceEvent(
                    client_event_id=f"p7-{lecture.id}-{student.id}-return",
                    lecture_id=lecture.id,
                    classroom_id=lecture.classroom_id,
                    student_id=student.id,
                    student_code_raw=student.student_code,
                    event_type="RETURN",
                    timestamp_utc=(local_start + timedelta(minutes=40)).astimezone(UTC),
                    confidence=1.0,
                    source="simulated",
                    flagged_for_review=False,
                    review_status="not_required",
                    presence_confirmed=True,
                ),
            )
        )
    session.add_all(events)


def main() -> None:
    from app.database import session_scope

    with session_scope() as session:
        summary = generate_sample_data(session)
    print(
        "Simulated Phase 7 data ready: "
        f"{summary['student_count']} students, "
        f"{summary['lecture_count']} lectures, "
        f"spike_lecture_id={summary['spike_lecture_id']}"
    )


if __name__ == "__main__":
    main()
