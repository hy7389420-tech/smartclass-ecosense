from datetime import UTC, datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.config import get_settings
from app.database import session_scope
from app.models import ClassGroup, Classroom, Department, Lecture, Student

DEMO_STUDENTS = (
    ("STUDENT_A", "1", "Student A"),
    ("STUDENT_B", "2", "Student B"),
    ("STUDENT_C", "3", "Student C"),
    ("STUDENT_D", "4", "Student D"),
    ("STUDENT_E", "5", "Student E"),
)


def seed_demo() -> tuple[int, int, int]:
    timezone = ZoneInfo(get_settings().local_timezone)
    today = datetime.now(timezone).date()
    local_start = datetime.combine(today, time(10, 0), tzinfo=timezone)
    local_end = datetime.combine(today, time(11, 0), tzinfo=timezone)
    start_utc = local_start.astimezone(UTC)
    end_utc = local_end.astimezone(UTC)

    with session_scope() as session:
        department = session.scalar(
            select(Department).where(Department.name == "Demo Department")
        )
        if department is None:
            department = Department(name="Demo Department")
            session.add(department)
            session.flush()

        class_group = session.scalar(
            select(ClassGroup).where(
                ClassGroup.department_id == department.id,
                ClassGroup.name == "B.Tech",
                ClassGroup.section == "A",
                ClassGroup.year == 1,
            )
        )
        if class_group is None:
            class_group = ClassGroup(
                department_id=department.id,
                name="B.Tech",
                section="A",
                year=1,
            )
            session.add(class_group)
            session.flush()

        classroom = session.scalar(
            select(Classroom).where(Classroom.name == "Demo Room 101")
        )
        if classroom is None:
            classroom = Classroom(name="Demo Room 101", capacity=60)
            session.add(classroom)
            session.flush()

        for student_code, roll_no, name in DEMO_STUDENTS:
            existing_student = session.scalar(
                select(Student).where(Student.student_code == student_code)
            )
            if existing_student is None:
                session.add(
                    Student(
                        student_code=student_code,
                        roll_no=roll_no,
                        name=name,
                        class_id=class_group.id,
                    )
                )

        lecture = session.scalar(
            select(Lecture).where(
                Lecture.classroom_id == classroom.id,
                Lecture.class_id == class_group.id,
                Lecture.subject == "Demo Lecture",
                Lecture.start_time == start_utc,
            )
        )
        if lecture is None:
            lecture = Lecture(
                classroom_id=classroom.id,
                class_id=class_group.id,
                subject="Demo Lecture",
                start_time=start_utc,
                end_time=end_utc,
                status="scheduled",
            )
            session.add(lecture)
            session.flush()

        ids = department.id, classroom.id, lecture.id

    return ids


if __name__ == "__main__":
    department_id, classroom_id, lecture_id = seed_demo()
    print(
        "Demo data ready: "
        f"department_id={department_id}, classroom_id={classroom_id}, "
        f"lecture_id={lecture_id}"
    )
