import assert from "node:assert/strict";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { registerPiSearchExtension } from "../src/pi-search/extension";
import { formatPiSearchPrompt } from "../src/pi-search/agent_prompt";

function registeredTools(enabled: string) {
  process.env.PI_SEARCH_FIRST_MOVE_ENABLED = enabled;
  const tools: Array<{ name: string; description: string; parameters: unknown }> = [];
  const pi = { on() {}, registerTool(tool: typeof tools[number]) { tools.push(tool); } };
  registerPiSearchExtension(pi as unknown as ExtensionAPI, {
    resolveConfig: () => ({ backend: { kind: "mock", documents: [] } }),
  });
  return tools;
}

const previous = process.env.PI_SEARCH_FIRST_MOVE_ENABLED;
const baseline = registeredTools("0");
const gambit = registeredTools("1");
assert(!baseline.some(tool => tool.name === "first_move"));
assert(gambit.some(tool => tool.name === "first_move"));
assert.equal(JSON.stringify(baseline), JSON.stringify(gambit.filter(tool => tool.name !== "first_move")));
process.env.PI_SEARCH_FIRST_MOVE_ENABLED = "0";
const prompt = formatPiSearchPrompt("Synthetic verification question");
process.env.PI_SEARCH_FIRST_MOVE_ENABLED = "1";
assert.equal(formatPiSearchPrompt("Synthetic verification question"), prompt);
if (previous === undefined) delete process.env.PI_SEARCH_FIRST_MOVE_ENABLED;
else process.env.PI_SEARCH_FIRST_MOVE_ENABLED = previous;
console.log("Both conditions have identical common tools and user prompt; only first_move differs.");
