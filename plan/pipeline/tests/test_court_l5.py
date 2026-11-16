"""K-L5 court: role_grant events, store.can scoping, PLAN_AUTHZ enforcement (real store)."""
import tomllib
from pathlib import Path

import pytest

from enterprise_pipeline import store
from helpers_world import nm

ROSTER = tomllib.loads((Path(__file__).parent / "avatar_roster.toml").read_text())
ROLES = ("super_user", "entity_lead", "team_lead", "coordinator", "provider_ops")


@pytest.fixture()
def world(tmp_path):
    """Own minimal world (entity + primary client) so L5 does not depend on build()'s churn."""
    sp = tmp_path / "s.jsonl"
    A = lambda av, k, p: store.append(av, k, p, path=sp)
    o = {"ent": nm("ent"), "dba": nm("dba"), "cli": nm("cli")}
    A("admin", "entity", {"name": o["ent"], "dba": o["dba"]})
    A("admin", "client", {"name": o["cli"], "kind": "primary_client"})
    return sp, A, o


def _person(A):
    n = nm("person")
    A("admin", "person", {"name": n})
    return n


def _roles(sp, n):
    return next(p for p in store.reduce(store.read(sp))["people"] if p["id"] == n)["roles"]


def test_roster_declares_kinds():
    assert ROSTER["kinds"] and set(ROSTER["kinds"].values()) <= {"entity", "client"}


def test_person_and_grants_positive(world):
    sp, A, o = world
    p = _person(A)
    A("admin", "role_grant", {"person": p, "role": "super_user"})
    A("admin", "role_grant", {"person": p, "role": "entity_lead", "entity": o["ent"]})
    A("admin", "role_grant", {"person": p, "role": "team_lead", "client": o["cli"]})
    assert len(_roles(sp, p)) == 3  # L23 multiple grants


@pytest.mark.parametrize("role", ROLES)
def test_every_role_grantable_or_typed_refusal(world, role):
    sp, A, o = world
    p = _person(A)
    pay = {"person": p, "role": role}
    if role == "entity_lead":
        pay["entity"] = o["ent"]
    if role == "team_lead":
        pay["client"] = o["cli"]
    A("admin", "role_grant", pay)
    assert _roles(sp, p)


def test_grant_refusals_antivacuity(world):
    sp, A, o = world
    p = _person(A)
    for pay, msg in (({"person": nm("ghost"), "role": "super_user"}, "UNKNOWN[person:"),
                     ({"person": p, "role": nm("bogus")}, "BAD_ROLE["),
                     ({"person": p, "role": "entity_lead"}, "MISSING[entity"),
                     ({"person": p, "role": "team_lead"}, "MISSING[client"),
                     ({"person": p, "role": "team_lead", "client": nm("nc")}, "UNKNOWN[client:")):
        with pytest.raises(store.Refused, match=msg.replace("[", r"\[")):
            A("admin", "role_grant", pay)
    assert _roles(sp, p) == []


def test_can_scoping_and_twin(world):
    sp, A, o = world
    sup, el, tl = _person(A), _person(A), _person(A)
    A("admin", "role_grant", {"person": sup, "role": "super_user"})
    A("admin", "role_grant", {"person": el, "role": "entity_lead", "entity": o["ent"]})
    A("admin", "role_grant", {"person": tl, "role": "team_lead", "client": o["cli"]})
    st = store.reduce(store.read(sp))
    act = next(iter(ROSTER["kinds"]))
    other = nm("other")
    assert store.can(st, sup, act, entity=other, client=other)
    assert store.can(st, el, act, entity=o["ent"], client=o["cli"])
    assert not store.can(st, el, act, entity=other)           # twin: wrong entity
    assert store.can(st, tl, act, client=o["cli"])
    assert not store.can(st, tl, act, client=other)           # twin: wrong client
    assert not store.can(st, nm("nobody"), act, entity=o["ent"], client=o["cli"])


def test_authz_off_by_default_no_check(world, monkeypatch):
    sp, A, o = world
    monkeypatch.delenv("PLAN_AUTHZ", raising=False)
    store.append("not_a_person", "taxonomy", {"type": "trade", "name": nm("t")}, path=sp)


def test_authz_on_refuses_unauthorized_and_allows_super_user(world, monkeypatch):
    sp, A, o = world
    sup = _person(A)
    A("admin", "role_grant", {"person": sup, "role": "super_user"})
    monkeypatch.setenv("PLAN_AUTHZ", "1")
    pay = {"type": "trade", "name": nm("t")}
    with pytest.raises(store.Refused, match=r"AUTHZ\[nobody,taxonomy\]"):
        store.append("nobody", "taxonomy", pay, path=sp)
    store.append(sup, "taxonomy", pay, path=sp)               # twin: same event, authorized
    n = len(store.read(sp))
    with pytest.raises(store.Refused):
        store.append("nobody", "taxonomy", {"type": "trade", "name": nm("t")}, path=sp)
    assert len(store.read(sp)) == n                           # refusal appends nothing
