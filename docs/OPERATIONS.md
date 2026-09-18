# Operations

Use the cheapest high-information verification gate first, then expand only as the claim requires.

```bash
uv sync --extra=all -v
just test
```

Before publishing a broad behavioral change, run the applicable integration/end-to-end checks and, where feasible:

```bash
just test-full
```

## Change flow

```text
orient -> resolve exact base -> read doctrine -> inspect -> admit plan -> implement -> narrow verify -> expand verify -> review -> commit -> draft PR -> exact-head CI -> receipt
```

## Generated artifacts

Locate the canonical graph/template and generation command before editing a suspected projection. If generation cannot execute, classify that edge as blocked instead of hand-editing generated output.

## Failure handling

Preserve failure evidence, locate the failed transition, form a new hypothesis, repair the narrowest cause, add a permanent guard/refusal/fixture where appropriate, and rerun the boundary. Do not rerun an unchanged failure without a new hypothesis.

## Publication boundary

CI supplements local proof; status metadata is not execution evidence. A branch or pull request establishes only the changes and checks actually observed for its exact head.
