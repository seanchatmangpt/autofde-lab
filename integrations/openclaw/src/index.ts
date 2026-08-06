import { spawn } from "node:child_process";
import { Type } from "typebox";
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

type PluginConfig = {
  python?: string;
  cwd?: string;
  timeoutMs?: number;
  maxOutputBytes?: number;
};

type BridgeReply = {
  ok: boolean;
  status: string;
  result?: unknown;
  error?: { code: string; message: string };
  receipt: Record<string, unknown>;
};

const Subject = Type.Object(
  {
    name: Type.String({ minLength: 1 }),
    kwargs: Type.Optional(Type.Record(Type.String(), Type.Unknown())),
  },
  { additionalProperties: false },
);

function invokeBridge(config: PluginConfig, tool: string, params: unknown): Promise<BridgeReply> {
  const python = config.python || "python";
  const timeoutMs = config.timeoutMs ?? 120_000;
  const maxOutputBytes = config.maxOutputBytes ?? 4 * 1024 * 1024;
  return new Promise((resolve, reject) => {
    const child = spawn(
      python,
      ["-m", "skdecide.openclaw_bridge", "call", tool, "--arguments", JSON.stringify(params)],
      {
        cwd: config.cwd || undefined,
        env: process.env,
        shell: false,
        stdio: ["ignore", "pipe", "pipe"],
      },
    );
    const stdout: Buffer[] = [];
    const stderr: Buffer[] = [];
    let size = 0;
    let settled = false;
    const finish = (error?: Error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) reject(error);
    };
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      finish(new Error(`scikit-decide bridge exceeded ${timeoutMs}ms`));
    }, timeoutMs);
    const capture = (target: Buffer[], chunk: Buffer) => {
      size += chunk.length;
      if (size > maxOutputBytes) {
        child.kill("SIGKILL");
        finish(new Error(`scikit-decide bridge output exceeded ${maxOutputBytes} bytes`));
        return;
      }
      target.push(chunk);
    };
    child.stdout.on("data", (chunk: Buffer) => capture(stdout, chunk));
    child.stderr.on("data", (chunk: Buffer) => capture(stderr, chunk));
    child.on("error", (error) => finish(error));
    child.on("close", (code) => {
      if (settled) return;
      clearTimeout(timer);
      try {
        const reply = JSON.parse(Buffer.concat(stdout).toString("utf8")) as BridgeReply;
        settled = true;
        resolve(reply);
      } catch (error) {
        finish(
          new Error(
            `scikit-decide bridge returned invalid JSON (exit=${code}): ${Buffer.concat(stderr)
              .toString("utf8")
              .slice(-4000)}`,
            { cause: error },
          ),
        );
      }
    });
  });
}

function toolResult(reply: BridgeReply) {
  return {
    content: [{ type: "text" as const, text: JSON.stringify(reply) }],
    details: reply,
    isError: !reply.ok,
  };
}

export default definePluginEntry({
  id: "scikit-decide",
  name: "scikit-decide",
  description: "Registered planning, scheduling, and reinforcement-learning capabilities",
  register(api) {
    const config = (api.pluginConfig || {}) as PluginConfig;
    api.registerTool({
      name: "skdecide_catalog",
      description: "List registered scikit-decide domains and solvers.",
      parameters: Type.Object(
        {
          kind: Type.Optional(Type.Union([
            Type.Literal("all"),
            Type.Literal("domains"),
            Type.Literal("solvers"),
          ])),
        },
        { additionalProperties: false },
      ),
      async execute(_id, params) {
        return toolResult(await invokeBridge(config, "skdecide_catalog", params));
      },
    });
    api.registerTool({
      name: "skdecide_describe",
      description: "Describe one registered scikit-decide domain or solver.",
      parameters: Type.Object(
        {
          kind: Type.Union([Type.Literal("domain"), Type.Literal("solver")]),
          name: Type.String({ minLength: 1 }),
        },
        { additionalProperties: false },
      ),
      async execute(_id, params) {
        return toolResult(await invokeBridge(config, "skdecide_describe", params));
      },
    });
    api.registerTool(
      {
        name: "skdecide_match",
        description: "Construct a registered domain and list compatible registered solvers.",
        parameters: Type.Object({ domain: Subject }, { additionalProperties: false }),
        async execute(_id, params) {
          return toolResult(await invokeBridge(config, "skdecide_match", params));
        },
      },
      { optional: true },
    );
    api.registerTool(
      {
        name: "skdecide_run",
        description: "Run a bounded scikit-decide rollout using registered subjects only.",
        parameters: Type.Object(
          {
            domain: Subject,
            solver: Type.Optional(Subject),
            solve: Type.Optional(Type.Boolean()),
            rollout: Type.Optional(
              Type.Object(
                {
                  num_episodes: Type.Optional(Type.Integer({ minimum: 1, maximum: 100 })),
                  max_steps: Type.Optional(Type.Integer({ minimum: 1, maximum: 10_000 })),
                },
                { additionalProperties: false },
              ),
            ),
            timeout_seconds: Type.Optional(Type.Number({ exclusiveMinimum: 0, maximum: 600 })),
          },
          { additionalProperties: false },
        ),
        async execute(_id, params) {
          return toolResult(await invokeBridge(config, "skdecide_run", params));
        },
      },
      { optional: true },
    );
  },
});
