# Question's Gambit: experiment summary and trace findings

## Summary

I ran two separate paired comparisons: a 20-question experiment to inspect
overall performance, and a five-question experiment to examine how the search
process differed with and without Question's Gambit. Each pair uses the same
question in both conditions. The five-question batch is a separate case study,
not a subset of the 20-question experiment.

In the 20-question experiment, I did not observe an improvement in final-answer
accuracy with Gambit. It used fewer agent-visible tool calls, but average
latency and estimated inference cost were higher. The trace review showed
mixed behavior: Gambit sometimes exposed useful evidence earlier, sometimes
left useful evidence outside the opening top five, and sometimes introduced
an incorrect candidate that was pursued in later searches.

These observations suggest that **finding evidence, presenting it to the agent,
and checking the final answer's conditions are separate problems**. They do
not establish that Gambit is ineffective in general, or identify which
individual component causes its gains or failures.

## 1. How I ran the comparisons

Both experiments used a fixed local BrowseComp-Plus corpus and BM25 index,
the same GPT-5.5 agent with medium thinking, shared system/user prompts, and
the same downstream search and document-reading tools. Reference answers
were used for evaluation, not provided to the agent.

The baseline disables the `first_move` tool; Gambit enables it. Gambit's opening
pipeline decomposes the question into clues, retrieves three feedback results
per clue, generates MUGI expansions with GPT-4.1, retrieves deeper candidate
lists, merges and reranks them, and returns five opening documents.

This is a **whole-pipeline on/off comparison in the released local harness**.
The baseline still receives the shared prompt mentioning `first_move`, although
that tool is unavailable. It is not an independently verified reproduction of
upstream Pi-Serini. Identical downstream settings and time limits also do not
mean equal total computation: Gambit's opening includes additional internal
retrieval, generation, and reranking.

### Experiment A: 20 paired questions — overall performance

I used the frozen 20-question sample drawn from the repository's q50 development
set with seed 42, running each question once per condition. All 40 agent runs
completed and received valid automated judgments. I compared final-answer
correctness, evidence recall, tool use, latency, and estimated cost.

**Conclusion:** This sample did not reproduce an accuracy gain from Gambit.
Fewer outer tool calls did not translate into lower average latency or cost.
However, this is a small, single-run sample with a near-ceiling baseline, not
evidence of equivalence or a direct refutation of the paper's benchmark results.
It also cannot isolate whether the position of the opening retrieval matters.

References: [experiment setup](comparison20.md),
[full results](../runs/comparison20/REPORT.md),
[per-question results and artifact paths](../runs/comparison20/comparison.json),
[frozen sample](../runs/comparison20/subset.json).
The `runs/` links point to local, ignored artifacts; they will not work in a
public checkout unless those artifacts are separately supplied.

### Experiment B: five paired questions — qualitative process review

I ran tasks **770, 781, 788, 792, and 244** once per condition: five pairs,
ten agent runs. I inspected generated clues, the exact feedback supplied to
MUGI, generated passages, candidate rankings, the opening context, subsequent
searches and reads, and final answers where available. I checked completed
answers against the local reference answers manually, separately from whether
their explanations verified every condition.

Eight runs completed. Gambit–770 and baseline–244 stopped after repeated API
token-rate-limit errors. Their partial traces can reveal intermediate behavior,
but they cannot support final-answer comparisons. This review did not add
paid agent runs or automated judging.

**Conclusion:** The clearest observed benefit was earlier exposure to useful
evidence on 781. Other cases showed opening-selection problems, misleading
leads, or incomplete condition verification. These are descriptive case
findings, not estimates of how frequently each problem occurs.

References: [five-pair trace index](comparison5/TRACE_PAIRS.md),
[detailed analysis](comparison5/ANALYSIS.md),
[completion summary](comparison5/summary.json),
[protocol checks and API errors](comparison5/validation.json).

## 2. What differed between baseline and Gambit?

| Task | Baseline | Question's Gambit | Finding |
|---|---|---|---|
| **781** | The correct report was already in the first search at rank 203, outside the initial previews. The agent read it at tool call 22 and answered correctly. | The correct report was first in the opening context. The agent read it immediately and answered correctly with far fewer outer calls. | Useful evidence became visible and usable earlier; this does not isolate first-move timing from deeper retrieval and reranking. |
| **770** | The agent read the correct research-group page at call 16, checked additional sources, and returned the reference name. | That page was feedback rank 1 and expanded-retrieval rank 2, but rerank position 12 excluded it from the opening. The agent first read an unrelated profile; it read the group page at call 30 and later stopped due to rate limiting. | Retrieval found useful evidence, but opening selection did not expose it. There is no completed Gambit answer to compare. |
| **244** | A correct document appeared at rank 52 in the search at call 18, but was not previewed or read. The run later stopped due to rate limiting. | Neither gold document was in the initial candidate pool. An incorrect opening candidate was used in later searches and ultimately returned as the wrong answer. | Baseline found but did not use relevant evidence; Gambit pursued a misleading candidate. The sequence is observable, but it does not prove the opening caused the final error. |
| **788** | The correct mosque document was rank 2 in the first search and read at call 2. The final entity matched the reference, but the hospital-date condition was not properly verified. | The same document was opening rank 1 and read at call 2. The final entity also matched, with the same hospital-date verification gap. | No rescue from a wrong opening was observed. A correct entity answer can conceal an unsupported condition. |
| **792** | The publisher clue immediately retrieved a useful publisher page; subsequent searches found the correct article. | The agent used related creatine-study documents as a bridge. The target article was rerank position 7, outside the opening top five, and was found later. | Both answered correctly via different routes. Gambit did not reduce outer calls or observed elapsed time in this run. |

Case evidence:
[781](comparison5/evidence/781.md),
[770](comparison5/evidence/770.md),
[244](comparison5/evidence/244.md),
[788](comparison5/evidence/788.md),
[792](comparison5/evidence/792.md).
The [trace index](comparison5/TRACE_PAIRS.md) links both conditions' transcripts.
Elapsed-time differences are not clean speed estimates: API rate limiting
affected some runs, including runs that eventually completed.

## 3. My findings from the traces

1. **Retrieved does not mean seen or used.** On 781, baseline had the report
   deep in its first ranking; Gambit made it immediately visible. On 770,
   Gambit had useful evidence but dropped it from the opening top five.
2. **Expansion can add unsupported connections.** Unrelated feedback was
   sometimes combined into specific people, institutions, or publication
   claims. For example, 770's passages linked people and labs without support
   in the supplied feedback. Generated search text is not verified evidence.
   However, an unsupported passage alone does not show that it affected the
   downstream answer; that requires following its retrieval and action path.
3. **An opening candidate can become a persistent lead.** On 244, the
   bibliometrics/co-authorship candidate appeared in later searches and the
   final answer, without verification of the required shared-citation relation.
   This suggests a possible anchoring mechanism, not proven causation.
4. **Answer matching and evidence verification can disagree.** On 788, both
   systems found the reference entity, but used hospital building/expansion
   dates to support an establishment-date condition. The trace therefore
   reveals a weakness that final-answer scoring misses.
5. **A different opening is not automatically a better process.** On 792,
   baseline already had a useful first result. Gambit supplied another route
   to the same answer without an observed efficiency gain.

## 4. Questions to discuss with Amir

1. **What exactly helped on 781: the first position, or better evidence
   ranking?** Would the same documents help as much if the agent received
   them later? The current comparison changes both document selection and
   presentation timing.
2. **Why was useful evidence pushed out of the opening on 770?** Is the
   problem the reranker's input, its ranking, or the five-document cutoff?
   What is the smallest controlled check that would distinguish these?
3. **When does noisy MUGI text actually change the agent's path?** Can we
   follow an unsupported name or relationship from expansion into retrieved
   documents, then into a later query or final claim, rather than assume
   every unsupported passage is harmful?
4. **What would show that the opening caused the detour on 244?** Could we
   rerun the same task with the misleading opening candidate removed or
   replaced, while holding the remaining settings and budget fixed?
5. **How should we evaluate answers that name the right entity but do not
   verify all the clues?** On 788, should we separately assess each condition
   and whether its cited evidence actually supports it?
6. **When is Gambit's extra work worth it?** Comparing 781 with 788 and 792,
   can we identify questions that need deeper opening retrieval versus those
   where an ordinary first search already provides a useful lead?

These are follow-up questions motivated by the saved traces, not mechanisms
already established by the experiments. No additional runs were launched to
write this summary. The incomplete later `followup5` batch is outside the two
experiments summarized here.

---

# Original five-question experiment specification

The original specification is retained below for protocol and artifact details.
The completed-run findings above supersede its prospective review instructions.

Status: the initial experiment finished on October 22, 2026. Exactly five
questions were run in both conditions (ten traces): eight completed, and
Gambit–770 and baseline–244 failed after repeated API token-rate-limit errors.
No replacement attempts or answer judging were run.

Inspect the [five trace pairs](comparison5/TRACE_PAIRS.md).
The index links readable transcripts, final answers where available, and full
sanitized artifact archives. Complete original artifacts remain under the local
`runs/comparison5/<condition>/queries/<id>/` directories.

Branch: `experiment/five-question-trace-comparison`.

## Trace pairs

Each question produces one Question's Gambit trace and one Pi-Serini baseline
trace: five pairs, ten agent runs total. The question descriptions below are
labels, not replacements for the full original questions.

| Pair | Question ID | Question label | Gambit trace directory | Baseline trace directory |
|---|---|---|---|---|
| 1 | 770 | Research-group coordinator and Routledge book co-editor | `runs/comparison5/questions_gambit/queries/770/` | `runs/comparison5/pi_serini/queries/770/` |
| 2 | 781 | Player who assisted the third goal of the football match | `runs/comparison5/questions_gambit/queries/781/` | `runs/comparison5/pi_serini/queries/781/` |
| 3 | 788 | Mosque identified through capacity, area, and nearby landmarks | `runs/comparison5/questions_gambit/queries/788/` | `runs/comparison5/pi_serini/queries/788/` |
| 4 | 792 | Article about a supplement-based disease approach | `runs/comparison5/questions_gambit/queries/792/` | `runs/comparison5/pi_serini/queries/792/` |
| 5 | 244 | Shared 2016 citation in a post and scientific paper | `runs/comparison5/questions_gambit/queries/244/` | `runs/comparison5/pi_serini/queries/244/` |

These local directories now contain the initial traces, including failed runs.
The initial deliverable after running is an index linking each pair so the user
can inspect the traces themselves. Written qualitative reviews are optional
follow-up work, not a prerequisite for delivering the trace pairs.

## Inputs and controls

Before running, match each supplied question to its dataset ID and verify the
full text. Stop on an ID/text mismatch rather than silently substituting a
question. Freeze exactly these five questions in
`runs/comparison5/questions.tsv`, preserving the order above. Record input
checksums and the code revision in `manifest.json`.

Use a separate runner and output directory. Do not replace the existing frozen
20-question experiment or alter its exact-20-question guards.

| Setting | Specification |
|---|---|
| Agent model | `openai/gpt-5.5` |
| Agent thinking | `medium` |
| Timeout | 900 seconds per agent run, including first-move work |
| Corpus/index | Local BrowseComp-Plus, `indexes/browsecomp-plus-bm25-tevatron` |
| Runtime retrieval | Pyserini BM25, k1=25, b=1 |
| Agent concurrency | At most four runs, using the shared BM25 server |
| Repetitions | One run per question per condition |
| Submission order | Alternate baseline-first and Gambit-first by pair |
| Shared behavior | Identical input questions, system/user prompts, and downstream tool definitions |
| Baseline treatment | `PI_SEARCH_FIRST_MOVE_ENABLED=0` |
| Gambit treatment | `PI_SEARCH_FIRST_MOVE_ENABLED=1` |

The baseline is the repository's Pi-Serini-style ablation: it disables
`first_move` registration while retaining the shared prompt and harness. The
shared prompt still mentions `first_move`. Tool definitions therefore differ
by that tool's availability. This is not a separately verified reproduction of
upstream Pi-Serini.

Gambit retains the released pipeline: agent-model clue decomposition, three
feedback documents per clue, five MUGI pseudo-documents per clue generated by
`gpt-4.1`, retrieval depth 1000 per expanded clue, merged candidate reranking
with Cohere Rerank 4 Pro, and five opening-context documents. The downstream
agent uses `search`, `read_search_results`, and `read_document` in both arms.

## Run procedure

1. Verify and freeze the five questions and save configuration and checksums.
2. Save the actual prompts and launch settings for each condition.
3. Execute exactly ten initial agent runs using the paired submission order.
4. Verify statuses, tool errors, shared-prompt equality, no baseline
   `first_move` calls, and Gambit's opening `first_move` call. Flag departures
   from the intended protocol in the results.
5. Preserve failures and timeouts. Do not silently overwrite or replace a trace.
   Any explicitly requested retry gets a separate attempt directory.
6. Generate `runs/comparison5/TRACE_PAIRS.md` with direct relative links to each
   pair's answer, readable transcript, raw events, and Gambit audit artifacts.

No live web search is part of these benchmark runs. Reference answers are used
only for evaluation after the agent finishes, not as agent input.

## Required trace artifacts

For each of the ten runs, retain the full question, prompt snapshot, launch
configuration, raw agent events, readable transcript, tool arguments and
responses, document IDs and reads, final answer, completion status, errors,
wall time, and available API usage. Preserve agent-visible content and event
ordering; do not synthesize missing reasoning.

For each Gambit run, additionally retain:

- Every generated clue in order.
- All three ranked feedback results per clue, including document IDs and the
  exact text supplied to expansion.
- All five MUGI passages per clue, the combined expanded query, and repetition
  count.
- Per-clue retrieval results and merged/reranked candidate information available
  from the pipeline.
- The five opening-context documents in their returned order and the exact
  context returned to the agent.

Inspect existing logging before launch. If a required intermediate artifact is
not currently recorded, add logging that preserves retrieval and prompt
behavior. Mark unavailable fields explicitly rather than reconstructing them
as if they had been observed.

## Manual review checklist

The user can apply these five questions to each pair independently:

1. **Are the generated clues faithful to the original question?** Check every
   condition, including dates, ranges, quantities, entities, and relationships.
   Identify missing, misunderstood, weakened, or added conditions.
2. **Are the top-three feedback results relevant to each clue?** Inspect each
   result separately and identify content that could mislead expansion.
3. **What does MUGI add?** Separate useful search terms, content supported by
   feedback, and unsupported names, facts, or assumptions.
4. **How does the opening context affect later actions?** Follow which
   documents the agent reads and which later searches pursue useful evidence
   or a wrong direction. Distinguish observed behavior from inferred influence.
5. **Compared with the baseline, where does Gambit help or hurt?** Compare
   first moves, evidence discovery, detours, and final answers. Consider whether
   a difference appears associated with decomposition, feedback, expansion,
   reranking, or subsequent agent behavior.

## Secondary evaluation

After delivering the trace pairs, automated evaluation may report final-answer
correctness using the existing gold-answer judge (`gpt-5.3-codex`, 180-second
timeout), evidence/gold recall at surfaced, previewed, opened, and cited tiers,
tool-call counts, latency, and estimated API cost. Record the actual judge
model identifier and pricing assumptions. Include all five questions in each
arm's denominator and explicitly identify missing or failed evaluations.

One run per condition supports case-by-case trace inspection. It does not
establish performance stability or isolate the causal effect of MUGI or
reranking within the full Gambit pipeline.

## Output layout and Git policy

```text
docs/readme.md
docs/comparison5/     # published trace pairs, transcripts, answers, and archives
runs/comparison5/
  questions.tsv
  configuration.json
  manifest.json
  TRACE_PAIRS.md
  pi_serini/queries/<question_id>/
  questions_gambit/queries/<question_id>/
  evaluation/          # secondary evaluation, if generated
  per_question.csv    # secondary evaluation, if generated
  REPORT.md           # secondary evaluation, if generated
```

Commit experiment scripts, this specification, the pair index, and publishable
results on `experiment/five-question-trace-comparison`. Publish results under
`docs/comparison5/`; keep `runs/` ignored so unrelated runs remain local.
Keep complete raw artifacts locally and preserve
trace links to their publishable counterparts where sanitization is needed.

The repository is public. Exclude credentials, authorization headers, local
account/session state, bulk datasets, indexes, and dependencies. Check benchmark
and document redistribution terms before committing their full text. Record
any omitted or redacted content so the public record is not presented as a
complete raw trace when it is not.
