import { readFileSync } from "node:fs";
import process from "node:process";

const SCHEMA = "autofde.dspy-wasm.probe.v1";
const DSPY_VERSION = "3.4.0";
const GEPA_VERSION = "0.1.4";
const PYODIDE_VERSION = "314.0.7";
const stages = [];
const hostCounters = { complete: 0, tool: 0, retrieve: 0, observe: 0 };
const hostReceipts = [];

function stage(name, status, detail = {}) {
  stages.push({ name, status, ...detail });
}

function emit(status, { blocker = null, output = {} } = {}) {
  process.stdout.write(
    JSON.stringify({
      schema: SCHEMA,
      status,
      subject: {
        dspy: DSPY_VERSION,
        gepa: GEPA_VERSION,
        pyodide: PYODIDE_VERSION,
        runtime: "node-pyodide",
        profile: "autofde-core-no-provider-io-v1",
        court: "full-capability-matrix",
      },
      stages,
      blocker,
      output,
    }) + "\n",
  );
}

function blocker(code, layer, error) {
  return {
    code,
    layer,
    type: error?.name ?? "Error",
    detail: String(error?.message ?? error),
  };
}

function requireNoActuation(request) {
  if (request.authority?.actuation !== "none") {
    throw new Error("host capability refused non-observational authority");
  }
}

function receipt(capability, request = {}) {
  const r = {
    schema: "autofde.dspy-wasm.host-receipt.v1",
    capability,
    authority: { class: "candidate", actuation: "none" },
    request_model: request.model ?? null,
    ordinal: hostReceipts.length + 1,
  };
  hostReceipts.push(r);
  return r;
}

function completionText(request) {
  const mode = request.mode ?? "predict";
  const ordinal = Number(request.ordinal ?? 1);
  switch (mode) {
    case "predict":
      return JSON.stringify({ output: "WASM-HOST" });
    case "cot":
      return JSON.stringify({ reasoning: "bounded", answer: "42" });
    case "typed":
      return JSON.stringify({ y: 42 });
    case "react":
      if (ordinal === 1) {
        return JSON.stringify({
          next_thought: "use the admitted host tool",
          next_tool_name: "host_add",
          next_tool_args: { x: 2, y: 3 },
        });
      }
      if (ordinal === 2) {
        return JSON.stringify({
          next_thought: "the required observation is available",
          next_tool_name: "finish",
          next_tool_args: {},
        });
      }
      return JSON.stringify({ reasoning: "host tool returned five", answer: "5" });
    case "bootstrap":
      return JSON.stringify({ answer: "OK" });
    case "best_of_n":
      return JSON.stringify({ answer: "BEST" });
    case "two_step_main":
      return "The extracted answer is TWO.";
    case "two_step_extract":
      return "[[ ## answer ## ]]\nTWO\n\n[[ ## completed ## ]]";
    case "async":
      return JSON.stringify({ output: "ASYNC" });
    case "flex":
      return JSON.stringify({ output: "FLEX" });
    case "multi_chain":
      return JSON.stringify({ rationale: "selected", answer: "MC" });
    case "program_of_thought":
      return ordinal === 1
        ? JSON.stringify({ reasoning: "execute bounded expression", generated_code: "'POT'" })
        : JSON.stringify({ reasoning: "extract bounded result", answer: "POT" });
    case "code_act":
      return ordinal === 1
        ? JSON.stringify({ generated_code: "print(local_add(2, 3))", finished: true })
        : JSON.stringify({ reasoning: "extract tool result", answer: "5" });
    case "react_v2":
      return JSON.stringify({
        next_thought: "submit admitted result",
        tool_calls: { tool_calls: [{ name: "submit", args: { answer: "V2" } }] },
      });
    case "rlm":
      return JSON.stringify({
        reasoning: "submit bounded output",
        code: "SUBMIT(output='RLM')",
      });
    case "refine":
      return JSON.stringify({ answer: "REFINE" });
    case "random_search":
      return JSON.stringify({ answer: "RS" });
    case "knn_fewshot":
      return JSON.stringify({ answer: "KNN" });
    case "gepa":
      return JSON.stringify({ answer: "GEPA" });
    case "mipro":
      return JSON.stringify({ answer: "MIPRO" });
    case "copro_prompt":
      return JSON.stringify({
        proposed_instruction: "Return the admitted answer.",
        proposed_prefix_for_output_field: "Answer:",
      });
    case "copro_task":
      return JSON.stringify({ answer: "COPRO" });
    case "infer_rules":
      return JSON.stringify({
        reasoning: "extract concise rule",
        natural_language_rules: "Return the admitted answer.",
      });
    case "infer_task":
      return JSON.stringify({ answer: "RULE" });
    default:
      return JSON.stringify({ answer: "OK", output: "WASM-HOST" });
  }
}

let loadPyodide;
try {
  ({ loadPyodide } = await import("pyodide"));
  stage("host-import", "ALIVE", { package: `pyodide@${PYODIDE_VERSION}` });
} catch (error) {
  stage("host-import", "UNSUPPORTED");
  emit("UNSUPPORTED", {
    blocker: blocker("PYODIDE_NODE_PACKAGE_UNAVAILABLE", "host", error),
  });
  process.exit(0);
}

let pyodide;
try {
  pyodide = await loadPyodide({
    stdout: (message) => process.stderr.write(`${message}\n`),
    stderr: (message) => process.stderr.write(`${message}\n`),
  });
  const runtimeVersion = String(pyodide.version ?? "unknown");
  if (runtimeVersion !== PYODIDE_VERSION) {
    throw new Error(
      `Pyodide runtime drift: expected ${PYODIDE_VERSION}, observed ${runtimeVersion}`,
    );
  }
  stage("pyodide-start", "ALIVE", { version: runtimeVersion });
} catch (error) {
  stage("pyodide-start", "BLOCKED");
  emit("BLOCKED", {
    blocker: blocker("PYODIDE_START_FAILED", "runtime", error),
  });
  process.exit(0);
}

try {
  await pyodide.loadPackage([
    "micropip",
    "numpy",
    "pydantic",
    "regex",
    "jsonschema",
  ]);
  await pyodide.runPythonAsync(`
import micropip

for requirement in [
    "tqdm>=4.66.1",
    "requests>=2.31.0",
    "diskcache>=5.6.0",
    "json-repair>=0.54.2",
    "tenacity>=8.2.3",
    "anyio",
    "cachetools>=5.5.0",
    "cloudpickle>=3.1.2",
]:
    await micropip.install(requirement)

await micropip.install("gepa==${GEPA_VERSION}", deps=False)
await micropip.install("dspy==${DSPY_VERSION}", deps=False)
`);
  stage("dspy-profile-install", "ALIVE", {
    dspy: DSPY_VERSION,
    gepa: GEPA_VERSION,
    excluded: ["litellm", "openai"],
  });
} catch (error) {
  stage("dspy-profile-install", "BLOCKED");
  emit("BLOCKED", {
    blocker: blocker("DSPY_WASM_PROFILE_UNAVAILABLE", "package-resolution", error),
  });
  process.exit(0);
}

try {
  await pyodide.runPythonAsync(`
import json as _json
import sys as _sys
import types as _types

_orjson = _types.ModuleType("orjson")
_orjson.OPT_INDENT_2 = 1
_orjson.OPT_APPEND_NEWLINE = 2
_orjson.OPT_SORT_KEYS = 4
_orjson.JSONEncodeError = TypeError
_orjson.JSONDecodeError = ValueError

def _dumps(value, option=0, default=None):
    kwargs = {"ensure_ascii": False, "allow_nan": False, "default": default}
    if option & _orjson.OPT_SORT_KEYS:
        kwargs["sort_keys"] = True
    if option & _orjson.OPT_INDENT_2:
        kwargs["indent"] = 2
    text = _json.dumps(value, **kwargs)
    if option & _orjson.OPT_APPEND_NEWLINE:
        text += "\\n"
    return text.encode("utf-8")

def _loads(value):
    if isinstance(value, (bytes, bytearray, memoryview)):
        value = bytes(value).decode("utf-8")
    return _json.loads(value)

_orjson.dumps = _dumps
_orjson.loads = _loads
_sys.modules["orjson"] = _orjson
`);
  stage("orjson-compat", "ALIVE", {
    implementation: "stdlib-json",
    surface: ["dumps", "loads", "OPT_INDENT_2", "OPT_APPEND_NEWLINE", "OPT_SORT_KEYS"],
  });
} catch (error) {
  stage("orjson-compat", "BLOCKED");
  emit("BLOCKED", {
    blocker: blocker("ORJSON_COMPAT_INSTALL_FAILED", "compatibility", error),
  });
  process.exit(0);
}

let guest;
try {
  const raw = await pyodide.runPythonAsync(`
import importlib.metadata
import json
import dspy

class WasmEcho(dspy.Module):
    def forward(self, text: str):
        return dspy.Prediction(output=text.upper())

prediction = WasmEcho()(text="wasm")
json.dumps({
    "dspy_version": getattr(dspy, "__version__", "unknown"),
    "gepa_version": importlib.metadata.version("gepa"),
    "module_output": prediction.output,
    "module_type": type(prediction).__name__,
}, sort_keys=True)
`);
  guest = JSON.parse(String(raw));
  if (guest.dspy_version !== DSPY_VERSION) {
    throw new Error(
      `DSPy runtime drift: expected ${DSPY_VERSION}, observed ${guest.dspy_version}`,
    );
  }
  if (guest.gepa_version !== GEPA_VERSION) {
    throw new Error(
      `GEPA runtime drift: expected ${GEPA_VERSION}, observed ${guest.gepa_version}`,
    );
  }
  if (guest.module_output !== "WASM") {
    throw new Error(`deterministic module mismatch: ${guest.module_output}`);
  }
  stage("dspy-import", "ALIVE", { version: guest.dspy_version });
  stage("dspy-module", "ALIVE", { output: guest.module_output });
} catch (error) {
  stage("dspy-module", "BLOCKED");
  emit("BLOCKED", {
    blocker: blocker("DSPY_MODULE_EXECUTION_FAILED", "guest", error),
  });
  process.exit(0);
}

pyodide.registerJsModule("autofde_host", {
  complete: (requestJson) => {
    hostCounters.complete += 1;
    const request = JSON.parse(String(requestJson));
    requireNoActuation(request);
    return JSON.stringify({
      text: completionText(request),
      receipt: receipt("lm.complete", request),
    });
  },
  tool: (requestJson) => {
    hostCounters.tool += 1;
    const request = JSON.parse(String(requestJson));
    requireNoActuation(request);
    if (request.name !== "add") {
      throw new Error(`unsupported host tool: ${request.name}`);
    }
    const result = Number(request.args?.x) + Number(request.args?.y);
    return JSON.stringify({
      result,
      receipt: receipt("tool.add", request),
    });
  },
  retrieve: (requestJson) => {
    hostCounters.retrieve += 1;
    const request = JSON.parse(String(requestJson));
    requireNoActuation(request);
    const k = Number(request.k ?? 3);
    return JSON.stringify({
      passages: Array.from({ length: k }, (_, i) => `${request.query}:${i}`),
      receipt: receipt("retrieve", request),
    });
  },
  observe: (eventJson) => {
    hostCounters.observe += 1;
    const event = JSON.parse(String(eventJson));
    return JSON.stringify({
      accepted: true,
      event,
      receipt: receipt("observe", {}),
    });
  },
});

let hostGuest;
try {
  const raw = await pyodide.runPythonAsync(`
import json
import dspy
from autofde_host import complete as host_complete
from dspy.lm15 import Message, Response, Usage

class HostEngine:
    def complete(self, request):
        envelope = {
            "mode": "predict",
            "ordinal": 1,
            "model": request.model,
            "authority": {"class": "candidate", "actuation": "none"},
            "messages": [
                {"role": message.role, "text": message.text}
                for message in request.messages
            ],
        }
        host = json.loads(str(host_complete(json.dumps(envelope, sort_keys=True))))
        self.last_receipt = host["receipt"]
        return Response(
            id="autofde-host-1",
            model=request.model,
            message=Message.assistant(host["text"]),
            finish_reason="stop",
            usage=Usage(input_tokens=0, output_tokens=0),
            provider_data={"transport": "autofde-host-capability"},
        )

engine = HostEngine()
lm = dspy.LM("autofde/host", engine=engine, cache=False)
dspy.configure(
    lm=lm,
    adapter=dspy.JSONAdapter(use_native_function_calling=False),
)

class HostEcho(dspy.Signature):
    text: str = dspy.InputField()
    output: str = dspy.OutputField()

host_prediction = dspy.Predict(HostEcho)(text="wasm")
json.dumps({
    "host_output": host_prediction.output,
    "host_receipt": engine.last_receipt,
}, sort_keys=True)
`);
  hostGuest = JSON.parse(String(raw));
  if (hostGuest.host_output !== "WASM-HOST") {
    throw new Error(`host engine mismatch: ${hostGuest.host_output}`);
  }
  if (hostGuest.host_receipt?.authority?.actuation !== "none") {
    throw new Error("host receipt lost zero-actuation authority");
  }
  if (hostCounters.complete !== 1) {
    throw new Error(
      `expected one core host capability call, observed ${hostCounters.complete}`,
    );
  }
  stage("dspy-host-engine", "ALIVE", {
    calls: hostCounters.complete,
    output: hostGuest.host_output,
    authority: hostGuest.host_receipt.authority,
  });
} catch (error) {
  stage("dspy-host-engine", "BLOCKED");
  emit("BLOCKED", {
    blocker: blocker("DSPY_HOST_ENGINE_FAILED", "host-capability", error),
  });
  process.exit(0);
}

let capabilityMatrix;
try {
  const source = readFileSync(new URL("./capabilities.py", import.meta.url), "utf8");
  const raw = await pyodide.runPythonAsync(source);
  capabilityMatrix = JSON.parse(String(raw));
  const blocked = capabilityMatrix.summary.blocked;
  stage("dspy-capability-matrix", blocked === 0 ? "ALIVE" : "BLOCKED", {
    total: capabilityMatrix.summary.total,
    alive: capabilityMatrix.summary.alive,
    blocked,
    blocked_names: capabilityMatrix.summary.blocked_names,
  });
  if (blocked !== 0) {
    emit("BLOCKED", {
      blocker: {
        code: "DSPY_CAPABILITY_MATRIX_INCOMPLETE",
        layer: "capability",
        type: "CapabilityMatrix",
        detail: capabilityMatrix.summary.blocked_names.join(", "),
      },
      output: {
        dspy_version: guest.dspy_version,
        gepa_version: guest.gepa_version,
        module_output: guest.module_output,
        host_output: hostGuest.host_output,
        provider_io: false,
        authority: { class: "candidate", actuation: "none" },
        host_counters: hostCounters,
        capabilities: capabilityMatrix,
      },
    });
    process.exit(0);
  }
} catch (error) {
  stage("dspy-capability-matrix", "BLOCKED");
  emit("BLOCKED", {
    blocker: blocker("DSPY_CAPABILITY_MATRIX_FAILED", "capability", error),
    output: {
      dspy_version: guest.dspy_version,
      module_output: guest.module_output,
      provider_io: false,
      authority: { class: "candidate", actuation: "none" },
    },
  });
  process.exit(0);
}

emit("ALIVE", {
  output: {
    dspy_version: guest.dspy_version,
    gepa_version: guest.gepa_version,
    module_output: guest.module_output,
    module_type: guest.module_type,
    host_output: hostGuest.host_output,
    core_host_calls: 1,
    host_receipt: hostGuest.host_receipt,
    host_counters: hostCounters,
    host_receipts: hostReceipts,
    provider_io: false,
    authority: { class: "candidate", actuation: "none" },
    capabilities: capabilityMatrix,
  },
});
