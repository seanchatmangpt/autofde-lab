# A2A no-op decision — REFUSED by evidence

The v26.10.8 card-consolidation wave proposed classifying autofde-lab as a
**documented no-op** ("docs/research lab, no servable agent surface"). That
proposed classification is **false at the current checkout** and is recorded
here as refused, not admitted.

Evidence (re-verified 2026-10-08, this branch):

- `src/autofde_lab/fabric/a2a.py` defines a real A2A v1.0 HTTP server:
  `create_app()` builds a Starlette JSON-RPC app with agent-card routes via
  the `a2a-sdk` server imports; `run()` serves it under uvicorn; `__main__`
  is a runnable entrypoint.
- `src/autofde_lab/fabric/cli.py:289` wires `run` into the CLI.
- `requirements-agentic.txt:5-7` pins `a2a-sdk[http-server]>=1.0.2,<2` and
  `uvicorn>=0.35,<1` — the serving dependencies are declared, not absent.
- `.well-known/agent.json` exists and asserts the card surface.
- `tests/aaif/test_aaif_runtime_court.py` exercises the protocol handler.

autofde-lab is therefore **card-served** (server module + card surface
present and declared servable), not `documented-no-op`. If the intent was
"no card deployed in production today", that is a different, weaker claim
and needs its own evidence; this doc refuses the no-op classification as
stated.
