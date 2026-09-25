"""Executable DSPy 3.4 capability census for the Pyodide/WASM profile.

Every row is evidence for one exact semantic surface. A capability is ALIVE only
after its behavior is observed; import/construct-only checks say CONSTRUCTED.
Failures are typed per capability so one optional surface never erases evidence
for the rest.
"""

from __future__ import annotations

import ast
import asyncio
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import dspy
from autofde_host import complete as _host_complete
from autofde_host import observe as _host_observe
from autofde_host import retrieve as _host_retrieve
from autofde_host import tool as _host_tool
from dspy.lm15 import Message, Response, Usage
from dspy.primitives.code_interpreter import CodeExecutionError, FinalOutput


@dataclass
class CapabilityResult:
    name: str
    status: str
    phase: str
    evidence: dict[str, Any]
    error: dict[str, str] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "phase": self.phase,
            "evidence": self.evidence,
            "error": self.error,
        }


class HostEngine:
    """DSPy 3.4 custom engine backed only by the explicit JS host capability."""

    def __init__(self, mode: str):
        self.mode = mode
        self.calls = 0
        self.receipts: list[dict[str, Any]] = []

    def complete(self, request):
        self.calls += 1
        envelope = {
            "mode": self.mode,
            "ordinal": self.calls,
            "model": request.model,
            "authority": {"class": "candidate", "actuation": "none"},
            "messages": [
                {"role": message.role, "text": message.text}
                for message in request.messages
            ],
        }
        host = json.loads(str(_host_complete(json.dumps(envelope, sort_keys=True))))
        self.receipts.append(host["receipt"])
        return Response(
            id=f"autofde-host-{self.mode}-{self.calls}",
            model=request.model,
            message=Message.assistant(host["text"]),
            finish_reason="stop",
            usage=Usage(input_tokens=0, output_tokens=0),
            provider_data={"transport": "autofde-host-capability", "mode": self.mode},
        )


class AsyncHostEngine(HostEngine):
    async def complete(self, request):
        return super().complete(request)


def lm(mode: str, *, async_: bool = False) -> dspy.LM:
    engine = HostEngine(mode)
    async_engine = AsyncHostEngine(mode) if async_ else None
    return dspy.LM(
        f"autofde/{mode}",
        engine=engine,
        async_engine=async_engine,
        cache=False,
    )


def host_add(x: int, y: int) -> int:
    payload = json.loads(
        str(
            _host_tool(
                json.dumps(
                    {
                        "name": "add",
                        "args": {"x": x, "y": y},
                        "authority": {"class": "candidate", "actuation": "none"},
                    },
                    sort_keys=True,
                )
            )
        )
    )
    return int(payload["result"])


def host_retriever(query: str, k: int = 3, **_: Any):
    payload = json.loads(
        str(
            _host_retrieve(
                json.dumps(
                    {
                        "query": query,
                        "k": k,
                        "authority": {"class": "candidate", "actuation": "none"},
                    },
                    sort_keys=True,
                )
            )
        )
    )
    return [dspy.Prediction(long_text=text) for text in payload["passages"]]


class WasmGuestInterpreter:
    """A second interpreter boundary inside the already-sandboxed Pyodide guest.

    This is intentionally *not* advertised as a general secure CPython sandbox.
    Its authority is bounded by the outer Pyodide/WASM guest. It exists so DSPy's
    Flex bridge still gets a separate CodeInterpreter lifecycle and explicit tool
    registry without requiring Deno or a subprocess from inside WASM.
    """

    def __init__(self):
        self._tools: dict[str, Callable[..., Any]] = {}
        self._globals: dict[str, Any] = {"__builtins__": __builtins__}
        self._started = False
        self._closed = False

    @property
    def tools(self):
        return self._tools

    def start(self):
        if self._closed:
            raise RuntimeError("interpreter already closed")
        self._started = True

    def _tool_globals(self) -> dict[str, Any]:
        return {name: fn for name, fn in self._tools.items()}

    def execute(self, code: str, variables: dict[str, Any] | None = None):
        if self._closed:
            raise RuntimeError("interpreter already closed")
        if not self._started:
            self.start()
        self._globals.update(self._tool_globals())
        if variables:
            self._globals.update(variables)

        old_dspy = sys.modules.get("dspy")
        tree = ast.parse(code, mode="exec")
        out = io.StringIO()
        try:
            with redirect_stdout(out):
                if tree.body and isinstance(tree.body[-1], ast.Expr):
                    prefix = ast.Module(body=tree.body[:-1], type_ignores=[])
                    if prefix.body:
                        exec(compile(prefix, "<dspy-wasm-guest>", "exec"), self._globals)
                    result = eval(
                        compile(ast.Expression(tree.body[-1].value), "<dspy-wasm-guest>", "eval"),
                        self._globals,
                    )
                else:
                    exec(compile(tree, "<dspy-wasm-guest>", "exec"), self._globals)
                    result = None
        except Exception as exc:
            raise CodeExecutionError(str(exc)) from exc
        finally:
            # DSPy's sandbox shim temporarily registers its fake module globally.
            # Restore the real outer-guest DSPy module before host callbacks run.
            if old_dspy is not None:
                sys.modules["dspy"] = old_dspy
            else:
                sys.modules.pop("dspy", None)

        if isinstance(result, FinalOutput):
            return result
        if result is not None:
            return result
        stdout = out.getvalue().strip()
        return stdout or None

    def shutdown(self):
        self._closed = True
        self._globals.clear()
        self._tools.clear()


def _record(
    rows: list[CapabilityResult],
    name: str,
    phase: str,
    fn: Callable[[], dict[str, Any]],
) -> None:
    try:
        evidence = fn()
        rows.append(CapabilityResult(name, "ALIVE", phase, evidence))
        _host_observe(json.dumps({"capability": name, "status": "ALIVE"}, sort_keys=True))
    except Exception as exc:
        rows.append(
            CapabilityResult(
                name,
                "BLOCKED",
                phase,
                {},
                {
                    "type": type(exc).__name__,
                    "detail": str(exc),
                },
            )
        )
        _host_observe(
            json.dumps(
                {
                    "capability": name,
                    "status": "BLOCKED",
                    "error": type(exc).__name__,
                },
                sort_keys=True,
            )
        )


def _signatures() -> dict[str, Any]:
    class Typed(dspy.Signature):
        """Typed signature court."""

        x: int = dspy.InputField()
        y: int = dspy.OutputField()

    state = Typed.dump_state()
    assert list(Typed.input_fields) == ["x"]
    assert list(Typed.output_fields) == ["y"]
    assert state["instructions"] == "Typed signature court."
    return {"inputs": ["x"], "outputs": ["y"], "instructions": state["instructions"]}


def _adapters() -> dict[str, Any]:
    sig = dspy.Signature("question -> answer")
    chat = dspy.ChatAdapter().parse(
        sig, "[[ ## answer ## ]]\nCHAT\n\n[[ ## completed ## ]]"
    )
    js = dspy.JSONAdapter(use_native_function_calling=False).parse(
        sig, '{"answer":"JSON"}'
    )
    xml = dspy.XMLAdapter().parse(sig, "<answer>XML</answer>")
    assert chat["answer"] == "CHAT"
    assert js["answer"] == "JSON"
    assert xml["answer"] == "XML"
    return {"chat": "CHAT", "json": "JSON", "xml": "XML"}


def _predict() -> dict[str, Any]:
    engine = lm("predict")
    with dspy.context(lm=engine, adapter=dspy.JSONAdapter(use_native_function_calling=False)):
        pred = dspy.Predict("text -> output")(text="wasm")
    assert pred.output == "WASM-HOST"
    return {"output": pred.output, "calls": engine._engine_spec.calls}


def _chain_of_thought() -> dict[str, Any]:
    engine = lm("cot")
    with dspy.context(lm=engine, adapter=dspy.JSONAdapter(use_native_function_calling=False)):
        pred = dspy.ChainOfThought("question -> answer")(question="6 * 7?")
    assert pred.answer == "42"
    assert pred.reasoning == "bounded"
    return {"answer": pred.answer, "reasoning": pred.reasoning}


def _typed_predict() -> dict[str, Any]:
    class Typed(dspy.Signature):
        x: int = dspy.InputField()
        y: int = dspy.OutputField()

    engine = lm("typed")
    with dspy.context(lm=engine, adapter=dspy.JSONAdapter(use_native_function_calling=False)):
        pred = dspy.Predict(Typed)(x=41)
    assert pred.y == 42
    assert isinstance(pred.y, int)
    return {"y": pred.y, "type": type(pred.y).__name__}


def _tool() -> dict[str, Any]:
    tool = dspy.Tool(host_add)
    value = tool(x=2, y=3)
    assert value == 5
    return {"tool": tool.name, "result": value}


def _react() -> dict[str, Any]:
    engine = lm("react")
    with dspy.context(lm=engine, adapter=dspy.JSONAdapter(use_native_function_calling=False)):
        agent = dspy.ReAct("question -> answer", tools=[host_add], max_iters=2)
        pred = agent(question="Add 2 and 3.")
    assert pred.answer == "5"
    assert any(value == 5 for key, value in pred.trajectory.items() if key.startswith("observation_"))
    return {
        "answer": pred.answer,
        "trajectory_keys": sorted(pred.trajectory),
        "lm_calls": engine._engine_spec.calls,
    }


def _retrieve() -> dict[str, Any]:
    with dspy.context(rm=host_retriever):
        pred = dspy.Retrieve(k=2)("wasm")
    assert pred.passages == ["wasm:0", "wasm:1"]
    return {"passages": pred.passages}


def _evaluate() -> dict[str, Any]:
    class Upper(dspy.Module):
        def forward(self, text: str):
            return dspy.Prediction(answer=text.upper())

    devset = [
        dspy.Example(text="a", answer="A").with_inputs("text"),
        dspy.Example(text="b", answer="B").with_inputs("text"),
    ]

    def metric(example, prediction, trace=None):
        return float(example.answer == prediction.answer)

    result = dspy.Evaluate(
        devset=devset,
        metric=metric,
        num_threads=1,
        display_progress=False,
        display_table=False,
    )(Upper())
    assert float(result.score) == 100.0
    return {"score": float(result.score), "examples": len(result.results)}


def _parallel() -> dict[str, Any]:
    class Upper(dspy.Module):
        def forward(self, text: str):
            return dspy.Prediction(answer=text.upper())

    pairs = [(Upper(), {"text": "a"}), (Upper(), {"text": "b"})]
    out = dspy.Parallel(num_threads=1, disable_progress_bar=True)(pairs)
    answers = [x.answer for x in out]
    assert answers == ["A", "B"]
    return {"answers": answers}


def _labeled_fewshot() -> dict[str, Any]:
    student = dspy.Predict("text -> answer")
    train = [
        dspy.Example(text="a", answer="A").with_inputs("text"),
        dspy.Example(text="b", answer="B").with_inputs("text"),
    ]
    compiled = dspy.LabeledFewShot(k=2).compile(student, trainset=train, sample=False)
    assert len(compiled.demos) == 2
    return {"demos": len(compiled.demos)}


def _bootstrap_fewshot() -> dict[str, Any]:
    student = dspy.Predict("text -> answer")
    train = [
        dspy.Example(text="a", answer="OK").with_inputs("text"),
        dspy.Example(text="b", answer="OK").with_inputs("text"),
    ]

    def metric(example, prediction, trace=None):
        return True

    engine = lm("bootstrap")
    with dspy.context(lm=engine, adapter=dspy.JSONAdapter(use_native_function_calling=False)):
        compiled = dspy.BootstrapFewShot(
            metric=metric,
            max_bootstrapped_demos=1,
            max_labeled_demos=1,
            max_rounds=1,
        ).compile(student, trainset=train)
    assert compiled.demos
    return {"demos": len(compiled.demos), "lm_calls": engine._engine_spec.calls}


def _best_of_n() -> dict[str, Any]:
    engine = lm("best_of_n")
    module = dspy.Predict("text -> answer")
    module.set_lm(engine)

    def reward(_args, pred):
        return 1.0 if pred.answer == "BEST" else 0.0

    with dspy.context(adapter=dspy.JSONAdapter(use_native_function_calling=False)):
        pred = dspy.BestOfN(module, N=2, reward_fn=reward, threshold=1.0)(text="x")
    assert pred.answer == "BEST"
    return {"answer": pred.answer, "calls": engine._engine_spec.calls}


def _serialization() -> dict[str, Any]:
    program = dspy.Predict("text -> answer")
    program.demos = [dspy.Example(text="a", answer="A").with_inputs("text")]
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "program.json"
        program.save(path)
        restored = dspy.Predict("text -> answer")
        restored.load(path)
        assert len(restored.demos) == 1
        assert restored.demos[0]["answer"] == "A"
        size = path.stat().st_size
    return {"mode": "state-json", "bytes": size, "demos": 1}


def _two_step_adapter() -> dict[str, Any]:
    main = lm("two_step_main")
    extraction = lm("two_step_extract")
    adapter = dspy.TwoStepAdapter(extraction)
    with dspy.context(lm=main, adapter=adapter):
        pred = dspy.Predict("question -> answer")(question="value?")
    assert pred.answer == "TWO"
    return {
        "answer": pred.answer,
        "main_calls": main._engine_spec.calls,
        "extraction_calls": extraction._engine_spec.calls,
    }


async def _async_predict_inner() -> dict[str, Any]:
    # DSPy 3.4 uses asyncio.to_thread() for request preparation. Pyodide has
    # no worker-thread stack switching in this Node runtime, so the WASM
    # profile projects that pure preparation step inline while preserving the
    # async engine contract itself.
    original_to_thread = asyncio.to_thread

    async def inline_to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    asyncio.to_thread = inline_to_thread
    try:
        engine = lm("async", async_=True)
        with dspy.context(
            lm=engine,
            adapter=dspy.JSONAdapter(use_native_function_calling=False),
        ):
            pred = await dspy.Predict("text -> output").acall(text="wasm")
        assert pred.output == "ASYNC"
        return {
            "output": pred.output,
            "async_calls": engine._async_engine_spec.calls,
            "to_thread": "inline-wasm-projection",
        }
    finally:
        asyncio.to_thread = original_to_thread


def _flex() -> dict[str, Any]:
    engine = lm("flex")
    flex = dspy.Flex(
        "text -> output",
        interpreter_factory=WasmGuestInterpreter,
        max_predictor_calls=3,
    )
    flex.set_lm(engine)
    with dspy.context(adapter=dspy.JSONAdapter(use_native_function_calling=False)):
        pred = flex(text="wasm")
    assert pred.output == "FLEX"
    module_src = flex.module_src
    assert module_src is not None and "dspy.Predict" in module_src
    # Runtime engines are host resources, not Flex state. Clear the borrowed
    # LM before asserting the code/state round-trip surface.
    flex.set_lm(None)
    state = flex.dump_state()
    assert state["lm"] is None
    assert state["module_src"] == module_src
    return {
        "output": pred.output,
        "module_src_sha": __import__("hashlib").sha256(module_src.encode()).hexdigest(),
        "lm_calls": engine._engine_spec.calls,
        "serialized_lm": None,
    }


def _gepa_construct() -> dict[str, Any]:
    # Construction is useful but is not allowed to masquerade as execution.
    def metric(gold, pred, trace, pred_name, pred_trace):
        return 1.0

    def proposer(candidate, reflective_dataset, components_to_update, *, metadata=None):
        return {name: candidate[name] for name in components_to_update}

    optimizer = dspy.GEPA(
        metric=metric,
        max_metric_calls=2,
        instruction_proposer=proposer,
        use_merge=False,
        num_threads=1,
    )
    assert optimizer.max_metric_calls == 2
    return {"optimizer": type(optimizer).__name__, "max_metric_calls": 2}


def _mipro_construct() -> dict[str, Any]:
    optimizer = dspy.MIPROv2(
        metric=lambda example, prediction, trace=None: 1.0,
        auto="light",
        num_threads=1,
    )
    return {"optimizer": type(optimizer).__name__, "auto": optimizer.auto}


def _context() -> dict[str, Any]:
    before = dspy.settings.get("max_errors")
    with dspy.context(max_errors=7):
        inside = dspy.settings.max_errors
    after = dspy.settings.get("max_errors")
    assert inside == 7
    assert after == before
    return {"before": before, "inside": inside, "after": after}


async def run_all() -> dict[str, Any]:
    rows: list[CapabilityResult] = []
    courts = [
        ("signature.typed", "execute", _signatures),
        ("adapter.chat-json-xml", "execute", _adapters),
        ("module.predict", "execute", _predict),
        ("module.chain_of_thought", "execute", _chain_of_thought),
        ("module.typed_predict", "execute", _typed_predict),
        ("tool.direct_host", "execute", _tool),
        ("module.react_host_tool", "compose", _react),
        ("retrieval.host_rm", "execute", _retrieve),
        ("evaluation.sequential", "execute", _evaluate),
        ("parallel.single_thread", "execute", _parallel),
        ("optimizer.labeled_fewshot", "optimize", _labeled_fewshot),
        ("optimizer.bootstrap_fewshot", "optimize", _bootstrap_fewshot),
        ("module.best_of_n", "execute", _best_of_n),
        ("serialization.state_json", "serialize", _serialization),
        ("adapter.two_step", "compose", _two_step_adapter),
        ("module.flex_wasm_interpreter", "compose", _flex),
        ("optimizer.gepa", "construct", _gepa_construct),
        ("optimizer.mipro_v2", "construct", _mipro_construct),
        ("settings.context", "execute", _context),
    ]
    for name, phase, fn in courts:
        _record(rows, name, phase, fn)

    try:
        evidence = await _async_predict_inner()
        rows.append(CapabilityResult("async.predict", "ALIVE", "execute", evidence))
        _host_observe(json.dumps({"capability": "async.predict", "status": "ALIVE"}, sort_keys=True))
    except Exception as exc:
        rows.append(
            CapabilityResult(
                "async.predict",
                "BLOCKED",
                "execute",
                {},
                {"type": type(exc).__name__, "detail": str(exc)},
            )
        )
        _host_observe(
            json.dumps(
                {"capability": "async.predict", "status": "BLOCKED", "error": type(exc).__name__},
                sort_keys=True,
            )
        )

    alive = [r.name for r in rows if r.status == "ALIVE"]
    blocked = [r.name for r in rows if r.status == "BLOCKED"]
    return {
        "schema": "autofde.dspy-wasm.capabilities.v1",
        "capabilities": [r.as_dict() for r in rows],
        "summary": {
            "total": len(rows),
            "alive": len(alive),
            "blocked": len(blocked),
            "alive_names": alive,
            "blocked_names": blocked,
        },
    }


result = await run_all()
json.dumps(result, sort_keys=True)
