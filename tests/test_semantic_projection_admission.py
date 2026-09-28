import pytest
from autofde_lab.semantic_projection_admission import ProjectionClaim, ProjectionRefusal, admit, replay
S="git:o/s@"+"a"*40+":ontology.ttl"; C="git:o/c@"+"b"*40+":projection.ttl"
D="sha256:"+"1"*64; E="sha256:"+"2"*64; Q="sha256:"+"3"*64
def c(**kw):
 d=dict(source_subject=S,consumer_subject=C,source_digest=D,consumer_digest=E,
 required_terms=("A","B"),projected_terms=("B","A"),consequence_digest=Q)
 d.update(kw); return ProjectionClaim(**d)
def test_deterministic_replay():
 r=admit(c()); assert r==admit(c(required_terms=("B","A"))); assert replay(c(),r); assert r["authority"]=="NONE"
@pytest.mark.parametrize("kw,reason",[
 ({"source_subject":"main"},"EXACT_SUBJECT_REQUIRED"),
 ({"source_digest":"unknown"},"CONTENT_DIGEST_REQUIRED"),
 ({"authority":"DO"},"AUTHORITY_WIDENING"),
 ({"consequence_digest":"UNKNOWN"},"CONSEQUENCE_WITNESS_REQUIRED"),
 ({"projected_terms":("A",)},"SEMANTIC_LOSS:B")])
def test_refusals(kw,reason):
 with pytest.raises(ProjectionRefusal,match=reason): admit(c(**kw))
