from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class StudentIdentity:
    student_id: str
    name: str
    flagged_for_review: bool


class IdentityMapper:
    def __init__(self, demo_students: Mapping[str, tuple[str, str]]) -> None:
        self._demo_students = {
            key: StudentIdentity(student_id, name, flagged_for_review=False)
            for key, (student_id, name) in demo_students.items()
        }
        self._track_identities: dict[int, StudentIdentity] = {}

    def assign(self, track_id: int, key: str) -> StudentIdentity:
        if key not in self._demo_students:
            raise ValueError(f"No demo student is assigned to key {key!r}")
        identity = self._demo_students[key]
        self._track_identities[track_id] = identity
        return identity

    def get(self, track_id: int) -> StudentIdentity:
        return self._track_identities.get(
            track_id,
            StudentIdentity(
                student_id="UNKNOWN",
                name="UNKNOWN",
                flagged_for_review=True,
            ),
        )
