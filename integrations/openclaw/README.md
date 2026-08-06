# scikit-decide for OpenClaw

This package projects scikit-decide's registered Python domain and solver entry points into three OpenClaw-native surfaces:

- a native tool plugin (`skdecide_catalog`, `skdecide_describe`, `skdecide_match`, `skdecide_run`);
- a bundled AgentSkills-compatible `SKILL.md`;
- a static stdio MCP server backed by `python -m skdecide.openclaw_bridge mcp`.

The bridge accepts registered names only, applies explicit episode/step/time/output bounds, and emits a receipt for every success, refusal, or failure.

## Local install

```bash
uv sync
openclaw plugins install --link ./integrations/openclaw
openclaw plugins enable scikit-decide
openclaw gateway restart
openclaw plugins inspect scikit-decide --runtime --json
openclaw mcp doctor scikit-decide --probe
```

The Gateway's Python environment must be able to import this scikit-decide checkout. Configure a different executable or working directory under `plugins.entries.scikit-decide.config`:

```json5
{
  plugins: {
    entries: {
      "scikit-decide": {
        enabled: true,
        config: {
          python: "/absolute/path/to/.venv/bin/python",
          cwd: "/absolute/path/to/scikit-decide",
          timeoutMs: 120000,
          maxOutputBytes: 4194304
        }
      }
    }
  }
}
```

The static MCP manifest uses `python` by default. Operators can override `mcp.servers.scikit-decide` when the Gateway needs a different executable.

## Verification

```bash
python -m pytest tests/test_openclaw_bridge.py -q
cd integrations/openclaw
npm install --ignore-scripts --no-audit --no-fund
npm run check
git diff --exit-code -- dist/index.js
npm pack --dry-run
```

Package-install and live-runtime proof additionally require an installed OpenClaw host:

```bash
npm pack --pack-destination /tmp
openclaw plugins install npm-pack:/tmp/chatman-ai-openclaw-scikit-decide-0.1.0.tgz --force
openclaw plugins inspect scikit-decide --runtime --json
openclaw mcp doctor scikit-decide --probe
```
