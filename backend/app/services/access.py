from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.models import (
    ClassGroup,
    Faculty,
    FacultyClassAssignment,
    Lecture,
    Student,
    User,
)


def require_roles(user: User, *roles: str) -> None:
    if user.role not in roles:
        raise ApiError(403, "FORBIDDEN", "You do not have access to this resource.")


def class_scope(session: Session, user: User) -> Select[tuple[int]]:
    if user.role == "ADMIN":
        return select(ClassGroup.id)
    if user.role == "STUDENT":
        if user.student_id is None:
            raise ApiError(
                403,
                "STUDENT_MAPPING_REQUIRED",
                "Student account is not linked to a student record.",
            )
        return select(Student.class_id).where(Student.id == user.student_id)

    faculty = session.scalar(select(Faculty).where(Faculty.user_id == user.id))
    if faculty is None:
        raise ApiError(
            403,
            "SCOPE_MAPPING_REQUIRED",
            "Account does not have an assigned department or faculty record.",
        )
    if user.role == "HOD":
        return select(ClassGroup.id).where(
            ClassGroup.department_id == faculty.department_id
        )
    if user.role == "FACULTY":
        return select(FacultyClassAssignment.class_id).where(
            FacultyClassAssignment.faculty_id == faculty.id
        )
    raise ApiError(403, "FORBIDDEN", "You do not have access to this resource.")


def assert_can_view_class(session: Session, user: User, class_id: int) -> None:
    if user.role == "ADMIN":
        return
    is_visible = session.scalar(
        select(ClassGroup.id).where(
            ClassGroup.id == class_id,
            ClassGroup.id.in_(class_scope(session, user)),
        )
    )
    if is_visible is None:
        raise ApiError(403, "FORBIDDEN", "You do not have access to this class.")


def assert_can_view_student(session: Session, user: User, student_id: int) -> Student:
    student = session.get(Student, student_id)
    if student is None:
        raise ApiError(404, "STUDENT_NOT_FOUND", "Student was not found.")
    if user.role == "STUDENT":
        if user.student_id is None:
            raise ApiError(
                403,
                "STUDENT_MAPPING_REQUIRED",
                "Student account is not linked to a student record.",
            )
        if student.id != user.student_id:
            raise ApiError(403, "FORBIDDEN", "You can only access your own data.")
        return student
    assert_can_view_class(session, user, student.class_id)
    return student


def assert_can_view_lecture(session: Session, user: User, lecture_id: int) -> Lecture:
    lecture = session.get(Lecture, lecture_id)
    if lecture is None:
        raise ApiError(404, "LECTURE_NOT_FOUND", "Lecture was not found.")
    assert_can_view_class(session, user, lecture.class_id)
    return lecture
