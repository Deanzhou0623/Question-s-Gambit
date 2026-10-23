# Question's Gambit: experiments and findings

## Summary

I compared baseline and Gambit in two separate batches: 20 paired questions for overall performance, and five paired questions for trace analysis. The 20-question sample showed no accuracy improvement and higher average latency and estimated cost. The traces showed mixed effects: earlier access to useful evidence in some cases, but poor opening selection or incomplete verification in others.

## 1. How I ran the comparisons

Both conditions used the same fixed BrowseComp-Plus corpus, BM25 index, GPT-5.5 agent with medium thinking, shared prompts, and downstream tools. The baseline disabled `first_move`; Gambit enabled clue decomposition, GPT-4.1 MUGI expansion, deeper retrieval, reranking, and a top-five opening context. Reference answers were used only for evaluation.

This compares the whole opening pipeline, not its individual components. The shared prompt still mentions `first_move` when it is disabled, so this is a local harness comparison, not a separately verified reproduction of upstream Pi-Serini. Equal time limits do not mean equal computation.

### Experiment A: 20 paired questions — overall performance

I used a frozen sample from the repository's q50 development set, selected with seed 42. Each question was run once per condition. All 40 runs completed and received valid automated judgments.

| Metric | Baseline | Question's Gambit |
|---|---:|---:|
| Correct answers | 19/20 | 18/20 |
| Average agent-visible tool calls | 18.9 | 14.3 |
| Average time per question | 77.8 s | 87.0 s |
| Total estimated inference cost | $8.14 | $10.57 |

**Conclusion:** Gambit used fewer outer tool calls, but this sample showed no accuracy gain, while average latency and estimated cost were higher. The small sample and near-ceiling baseline limit the conclusion; this does not establish equivalence or refute the paper's results. Outer calls exclude internal first-move work, and costs are estimates, not invoices.

References: [setup](comparison20.md), [results](../runs/comparison20/REPORT.md), [per-question records](../runs/comparison20/comparison.json). The `runs/` links are local-only and do not work in a public checkout.

### Experiment B: five paired questions — trace analysis

I reviewed tasks **770, 781, 788, 792, and 244**, each run once per condition. I followed clues, feedback, MUGI passages, rankings, opening documents, later actions, and final answers. Completed answers were manually checked against the reference answers.

Eight of ten runs completed. Gambit–770 and baseline–244 stopped due to API token-rate limits; neither should be counted as a reasoning error. Their partial traces support process observations, not final-answer comparisons.

References: [trace pairs](comparison5/TRACE_PAIRS.md), [analysis](comparison5/ANALYSIS.md), [status and errors](comparison5/validation.json).

## 2. Baseline versus Gambit: what changed?

| Task / evidence | Baseline | Gambit | Main observation |
|---|---|---|---|
| [781](comparison5/evidence/781.md) | Correct report ranked 203 in the first search; read at call 22. Answered correctly. | Same report ranked first in the opening; read immediately. Answered correctly. | Earlier evidence exposure helped, but timing is not isolated from retrieval and reranking. |
| [770](comparison5/evidence/770.md) | Correct group page read at call 16; returned the reference name. | Correct page was feedback rank 1 and expanded rank 2, but rerank 12 excluded it from the opening. Read at call 30; later rate-limited. | Useful evidence was retrieved but not presented early. No completed Gambit answer. |
| [244](comparison5/evidence/244.md) | Correct document appeared at rank 52 at call 18, but was not read. Later rate-limited. | Gold documents were absent from the initial pool. Pursued an incorrect opening candidate and returned it as the answer. | Different evidence-use failures; the trace suggests, but does not prove, an opening-induced detour. |
| [788](comparison5/evidence/788.md) | Correct candidate ranked 2; read at call 2. Answer matched, but hospital-date support was inadequate. | Same candidate ranked 1; read at call 2. Same answer and verification gap. | Both found the candidate early; correct entity scoring missed a condition-level weakness. |
| [792](comparison5/evidence/792.md) | Useful publisher page appeared first; later found the correct article. | Used related studies as a bridge; target article ranked 7, outside the opening. Later answered correctly. | Different successful paths, without fewer outer calls or lower observed latency for Gambit. |

These are single-run observations. Rate limits also affected some completed runs, so elapsed time is not a clean speed comparison in this five-pair batch.

## 3. Findings

- **Retrieved is not the same as seen or used.** Tasks 781 and 770 show opposite outcomes of evidence prioritization.
- **MUGI can add unsupported connections.** On 770, generated passages linked people and institutions without support in the supplied feedback. Whether these additions affected later actions must be checked, not assumed.
- **Wrong opening candidates can persist.** On 244, the initial bibliometrics candidate appeared in later searches and the wrong final answer. This is an observed sequence, not a causal demonstration.
- **Correct answers can hide verification gaps.** On 788, both systems used hospital building/expansion dates to support an establishment-date condition.
- **Extra opening work is not always beneficial.** On 792, baseline already had a useful first result; Gambit changed the route without an observed efficiency gain.

## 4. Questions

1. On **781**, did the benefit come from receiving evidence first, or from retrieving and ranking better documents?
2. On **770**, why was useful evidence pushed outside the opening: the reranker's input, ranking, or top-five cutoff?
3. When does unsupported **MUGI** text actually affect retrieved documents and later agent actions?
4. On **244**, would removing or replacing the misleading opening candidate change the later searches and answer?
5. On **788**, how should we evaluate an answer that names the right entity but does not verify all the conditions?
6. Comparing **781, 788, and 792**, when is Gambit's additional opening work worth the cost?

## 5. What I can do next

1. **Finish the evidence chains using existing traces.** For 781, 770, and 244, mark where the two paths diverge, which document prompted the next action, and what remains unverified. Also inspect task 484 from the 20-question batch, where baseline was judged correct and Gambit incorrect.
2. **Choose one small follow-up check.** Depending on the discussion, inspect ranking inputs on 770 or test removing the misleading opening candidate on 244. Change one factor at a time and record the computation used; do not expand into a new agent design yet.
3. **Complete missing pairs only if needed.** If final-answer comparisons for 770 and 244 are necessary, rerun the interrupted conditions with a separate attempt record. These are proposed next steps, not experiments already performed.
