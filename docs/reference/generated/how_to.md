# How to: Using autofde-lab

## Prerequisites


- .validation/gymact-base/src/gymact/action_contract.py::AcknowledgementStatus (class)

- .validation/gymact-base/src/gymact/action_contract.py::ActionDefinition (class)

- .validation/gymact-base/src/gymact/action_contract.py::AdmissionResult (class)

- .validation/gymact-base/src/gymact/action_contract.py::AuthorityRequirement (class)

- .validation/gymact-base/src/gymact/action_contract.py::CausalLocality (class)

- .validation/gymact-base/src/gymact/action_contract.py::CostModel (class)

- .validation/gymact-base/src/gymact/action_contract.py::ExecutionAcknowledgement (class)

- .validation/gymact-base/src/gymact/action_contract.py::ExecutionGrant (class)

- .validation/gymact-base/src/gymact/action_contract.py::ExpectedEffect (class)

- .validation/gymact-base/src/gymact/action_contract.py::IdempotencyClass (class)

- .validation/gymact-base/src/gymact/action_contract.py::ObservationConfidence (class)

- .validation/gymact-base/src/gymact/action_contract.py::PreparedAction (class)

- .validation/gymact-base/src/gymact/action_contract.py::ProviderHealth (class)

- .validation/gymact-base/src/gymact/action_contract.py::ProviderMetadata (class)

- .validation/gymact-base/src/gymact/action_contract.py::ReconciliationDisposition (class)

- .validation/gymact-base/src/gymact/action_contract.py::ReconciliationResult (class)

- .validation/gymact-base/src/gymact/action_contract.py::RefusalCode (class)

- .validation/gymact-base/src/gymact/action_contract.py::ReversalClass (class)

- .validation/gymact-base/src/gymact/action_contract.py::SubjectRef (class)

- .validation/gymact-base/src/gymact/action_contract.py::UncertainExecution (class)

- .validation/gymact-base/src/gymact/action_contract.py::VerificationKind (class)

- .validation/gymact-base/src/gymact/action_contract.py::VerificationStrategy (class)

- .validation/gymact-base/src/gymact/action_contract.py::admit_execution (function)

- .validation/gymact-base/src/gymact/action_contract.py::admit_retry (function)

- .validation/gymact-base/src/gymact/action_contract.py::construct_prepared_action (function)

- .validation/gymact-base/src/gymact/action_contract.py::enforce_execution_semantics (function)

- .validation/gymact-base/src/gymact/action_contract.py::require_aware_expiry (function)

- .validation/gymact-base/src/gymact/action_contract.py::require_quorum_for_quorum_strategy (function)

- .validation/gymact-base/src/gymact/action_contract.py::retry_requires_explicit_disposition (function)

- .validation/gymact-base/src/gymact/authority.py::AllowListAuthorityResolver (class)

- .validation/gymact-base/src/gymact/authority.py::AuthorityResolver (class)

- .validation/gymact-base/src/gymact/authority.py::DenyAuthorityResolver (class)

- .validation/gymact-base/src/gymact/authority.py::__init__ (function)

- .validation/gymact-base/src/gymact/authority.py::authorize (function)

- .validation/gymact-base/src/gymact/brce.py::BRCEBroker (class)

- .validation/gymact-base/src/gymact/brce.py::BrokerRequest (class)

- .validation/gymact-base/src/gymact/brce.py::BrokerRuntime (class)

- .validation/gymact-base/src/gymact/brce.py::_BrokerRuntimeView (class)

- .validation/gymact-base/src/gymact/brce.py::__init__ (function)

- .validation/gymact-base/src/gymact/brce.py::act (function)


## Steps


1. Use `AcknowledgementStatus` from `.validation/gymact-base/src/gymact/action_contract.py`.

2. Use `ActionDefinition` from `.validation/gymact-base/src/gymact/action_contract.py`.

3. Use `AdmissionResult` from `.validation/gymact-base/src/gymact/action_contract.py`.

4. Use `AuthorityRequirement` from `.validation/gymact-base/src/gymact/action_contract.py`.

5. Use `CausalLocality` from `.validation/gymact-base/src/gymact/action_contract.py`.

6. Use `CostModel` from `.validation/gymact-base/src/gymact/action_contract.py`.

7. Use `ExecutionAcknowledgement` from `.validation/gymact-base/src/gymact/action_contract.py`.

8. Use `ExecutionGrant` from `.validation/gymact-base/src/gymact/action_contract.py`.

9. Use `ExpectedEffect` from `.validation/gymact-base/src/gymact/action_contract.py`.

10. Use `IdempotencyClass` from `.validation/gymact-base/src/gymact/action_contract.py`.

11. Use `ObservationConfidence` from `.validation/gymact-base/src/gymact/action_contract.py`.

12. Use `PreparedAction` from `.validation/gymact-base/src/gymact/action_contract.py`.


## Verified snippet

<!-- The snippet slot carries code copied from the extracted code surface -->
<!-- (doc:Claim rows whose doc:attribute is "snippet"), never agent prose. -->

```rust
// .validation/gymact-base/src/gymact/action_contract.py :: admit_execution
admit_executionaction: ActionDefinition, prepared: PreparedAction, grant: ExecutionGrant, *, current_revision: str | None=None, now: datetime | None=None
```

<!-- AGENT-COMMENTARY-BEGIN -->
<!-- The ONLY region an agent may write into. Bounds: <= 12 lines,    -->
<!-- <= 100 chars/line, no new code facts (any new symbol mentioned   -->
<!-- must exist in queries/ast_extract.rq output; the doc_quality     -->
<!-- court fails Phi_halluc > 0.001 otherwise). No tables, no         -->
<!-- signatures, no parameters, no error lists — AGENT-FORBIDDEN      -->
<!-- everywhere.                                                      -->
<!-- AGENT-COMMENTARY-END -->
