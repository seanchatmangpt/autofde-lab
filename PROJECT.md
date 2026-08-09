# Project: autofde-lab SOTA Benchmark & Category-B Fault Mechanisms

## Architecture
`autofde-lab` provides deterministic fault detection and remediation modules for Kubernetes microservice environments evaluated on the SREGym benchmark suite.
- **Planner Architecture**: `src/autofde_lab_planner/` (and associated modules) provides candidate generation, decision basis, fault detection heuristics, and deterministic remediations.
- **Environment & Application Helm Charts**: `vendor/gyms/sregym/SREGym-applications/` containing vendored Helm charts for AstronomyShop, FleetCast, TrainTicket, HotelReservation, SocialNetwork, etc.
- **Evaluation Infrastructure**: `vendor/gyms/sregym/sregym/conductor/` and `tests/sota/` for zero-mock testing, problem execution, oracle verification, and benchmark metrics reporting.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | Vendored Helm Charts | Vendor missing `opentelemetry-demo` (astronomy-shop), `FleetCast`, `train-ticket`, and `flight-ticket` Helm charts into `SREGym-applications/` | M1 | ORIGINAL_REQUEST §R2 |
| 2 | Environment Unblocking | Verify all 10 blocked sample problems (and 48 total) deploy without `Helm chart_path does not exist` errors | M1 | ORIGINAL_REQUEST §R2 |
| 3 | Category-B4 Probe Faults | Implement probe misconfiguration detection (readiness/liveness) and spec/probe parameter remediation | M2 | ORIGINAL_REQUEST §R1 |
| 4 | Category-B6 OTel Trace Diffing | Implement Jaeger/OpenTelemetry span tree diffing against baseline to detect broken downstream RPC paths or latency anomalies | M2 | ORIGINAL_REQUEST §R1 |
| 5 | Category-B9 flagd Config Drift | Implement live `flagd` feature flag ConfigMap diffing against public defaults and rollout restart remediator | M2 | ORIGINAL_REQUEST §R1 |
| 6 | Category-B13 Object Reconstruction | Implement missing/corrupted Kubernetes ConfigMaps, Secrets, or Services reconstruction from Helm manifests/baselines | M2 | ORIGINAL_REQUEST §R1 |
| 7 | Zero-Mock Test Suite Verification | Ensure all unit and integration tests in `tests/sota/` pass cleanly with zero mocks (`just test`) | M3 | ORIGINAL_REQUEST §R3 |
| 8 | Systematic Sampling & Evaluation | Execute unbiased systematic sampling across all 123 SREGym problems, verifying Diagnosis >= 75% and Mitigation >= 75% | M3 | ORIGINAL_REQUEST §R3 |
| 9 | Documentation & Raw Artifacts | Generate detailed evaluation breakdown tables and raw TSV outputs in `docs/` and `STATUS.md` | M3 | ORIGINAL_REQUEST §R3 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Resolve Environment Dependencies | Download/vendor missing Helm charts in `SREGym-applications/`, unblock AstronomyShop, FleetCast, TrainTicket | None | DONE |
| M2 | Category-B Fault Mechanisms | Implement B4, B6, B9, B13 detectors & remediators in `src/autofde_lab_planner/` | M1 | IN_PROGRESS |
| M3 | Benchmark Evaluation & Verification | Run zero-mock test suite, execute systematic sampling, achieve >= 75% Diagnosis & Mitigation, write docs/ | M1, M2 | PLANNED |

## Interface Contracts
### Planner ↔ Category-B Detectors & Remediators
- **Detector Input**: `problem_id`, cluster state, OTel trace spans, live ConfigMaps/Secrets/Services, Pod specs/probes.
- **Detector Output**: `DecisionBasis` containing identified root cause fault pattern (`B4`, `B6`, `B9`, `B13`), target resource, and confidence.
- **Remediator Input**: Identified fault pattern, target resource, baseline manifest/config.
- **Remediator Output**: Remediation action (spec patch, rollout undo, ConfigMap apply, secret reconstruction) with execution status.

## Code Layout
- `src/autofde_lab_planner/`: Detector and remediator implementations for Category-B fault mechanisms.
- `vendor/gyms/sregym/SREGym-applications/`: Vendored Helm charts and application definitions.
- `tests/sota/`: Zero-mock integration and unit test suite.
- `docs/`: Evaluation results, per-problem breakdown tables, and raw TSV outputs.
