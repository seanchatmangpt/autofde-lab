"""JSON-in/JSON-out CLI over store/staged/align. stdout is always one JSON document.
Usage: python3 -m enterprise_pipeline.store_cli <append|reduce|events|taxonomy|plan|settle|dispatch>
Honors PLAN_STORE and PLAN_CLOCK_NOW (read by store). Refusals: {"refused": ...} and exit 2."""
import fcntl
import json
import os
import sys

from enterprise_pipeline import align, staged, store

TAXONOMY_TYPES = ("doc_slot", "media_artifact", "taxonomy", "client", "provider")


class _Refuse(Exception):
    pass


def _emit(obj, rc=0):
    sys.stdout.write(json.dumps(obj, sort_keys=True, default=str) + "\n")
    sys.stdout.flush()
    return rc


MAX_STDIN = 1 << 20  # 1 MiB cap on a request document


def _stdin():
    raw = sys.stdin.read(MAX_STDIN + 1)
    if len(raw) > MAX_STDIN:
        raise _Refuse(f"REFUSED[TooLarge: stdin exceeds {MAX_STDIN} bytes]")
    try:
        d = json.loads(raw) if raw.strip() else {}
    except ValueError as e:
        raise _Refuse(f"REFUSED[JSONDecodeError: {e}]")
    if not isinstance(d, dict):
        raise _Refuse("REFUSED[TypeError: stdin must be a JSON object]")
    return d


def _req(d, *keys):
    for k in keys:
        if d.get(k) in (None, ""):
            raise _Refuse(f"MISSING[{k}]")
    return [d[k] for k in keys]


def _heal_torn_tail():
    """Under the lock: drop a final line that has no newline and does not parse (a torn write)."""
    p = store.store_path()
    if not p.exists():
        return
    data = p.read_bytes()
    if not data or data.endswith(b"\n"):
        return
    cut = data.rfind(b"\n") + 1
    try:
        json.loads(data[cut:])
        p.write_bytes(data + b"\n")  # complete record missing only its newline
    except ValueError:
        p.write_bytes(data[:cut])


def _read():
    try:
        return store.read()
    except ValueError as e:
        lines = store.store_path().read_text().splitlines()
        for n, l in enumerate(lines, 1):
            if l.strip():
                try:
                    json.loads(l)
                except ValueError:
                    raise _Refuse(f"REFUSED[CORRUPT_STORE: line {n}: {e}]")
        raise _Refuse(f"REFUSED[CORRUPT_STORE: {e}]")


def _cur():
    return store.reduce(_read())


def _wo_exists(state, wo_id):
    if not any(w["id"] == wo_id for w in state["work_orders"]):
        raise _Refuse(f"UNKNOWN[wo {wo_id}]")


def _observe(obs):
    """Append the observation as console.py does; Refused surfaces as a typed refusal."""
    if obs:
        return store.append("system", *obs)
    return None


def cmd_append():
    d = _stdin()
    avatar, kind = _req(d, "avatar", "kind")
    payload = d.get("payload") or {}
    if not isinstance(payload, dict):
        raise _Refuse("REFUSED[TypeError: payload must be a JSON object]")
    payload = {k: v for k, v in payload.items() if v not in (None, "", [])}
    return _emit(store.append(avatar, kind, payload))


def cmd_reduce():
    return _emit(_cur())


def cmd_events():
    return _emit(_read())


def cmd_taxonomy():
    return _emit({"subtypes": {t: store.subtypes(t) for t in TAXONOMY_TYPES},
                  "constants": {"delivery_channel": store.domain_constants("delivery_channel")},
                  "dims": align.DIMS})


def cmd_plan():
    (wo_id,) = _req(_stdin(), "wo_id")
    state = _cur()
    _wo_exists(state, wo_id)
    r = staged.plan_wo(state, wo_id)
    obs = staged.observe_plan(state, wo_id, r)
    try:
        ev, oref = _observe(obs), None
    except store.Refused as e:  # keep the planner result; report the observation refusal beside it
        ev, oref = None, str(e)
    return _emit({**r, "observed": ev, **({"observe_refused": oref} if oref else {})})


def cmd_settle():
    (wo_id,) = _req(_stdin(), "wo_id")
    state = _cur()
    _wo_exists(state, wo_id)
    rc, out = staged.settle(state, wo_id)
    if rc != 0:
        first = out.splitlines()[0] if out else ""
        try:
            j = json.loads(first)
        except ValueError:
            j = None
        if isinstance(j, dict) and "refused" in j:  # NteCapError / MarginGuardError pass through typed
            return _emit({"refused": j["refused"], "detail": j.get("detail"), "rc": rc, "out": out}, 2)
        return _emit({"refused": out, "rc": rc, "out": out}, 2)
    try:
        ev, oref = _observe(staged.observe_settle(wo_id, rc, out)), None
    except store.Refused as e:
        ev, oref = None, str(e)
    return _emit({"rc": rc, "out": out, "ledger": json.loads(out.splitlines()[0]), "observed": ev,
                  **({"observe_refused": oref} if oref else {})})


def cmd_dispatch():
    d = _stdin()
    wo_id, prov_id = _req(d, "wo_id", "provider")
    state = _cur()
    wo = next((w for w in state["work_orders"] if w["id"] == wo_id), None)
    if wo is None:
        raise _Refuse(f"UNKNOWN[wo {wo_id}]")
    usable = [p for p in state["providers"] if not staged._provider_gap(p)]
    elig, _ = staged.eligibility(state, wo, usable)
    if not elig.get(prov_id):
        return _emit({"refused": f"REFUSED[not eligible: {prov_id}]", "eligibility": elig}, 2)
    return _emit(store.append("coord", "dispatch", {"wo": wo_id, "provider": prov_id}))


CMDS = {"append": cmd_append, "reduce": cmd_reduce, "events": cmd_events, "taxonomy": cmd_taxonomy, "plan": cmd_plan,
        "settle": cmd_settle, "dispatch": cmd_dispatch}


MUTATING = ("append", "plan", "settle", "dispatch", "reduce", "events")  # lock + heal torn tail


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1 or argv[0] not in CMDS:
        return _emit({"refused": f"USAGE[{'|'.join(CMDS)}]"}, 2)
    try:
        if argv[0] in MUTATING:
            p = store.store_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(str(p) + ".lock", "a") as lk:
                fcntl.flock(lk, fcntl.LOCK_EX)  # serialize read-reduce-check-write across processes
                _heal_torn_tail()
                return CMDS[argv[0]]()
        return CMDS[argv[0]]()
    except BrokenPipeError:
        sys.stdout = open(os.devnull, "w")
        return 0
    except store.Refused as e:
        return _emit({"refused": str(e)}, 2)
    except _Refuse as e:
        return _emit({"refused": str(e)}, 2)
    except (ValueError, KeyError, StopIteration, TypeError, AttributeError) as e:
        return _emit({"refused": f"REFUSED[{type(e).__name__}: {e}]"}, 2)


if __name__ == "__main__":
    raise SystemExit(main())
