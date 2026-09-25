import process from "node:process";

const SCHEMA = "autofde.dspy-wasm.probe.v1";
const DSPY_VERSION = "3.4.0";
const GEPA_VERSION = "0.1.4";
const PYODIDE_VERSION = "314.0.7";
const stages = [];
let hostCalls = 0;

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
        court: "import+deterministic-module+host-engine",
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
  await pyodide.loadPackage(["micropip", "numpy", "pydantic", "regex"]);
  await pyodide.runPythonAsync(`
import micropip

# The WASM profile intentionally excludes DSPy's ambient provider stack
# (LiteLLM/OpenAI) and installs only the surfaces needed by the admitted court.
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

# GEPA 0.1.4's base package has no mandatory dependencies. DSPy declares the
# empty [dspy] extra; dependency expansion is deliberately disabled here so
# provider-only packages cannot acquire ambient guest authority.
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

# DSPy 3.4.0 hard-imports orjson on serialization/cache paths. Pyodide does
# not ship an orjson wheel, so provide the exact tiny surface DSPy references
# in this release. This is a host compatibility projection, not a DSPy fork.
_orjson = _types.ModuleType("orjson")
_orjson.OPT_INDENT_2 = 1
_orjson.OPT_APPEND_NEWLINE = 2
_orjson.OPT_SORT_KEYS = 4
_orjson.JSONEncodeError = TypeError
_orjson.JSONDecodeError = ValueError

def _dumps(value, option=0, default=None):
    kwargs = {
        "ensure_ascii": False,
        "allow_nan": False,
        "default": default,
    }
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
    hostCalls += 1;
    const request = JSON.parse(String(requestJson));
    if (request.authority?.actuation !== "none") {
      throw new Error("host capability refused non-observational authority");
    }
    return JSON.stringify({
      text: JSON.stringify({ output: "WASM-HOST" }),
      receipt: {
        schema: "autofde.dspy-wasm.host-receipt.v1",
        capability: "lm.complete",
        authority: { class: "candidate", actuation: "none" },
        request_model: request.model,
      },
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
            "model": request.model,
            "authority": {"class": "candidate", "actuation": "none"},
            "messages": [
                {
                    "role": message.role,
                    "text": message.text,
                }
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
  if (hostCalls !== 1) {
    throw new Error(`expected one host capability call, observed ${hostCalls}`);
  }
  stage("dspy-host-engine", "ALIVE", {
    calls: hostCalls,
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

emit("ALIVE", {
  output: {
    dspy_version: guest.dspy_version,
    gepa_version: guest.gepa_version,
    module_output: guest.module_output,
    module_type: guest.module_type,
    lm_calls: 1,
    host_output: hostGuest.host_output,
    host_calls: hostCalls,
    host_receipt: hostGuest.host_receipt,
    provider_io: false,
    authority: { class: "candidate", actuation: "none" },
  },
});
