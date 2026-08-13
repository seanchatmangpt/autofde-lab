# Standing and Evidence

AutoFDE Lab uses explicit evidence states.

| State | Meaning |
|---|---|
| `UNKNOWN` | Not established. |
| `PARTIAL_ALIVE` | Some required transitions executed; crown not established. |
| `ALIVE` | Exact admitted subject executed and the required verifier passed. |
| `BLOCKED` | A dependency, authority, transport, or environment edge prevented execution. |
| `BUILD_BROKEN` | A required build/toolchain transition failed. |
| `UNSUPPORTED` | The implementation does not provide the requested capability. |
| `REFUSED(...)` | Admission or authority rejected an operation for a typed reason. |

Track observed, admitted, executed, changed, verified, inferred, refused, blocked, and unsupported independently.

## ALIVE rule

`ALIVE` requires observed execution against the exact admitted subject. Inspection is not execution. A connector object is not a mounted tree. A workflow definition is not a successful run. A checkpoint is not a crown.

## Receipts

A receipt should bind enough identity to replay or falsify the claim: source/tree, planner/policy/role, world/configuration, authority, toolchain/environment, executed transition, verifier, result, and relevant consequence.

Prior verifier evidence is reusable only when source, validator, toolchain, configuration, and environment identities match. Subject standing must still be established for the exact subject.

Historical documents under `archive/markdown/` remain provenance, not present-tense authority.
