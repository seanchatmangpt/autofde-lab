import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(here, "..");
const manifest = JSON.parse(fs.readFileSync(path.join(root, "openclaw.plugin.json"), "utf8"));
const pkg = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
const source = fs.readFileSync(path.join(root, "dist", "index.js"), "utf8");

const tools = ["skdecide_catalog", "skdecide_describe", "skdecide_match", "skdecide_run"];

test("manifest, package metadata, and runtime registrations agree", () => {
  assert.equal(manifest.id, "scikit-decide");
  assert.deepEqual(manifest.contracts.tools, tools);
  assert.deepEqual(pkg.openclaw.extensions, ["./dist/index.js"]);
  assert.equal(pkg.peerDependencies.openclaw, ">=2026.7.1-2");
  for (const tool of tools) {
    assert.match(source, new RegExp(`name: ["']${tool}["']`));
  }
});

test("plugin bundles a skill and a static stdio MCP server", () => {
  assert.deepEqual(manifest.skills, ["./skills"]);
  assert.equal(manifest.mcpServers["scikit-decide"].transport, "stdio");
  assert.deepEqual(manifest.mcpServers["scikit-decide"].args, ["-m", "skdecide.openclaw_bridge", "mcp"]);
  const skillPath = path.join(root, "skills", "scikit-decide", "SKILL.md");
  assert.ok(fs.existsSync(skillPath));
  const skill = fs.readFileSync(skillPath, "utf8");
  assert.match(skill, /^---\nname: scikit-decide\ndescription:/);
});

test("compute-bearing tools are optional and bounded", () => {
  assert.equal(manifest.toolMetadata.skdecide_match.optional, true);
  assert.equal(manifest.toolMetadata.skdecide_run.optional, true);
  assert.equal(manifest.toolMetadata.skdecide_match.replaySafe, false);
  assert.equal(manifest.toolMetadata.skdecide_run.replaySafe, false);
  assert.equal(manifest.configSchema.properties.timeoutMs.maximum, 600000);
  assert.equal(manifest.configSchema.properties.maxOutputBytes.maximum, 16777216);
});
