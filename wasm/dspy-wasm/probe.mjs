import process from "node:process";

const SCHEMA = "autofde.dspy-wasm.probe.v1";
const DSPY_VERSION = "3.4.0";
const PYODIDE_VERSION = "314.0.7";
const stages = [];

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
        pyodide: PYODIDE_VERSION,
        runtime: "node-pyodide",
        court: "import+deterministic-module",
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
  pyodide = await loadPyodide();
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
  await pyodide.loadPackage("micropip");
  await pyodide.runPythonAsync(`
import micropip
await micropip.install("dspy==${DSPY_VERSION}", keep_going=True)
`);
  stage("dspy-install", "ALIVE", { package: `dspy==${DSPY_VERSION}` });
} catch (error) {
  stage("dspy-install", "BLOCKED");
  emit("BLOCKED", {
    blocker: blocker("DSPY_DEPENDENCY_CLOSURE_UNAVAILABLE", "package-resolution", error),
  });
  process.exit(0);
}

let guest;
try {
  const raw = await pyodide.runPythonAsync(`
import json
import dspy

class WasmEcho(dspy.Module):
    def forward(self, text: str):
        return dspy.Prediction(output=text.upper())

prediction = WasmEcho()(text="wasm")
json.dumps({
    "dspy_version": getattr(dspy, "__version__", "unknown"),
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

emit("ALIVE", {
  output: {
    dspy_version: guest.dspy_version,
    module_output: guest.module_output,
    module_type: guest.module_type,
    lm_calls: 0,
    authority: { class: "candidate", actuation: "none" },
  },
});
