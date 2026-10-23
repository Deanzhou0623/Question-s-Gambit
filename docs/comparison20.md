# Paired 20-question BrowseComp-Plus experiment

The comparison uses `runs/comparison20/q20.tsv` for both conditions. It samples
20 questions from the repository's q50 development set with Python seed 42,
after sorting q50 by numeric query ID. `subset.json` records the selected IDs,
sampling algorithm, source checksum and subset checksum. A frozen subset cannot
be silently replaced.

The baseline disables `first_move` registration with
`PI_SEARCH_FIRST_MOVE_ENABLED=0`. Question's Gambit enables it with `1`. Both use
the same shared user-prompt template and downstream tool definitions. The shared
prompt still mentions `first_move` in the baseline, as required to keep the
prompt identical. Consequently this is a controlled ablation of the released
harness, rather than a separately verified reproduction of upstream Pi-Serini's
original prompt. The system's tool definitions necessarily differ by the added
`first_move` tool. Each query saves its actual prompts in `prompt_snapshot.json`.

Shared settings:

- Agent: `openai/gpt-5.5`; thinking: `medium`; timeout: 900 seconds.
- Index: `Tevatron/browsecomp-plus-indexes`, `bm25/*`.
- Runtime retrieval: Pyserini BM25, k1=25, b=1, shared server.
- Up to four concurrent agent queries, alternating condition submission order.
- Judge: `gpt-5.3-codex`, gold-answer mode, 180-second timeout, concurrency four.
- Question's Gambit retains the repository's fixed decomposition, five MUGI
  pseudo-documents per clue, gpt-4.1 expansion, depth 1000 per clue, Cohere
  Rerank 4 Pro, and top-five opening context.

With the local Python environment and assets installed, run:

```bash
# Only needed when q50 is absent. This performs full-population LOCAL BM25
# retrieval to reproduce q50 strata, and requires separate authorization.
# No agent or judge is invoked here. The repository's slice-generation
# preparation uses Anserini's default k1=0.9, b=0.4.
bash scripts/prepare_experiment20_bm25.sh

# If q50 already exists, freeze the subset directly instead:
python3 scripts/prepare_experiment20.py --seed 42

# First selected question, both conditions, including judge and recall checks.
bash scripts/experiment20.sh smoke

# Requires the smoke success marker. Runs the remaining 19 in both conditions.
# Smoke outputs are retained; completed agent/judge outputs are not repeated.
bash scripts/experiment20.sh remaining

python3 scripts/report_experiment20.py
```

The runner only accepts the frozen set of exactly 20 distinct IDs, limits each
agent subprocess to one question, checks judge inputs against those IDs, and
rejects changed configuration between stages. It does not launch `run_arm.sh`
or the full agent benchmark. The smoke success gate requires completed answers,
no retrieval-tool failures, an exercised `first_move` for Question's Gambit,
and a valid judge result in both conditions. Incorrect answers are valid smoke
outcomes; transport, retrieval and judge failures are not.

Outputs live under `runs/comparison20/`:

- `REPORT.md`, `comparison.json`, `per_question.csv`: aggregate and per-question
  answer accuracy, all four evidence/gold recall tiers, calls, latency and costs.
- `configuration.json`, `commands.jsonl`, `subset.json`, `input_hashes.json`,
  `python-requirements.lock`, `cost-rates.json`: reproducibility records.
- `<condition>/queries/<query_id>/`: answer, complete raw events, stderr,
  API usage, launch log and prompt snapshots.
- `<condition>/evaluation/per-query/`: judge response and recall evaluation.

Answer accuracy uses all 20 questions as its denominator. Missing and failed
questions are retained. Recall is reported as macro and micro over the surfaced,
previewed, opened and cited document sets, against both evidence and gold qrels.
Tool calls are agent-visible calls; internal first-move retrieval and LLM work
are additionally recorded in its trace and usage logs. Latency is the harness's
per-question agent wall time and includes first-move work, excluding server
startup and judging.

Costs combine agent streaming usage, decomposition/expansion token usage and
API-reported rerank charges. Judge costs are separate. Token costs are estimates
from the locked pi-ai 0.74.0 rate table, not an invoice; unpriced calls and absent
usage are explicit. No benchmark question or answer is published online.
