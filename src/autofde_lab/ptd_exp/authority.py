from dataclasses import dataclass
@dataclass(frozen=True)
class AuthorityBoundary: subject_id:str; authority_id:str; standing_id:str|None=None
def admit_authority(b,expected,allowed):
 if b.subject_id!=expected: raise ValueError("authority subject mismatch")
 if b.authority_id not in allowed: raise PermissionError("authority refused")
