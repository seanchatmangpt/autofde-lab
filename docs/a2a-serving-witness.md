# A2A Card-Served Witness

Live execution witness that `create_app()` serves the discoverable Agent Card
over HTTP — the a2a classification is card-served, not code-only.

- Date: 2026-10-08T23:38:44Z
- Subject: `/Users/sac/autofde-lab` @ `c20fc9184240c96ca292878ab264c140c1b6d048` (branch `lane/doc-hdit-scaffold`)
- Surface: `src/autofde_lab/fabric/a2a.py` `create_app()` (a2a-sdk 1.4.1, starlette via a2a-sdk[http-server], uvicorn 0.52.1)
- Server command:

```sh
.venv/bin/python -m uvicorn \
  --app-dir src "autofde_lab.fabric.a2a:create_app" --factory \
  --host 127.0.0.1 --port 8731
```

- Route: `GET /.well-known/agent-card.json` → HTTP 200
  (`/.well-known/agent.json` → 404; a2a-sdk 1.x serves the hyphenated path)
- Deps: already present in `.venv`; no installs performed.

## Served card (verbatim, 200 OK)

```json
{"name":"scikit-decide Decision Fabric","description":"Formal planning and decision intelligence exposed through A2A.","supportedInterfaces":[{"url":"http://127.0.0.1:9999","protocolBinding":"JSONRPC","protocolVersion":"1.0"}],"version":"0.1.0","capabilities":{"streaming":false},"defaultInputModes":["application/json","text/plain"],"defaultOutputModes":["application/json"],"skills":[{"id":"formal_decision","name":"Formal Decision Planning","description":"Match scikit-decide solvers, compute bounded plans or policies, and return receipt-addressed trajectories with ERRC cache evidence.","tags":["planning","scheduling","mdp","pomdp","pddl","ppddl"],"examples":["{\"domain\":\"Maze\",\"solver\":\"Astar\",\"max_steps\":100}","Plan the admitted scheduling job using a compatible solver."],"inputModes":["application/json","text/plain"],"outputModes":["application/json"]}]}
```

## Key

- name: `scikit-decide Decision Fabric`
- version: `0.1.0`
- skills: 1 — `formal_decision` ("Formal Decision Planning")
