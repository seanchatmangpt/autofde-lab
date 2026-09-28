from dataclasses import dataclass


@dataclass(frozen=True)
class Admission:
    subject_id: str
    epoch_id: str
    semantic_ok: bool
    provenance_ok: bool
    falsifiers: list[str]

    @property
    def admitted(self):
        return self.semantic_ok and self.provenance_ok and not self.falsifiers


def require_admitted(a):
    if not a.admitted:
        raise ValueError("PTD epoch refused")
