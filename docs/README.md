# AutoFDE Lab Documentation

This directory is the **current documentation surface**. The pre-2026-08-13 documentation corpus is preserved under `archive/markdown/docs/` so historical reports, inherited site pages, experiments, and stale architecture remain auditable without competing with current doctrine.

## Read in this order

1. [Architecture](ARCHITECTURE.md)
2. [Planner League](PLANNER_LEAGUE.md)
3. [GymAct](GYMACT.md)
4. [Standing and Evidence](STANDING.md)
5. [Operations](OPERATIONS.md)
6. `../MARKDOWN_DISPOSITION.md` — repository-wide Markdown governance ledger

Root contracts are `README.md`, `PROJECT.md`, `FORWARD_DEPLOYMENT.md`, `CONTRIBUTING.md`, and `CLAUDE.md`.

## Current system

```text
world -> observation -> planner federation -> admission -> intent -> GymAct -> brokered DO -> verification -> receipt -> replay -> standing
```

Historical documents are evidence of prior states. They are not silently upgraded into present-tense proof.
