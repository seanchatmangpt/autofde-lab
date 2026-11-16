"""K17: Hypothesis stateful model of store.append (stage / uniqueness / reference rules)."""
from __future__ import annotations

import os
import re
import shutil
import tempfile
from pathlib import Path

from . import Case, Outcome, Skip

KIND = "K17"
TITLE = "stateful property model of store.append (hypothesis)"
RUN_COUNTS = (10, 25)
ACCEPTED = [0]  # accepted appends across a run: anti-vacuity witness


def probe():
    try:
        import hypothesis  # noqa: F401
        from enterprise_pipeline import store  # noqa: F401
    except ImportError as e:
        return Skip(f"import failed: {e}", "uv pip install --python <autofde-lab>/.venv/bin/python hypothesis (PYTHONPATH=pipeline)")
    return None


def cases():
    return [Case(id=f"runs{n}", expect="PLAN", payload={"max_examples": n}) for n in RUN_COUNTS]


def _machine_cls():
    import hypothesis.strategies as st
    from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

    from enterprise_pipeline import store

    names = st.sampled_from([f"n{i}" for i in range(6)])
    tax_types = {"trade": "trade", "sub_trade": "sub_trade", "state": "state_jurisdiction",
                 "priority": "priority_tier"}
    tax_types = {k: v for k, v in tax_types.items() if v in store.subtypes("taxonomy")}
    client_kind = store.subtypes("client")[0]
    prov_kind = store.subtypes("provider")[0]
    wo_kind = store.subtypes("work_order")[0]

    class Machine(RuleBasedStateMachine):
        def __init__(self):
            super().__init__()
            self.dir = tempfile.mkdtemp(prefix="k17_")
            self.path = Path(self.dir) / "events.ndjson"
            os.environ["PLAN_STORE"] = str(self.path)
            self.nents = 0
            self.names = set()
            self.t = {k: [] for k in tax_types}
            self.clients, self.sites, self.coords, self.provs = [], [], [], []
            self.wos = {}  # name -> stage
            self.n_ok = 0

        def teardown(self):
            shutil.rmtree(self.dir, ignore_errors=True)

        # ---- harness: append and compare refusal code with the model
        def _try(self, kind, payload, expected):
            try:
                store.append("k17", kind, payload)
            except store.Refused as e:
                code = re.match(r"[A-Z_]+", str(e)).group(0)
                assert expected == code, f"{kind} {payload}: refused {e}, model expected {expected}"
                return False
            assert expected is None, f"{kind} {payload}: accepted, model expected {expected}"
            self.n_ok += 1
            ACCEPTED[0] += 1
            return True

        def _fresh(self, *ns):
            for n in ns:
                if n in self.names:
                    return "DUPLICATE"
            return None

        @invariant()
        def store_matches_accepts(self):
            assert len(store.read(self.path)) == self.n_ok

        @rule(name=names, dba=names)
        def entity(self, name, dba):
            exp = "DUPLICATE" if (name in self.names or dba == name or dba in self.names) else None
            if self._try("entity", {"name": name, "dba": dba}, exp):
                self.nents += 1
                self.names |= {name, dba}

        @rule(which=st.sampled_from(sorted(tax_types)), name=names)
        def taxonomy(self, which, name):
            exp = self._fresh(name)
            if self._try("taxonomy", {"type": tax_types[which], "name": name}, exp):
                self.t[which].append(name)
                self.names.add(name)

        def _plain(self, kind, name, payload, bucket, needs_ent=False):
            if not self.nents or (needs_ent and self.nents > 1):
                exp = "MISSING"  # no entity yet, or >1 entities and payload names none
            else:
                exp = self._fresh(name)
            if self._try(kind, payload, exp):
                bucket.append(name)
                self.names.add(name)

        @rule(name=names)
        def client(self, name):
            self._plain("client", name, {"name": name, "kind": client_kind}, self.clients,
                        needs_ent=True)

        @rule(name=names)
        def coordinator(self, name):
            self._plain("coordinator", name, {"name": name}, self.coords)

        @rule(name=names)
        def provider(self, name):
            self._plain("provider", name, {"name": name, "kind": prov_kind}, self.provs,
                        needs_ent=True)

        @rule(name=names, client=names, state=names)
        def site(self, name, client, state):
            if not self.nents:
                exp = "MISSING"
            elif client not in self.clients or state not in self.t["state"]:
                exp = "UNKNOWN"
            else:
                exp = self._fresh(name)
            if self._try("site", {"name": name, "client": client, "state": state,
                                  "territory_client": client}, exp):
                self.sites.append(name)
                self.names.add(name)

        @rule(name=names, client=names, site=names, coord=names, trade=names, sub=names,
              prio=names)
        def work_order(self, name, client, site, coord, trade, sub, prio):
            if not self.nents:
                exp = "MISSING"
            elif (client not in self.clients or site not in self.sites or coord not in self.coords
                  or trade not in self.t["trade"] or sub not in self.t["sub_trade"]
                  or prio not in self.t["priority"]):
                exp = "UNKNOWN"
            else:
                exp = self._fresh(name)
            p = {"name": name, "kind": wo_kind, "wo_type": "reactive", "client": client,
                 "site": site, "trade": trade, "sub_trade": sub, "priority": prio,
                 "coordinator": coord, "nte_cents": 1000, "onsite_sla_min": 60,
                 "complete_sla_min": 120}
            if self._try("work_order", p, exp):
                self.wos[name] = "intake"
                self.names |= {name, f"{name}_visit", f"{name}_proposal", f"{name}_invoice",
                               f"{name}_payout"}

        def _stage_rule(self, kind, wo, extra, want, to):
            if not self.nents:
                exp = "MISSING"
            elif wo not in self.wos:
                exp = "UNKNOWN"
            elif extra is not None and extra not in self.provs:
                exp = "UNKNOWN"
            elif self.wos[wo] != want:
                exp = "STAGE"
            else:
                exp = None
            p = {"wo": wo} if extra is None else {"wo": wo, "provider": extra}
            if self._try(kind, p, exp):
                self.wos[wo] = to

        @rule(wo=names, prov=names)
        def dispatch(self, wo, prov):
            self._stage_rule("dispatch", wo, prov, "intake", "dispatched")

        @rule(wo=names)
        def checkin(self, wo):
            self._stage_rule("checkin", wo, None, "dispatched", "on-site")

        @rule(wo=names)
        def checkout(self, wo):
            self._stage_rule("checkout", wo, None, "on-site", "qa-review")

    return Machine


def run(case):
    from hypothesis import HealthCheck, settings
    from hypothesis.stateful import run_state_machine_as_test

    ACCEPTED[0] = 0
    prev = os.environ.get("PLAN_STORE")
    cfg = settings(max_examples=case.payload["max_examples"], stateful_step_count=30,
                   deadline=None, database=None, derandomize=True,
                   suppress_health_check=list(HealthCheck))
    try:
        run_state_machine_as_test(_machine_cls(), settings=cfg)
    except AssertionError as e:
        return Outcome("NO_PLAN", f"divergence: {str(e)[:300]}")
    finally:
        if prev is None:
            os.environ.pop("PLAN_STORE", None)
        else:
            os.environ["PLAN_STORE"] = prev
    if ACCEPTED[0] == 0:
        return Outcome("NO_PLAN", "vacuous: model accepted no append")
    return Outcome("PLAN", f"no divergence in {case.payload['max_examples']} runs; "
                           f"{ACCEPTED[0]} accepted appends")
