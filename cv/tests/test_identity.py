import pytest

from cv.config import DEMO_STUDENTS
from cv.identity import IdentityMapper


def test_manual_assignment_maps_track_id_to_demo_student() -> None:
    mapper = IdentityMapper(DEMO_STUDENTS)

    identity = mapper.assign(track_id=14, key="1")

    assert identity.student_id == "STUDENT_A"
    assert identity.name == "Student A"
    assert identity.flagged_for_review is False
    assert mapper.get(14) == identity


def test_unknown_track_id_is_flagged_for_review() -> None:
    mapper = IdentityMapper(DEMO_STUDENTS)

    identity = mapper.get(track_id=99)

    assert identity.student_id == "UNKNOWN"
    assert identity.name == "UNKNOWN"
    assert identity.flagged_for_review is True


def test_assignment_rejects_unconfigured_key() -> None:
    mapper = IdentityMapper(DEMO_STUDENTS)

    with pytest.raises(ValueError, match="No demo student"):
        mapper.assign(track_id=14, key="9")
