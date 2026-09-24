"""IEC executed crowns (v26.9.23): run C1 and C3 against real, exact subjects.

The execution layer beside the IEC architecture package (`autofde_lab.iec`):
where that package defines contracts, courts and projections, this subpackage
runs the crowns against pinned sibling checkouts and emits byte-replayable
receipts under `receipts/v26.9.23/iec/`. Doctrine: `CLAUDE.md` here.

Stdlib-only except `kernel` (rdflib). Modules, in pipeline order: `model`, `corpus`,
`census`, `generators`, `templates`, `kernel`, `antiunify`, `decompile`, `reflexion`,
`court`, `federation`, `crown` (IEC-C1), `audit`, `retirement`, `c3` (IEC-C3).
"""
