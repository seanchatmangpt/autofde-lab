# S-k8-dups
Standing: PASS
Subject: pipeline/tests/plankinds/k08_executor.py (only file edited).
Finding: real executor behavior is right. A dup copy shares the original's timestamp, so it is refused
only when the action's at-start effects delete a fact its own at-start condition needs (dup-2,3,4).
The other six (dup-0,1,5,6,7,8) are idempotent re-assertions: rc 0, identical ledger.
Fix: expectation derived from the real domain (executor.pddl.Domain) via _self_consuming(); no literals.
Gate: pytest pipeline/tests/test_plankinds_exec_courts.py -> K8 passed; K9 failed (pre-existing, not
owned: "Name wo-territory-cleared already defined" in M12 planner case).
