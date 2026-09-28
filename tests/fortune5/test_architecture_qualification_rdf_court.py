from pathlib import Path

def test_equilibrium_ttl_is_executable_contract_surface():
    text = Path("ggen/fortune5/ontology/architecture-qualification.ttl").read_text()
    required = (
        "ce:ExactSubject", "ce:PositiveEvidence", "ce:FalsifierEvidence",
        "ce:AuthorityCeiling", "ce:DeterministicReplay", "ce:UNKNOWN",
        "ce:REFUSED", "ce:CrossSubjectReuse", "ce:ForgedReceipt",
        "ce:AuthorityLaundering", "ce:ReplayDivergence",
    )
    assert all(term in text for term in required)
    assert "ce:confersAuthority false" in text
