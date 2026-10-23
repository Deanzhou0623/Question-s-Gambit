// Capture usage for non-streaming decomposition, expansion, reranking, and judge calls.
// Agent streaming usage is retained separately in raw-events/*.jsonl by the harness.
import { appendFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import { getModel } from '@earendil-works/pi-ai';

const originalFetch = globalThis.fetch;
globalThis.fetch = async function(input, init) {
  const started = Date.now();
  const response = await originalFetch(input, init);
  const destination = process.env.EXPERIMENT_USAGE_FILE;
  const url = String(input?.url ?? input);
  if (!destination || !/api\.openai\.com|openrouter\.ai/.test(url) ||
      !response.headers.get('content-type')?.includes('application/json')) return response;
  try {
    const payload = await response.clone().json();
    let request = {};
    try { request = JSON.parse(init?.body ?? '{}'); } catch {}
    const usage = payload.usage;
    const model = request.model ?? payload.model;
    const rates = getModel('openai', model)?.cost;
    const cached = usage?.input_tokens_details?.cached_tokens ?? usage?.prompt_tokens_details?.cached_tokens ?? 0;
    const inputTokens = usage?.input_tokens ?? usage?.prompt_tokens;
    const outputTokens = usage?.output_tokens ?? usage?.completion_tokens;
    const estimate = rates && inputTokens !== undefined && outputTokens !== undefined
      ? ((inputTokens - cached) * rates.input + cached * rates.cacheRead + outputTokens * rates.output) / 1e6 : null;
    mkdirSync(dirname(destination), { recursive: true });
    appendFileSync(destination, JSON.stringify({
      query_id: process.env.PI_SEARCH_QUERY_ID ?? null,
      url, model, status: response.status, elapsed_ms: Date.now() - started,
      usage: usage ?? null, estimated_cost_usd: estimate,
      reported_cost_usd: usage?.cost ?? null,
      rates_source: rates ? '@earendil-works/pi-ai@0.74.0' : null,
      error: payload.error ? JSON.stringify(payload.error).slice(0, 500) : null,
    }) + '\n');
  } catch (error) {
    console.error('[experiment20 usage]', error.message);
  }
  return response;
};
