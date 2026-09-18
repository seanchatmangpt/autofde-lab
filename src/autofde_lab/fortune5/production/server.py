"""Zero-dependency HTTP + HTML dashboard for the Fortune-5 simulation."""

from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .service import SimulationService

_DASHBOARD = """<!doctype html>
<meta charset="utf-8">
<title>Fortune-5 Semantic A2A Production Simulation</title>
<style>
body{font:14px system-ui;margin:2rem;max-width:1100px}button{padding:.6rem 1rem}
pre{background:#111;color:#ddd;padding:1rem;overflow:auto}input,select{padding:.4rem}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem}.card{border:1px solid #ccc;padding:1rem}
</style>
<h1>Fortune-5 Semantic A2A Production Simulation</h1>
<p>Simulation only. No real infrastructure authority or actuation.</p>
<div>
Seed <input id="seed" value="1" size="5">
Rounds <input id="rounds" value="40" size="5">
Scale <select id="scale"><option>demo</option><option>enterprise</option><option selected>fortune5</option></select>
<button onclick="run()">Run</button>
</div>
<div id="cards" class="grid"></div>
<pre id="out">Ready.</pre>
<script>
async function run(){
 const body={seed:+seed.value,rounds:+rounds.value,scale_profile:scale.value};
 const r=await fetch('/api/v1/simulations',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)});
 const j=await r.json(); out.textContent=JSON.stringify(j,null,2);
 const s=j.summary||{}, w=j.world||{};
 cards.innerHTML=[
  ['Services',w.services],['Regions',w.regions],['Actuations',s.actuations],
  ['Frontier calls',s.frontier_invocations],['Known hits',s.known_route_hits],
  ['Unreceipted',s.unreconciled_actuations],['Authority violations',s.authority_violations],
  ['Standing',s.readiness_standing]
 ].map(x=>`<div class=card><b>${x[0]}</b><div>${x[1]}</div></div>`).join('');
}
</script>"""


def make_handler(service: SimulationService):
    class Handler(BaseHTTPRequestHandler):
        server_version = "Fortune5SA2A/26.9.18"

        def _json(self, payload: object, status: int = 200) -> None:
            raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
            self.send_response(status)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/":
                raw = _DASHBOARD.encode()
                self.send_response(HTTPStatus.OK)
                self.send_header("content-type", "text/html; charset=utf-8")
                self.send_header("content-length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if path == "/health":
                self._json({"status": "ok", "surface": "simulation-only"})
                return
            if path == "/api/v1/simulations":
                self._json({"runs": service.list()})
                return
            parts = [part for part in path.split("/") if part]
            if len(parts) >= 4 and parts[:3] == ["api", "v1", "simulations"]:
                run_id = parts[3]
                try:
                    view = service.get(run_id)
                except KeyError:
                    self._json({"error": "not_found", "run_id": run_id}, 404)
                    return
                if len(parts) == 4:
                    self._json(view.summary())
                elif len(parts) == 5 and parts[4] == "ocel":
                    self._json(view.ocel())
                elif len(parts) == 5 and parts[4] == "formal":
                    self._json(view.run.projection.canonical())
                else:
                    self._json({"error": "not_found"}, 404)
                return
            self._json({"error": "not_found"}, 404)

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path != "/api/v1/simulations":
                self._json({"error": "not_found"}, 404)
                return
            try:
                length = int(self.headers.get("content-length", "0"))
                payload = json.loads(self.rfile.read(length) or b"{}")
                view = service.start(
                    seed=int(payload.get("seed", 1)),
                    rounds=int(payload.get("rounds", 40)),
                    scale_profile=str(payload.get("scale_profile", "fortune5")),
                    scenario_choices=payload.get("scenario_choices") or {},
                    fault_density=float(payload.get("fault_density", 0.12)),
                )
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                self._json({"error": "invalid_request", "detail": str(exc)}, 400)
                return
            self._json(view.summary(), 201)

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def serve(host: str = "127.0.0.1", port: int = 8080) -> None:
    service = SimulationService()
    httpd = ThreadingHTTPServer((host, port), make_handler(service))
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()


__all__ = ["make_handler", "serve"]
