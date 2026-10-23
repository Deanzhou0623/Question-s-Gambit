#!/usr/bin/env python3
"""Report every frozen question, preserving failures in the denominator."""
import csv
import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'runs/comparison20'
ARMS = ('pi_serini', 'questions_gambit')
TIERS = ('surfaced', 'previewed', 'opened', 'cited')


def read_json(path):
    return json.loads(path.read_text()) if path.exists() else {}


def lines(path):
    if path.exists():
        for line in path.read_text().splitlines():
            try:
                yield json.loads(line)
            except ValueError:
                pass


def qrels(name):
    result = {}
    for line in (ROOT / 'data/browsecomp-plus/qrels' / name).read_text().splitlines():
        qid, _, docid, relevance = line.split()[:4]
        if float(relevance) > 0:
            result.setdefault(qid, set()).add(docid)
    return result


def main():
    manifest = read_json(DEST / 'subset.json')
    ids = manifest['query_ids']
    if len(ids) != 20 or len(set(ids)) != 20:
        raise ValueError('Expected the frozen 20-question subset')
    labels = {'evidence': qrels('qrel_evidence.txt'), 'gold': qrels('qrel_gold.txt')}
    judge_rates = read_json(DEST / 'cost-rates.json').get('models', {}).get('gpt-5.3-codex')
    rows, summaries = [], {}
    for arm in ARMS:
        arm_rows = []
        for qid in ids:
            unit = DEST / arm / 'queries' / qid
            run = read_json(DEST / arm / 'merged' / f'{qid}.json')
            evaluation = read_json(DEST / arm / 'evaluation/per-query' / f'{qid}_eval.json')
            judge = evaluation.get('judge_result', {})
            stats = run.get('stats', {})
            row = {'condition': arm, 'query_id': qid, 'status': run.get('status', 'missing'),
                   'correct': judge.get('correct'), 'judge_parse_error': judge.get('parse_error', True),
                   'tool_calls': stats.get('tool_calls_total'), 'tool_call_counts': run.get('tool_call_counts', {}),
                   'latency_seconds': stats.get('elapsed_seconds'), 'timed_out': stats.get('timed_out'),
                   'retrieval_failures': stats.get('pi_search_failures'),
                   'final_response': next((x.get('output', '') for x in reversed(run.get('result', []))
                                           if x.get('type') == 'output_text'), ''),
                   'run_path': str(DEST / arm / 'merged' / f'{qid}.json'),
                   'judge_path': str(DEST / arm / 'evaluation/per-query' / f'{qid}_eval.json'),
                   'raw_events_path': str(unit / 'raw-events' / f'{qid}.jsonl'),
                   'stderr_path': str(unit / 'stderr' / f'{qid}.log')}
            row['failures'] = []
            if row['status'] != 'completed': row['failures'].append(row['status'])
            if row['retrieval_failures']: row['failures'].append('retrieval_tool_error')
            if row['correct'] is None or row['judge_parse_error']: row['failures'].append('judge_missing_or_invalid')
            for label, relevance in labels.items():
                relevant = relevance.get(qid, set())
                for tier in TIERS:
                    retrieved = set(run.get(f'{tier}_docids', []))
                    hits = len(retrieved & relevant)
                    row[f'{label}_{tier}_hits'] = hits
                    row[f'{label}_{tier}_total'] = len(relevant)
                    row[f'{label}_{tier}_recall'] = hits / len(relevant) if relevant else None
            # Count only message_end, avoiding duplicate agent_end usage.
            agent_usage = [e.get('message', {}).get('usage') for e in lines(unit / 'raw-events' / f'{qid}.jsonl')
                           if e.get('type') == 'message_end' and e.get('message', {}).get('role') == 'assistant']
            agent_usage = [u for u in agent_usage if u]
            row['agent_turns_with_usage'] = len(agent_usage)
            row['agent_estimated_cost_usd'] = sum(u.get('cost', {}).get('total', 0) for u in agent_usage)
            row['agent_input_tokens'] = sum(u.get('input', 0) for u in agent_usage)
            row['agent_output_tokens'] = sum(u.get('output', 0) for u in agent_usage)
            row['agent_cached_tokens'] = sum(u.get('cacheRead', 0) for u in agent_usage)
            calls = list(lines(unit / 'api_usage.jsonl'))
            row['module_api_calls'] = len(calls)
            row['module_api_error_calls'] = sum(c.get('status', 200) >= 400 for c in calls)
            row['module_reported_cost_usd'] = sum(c.get('reported_cost_usd') or 0 for c in calls)
            row['module_estimated_cost_usd'] = sum(c.get('estimated_cost_usd') or 0 for c in calls
                                                   if c.get('reported_cost_usd') is None)
            row['module_unpriced_calls'] = sum(1 for c in calls if c.get('reported_cost_usd') is None
                                                and c.get('estimated_cost_usd') is None)
            row['inference_cost_usd'] = (row['agent_estimated_cost_usd'] + row['module_reported_cost_usd']
                                         + row['module_estimated_cost_usd'])
            judge_usage = evaluation.get('judge_usage', {})
            row['judge_estimated_cost_usd'] = (
                ((judge_usage.get('input', 0) - judge_usage.get('cacheRead', 0)) * judge_rates['input']
                 + judge_usage.get('cacheRead', 0) * judge_rates['cacheRead']
                 + judge_usage.get('output', 0) * judge_rates['output']) / 1e6
                if judge_rates and judge_usage.get('assistantTurnsWithUsage') else None)
            row['total_cost_usd'] = (row['inference_cost_usd'] + row['judge_estimated_cost_usd']
                                     if row['judge_estimated_cost_usd'] is not None else None)
            row['cost_coverage'] = 'incomplete' if row['module_unpriced_calls'] or not agent_usage else 'usage_available'
            arm_rows.append(row)
        rows.extend(arm_rows)
        summary = {'questions': 20, 'completed': sum(r['status'] == 'completed' for r in arm_rows),
                   'judged': sum(r['correct'] is not None and not r['judge_parse_error'] for r in arm_rows),
                   'correct': sum(r['correct'] is True and not r['judge_parse_error'] for r in arm_rows),
                   'questions_with_failures': sum(bool(r['failures']) for r in arm_rows)}
        summary['accuracy_pct_all_20'] = 100 * summary['correct'] / 20
        for field in ('tool_calls', 'latency_seconds'):
            values = [r[field] for r in arm_rows if r[field] is not None]
            summary[f'{field}_mean'] = statistics.mean(values) if values else None
            summary[f'{field}_median'] = statistics.median(values) if values else None
            summary[f'{field}_total'] = sum(values)
        for label in labels:
            for tier in TIERS:
                prefix = f'{label}_{tier}'
                values = [r[f'{prefix}_recall'] for r in arm_rows if r[f'{prefix}_recall'] is not None]
                total = sum(r[f'{prefix}_total'] for r in arm_rows)
                summary[f'{prefix}_macro_pct'] = 100 * statistics.mean(values) if values else None
                summary[f'{prefix}_micro_pct'] = 100 * sum(r[f'{prefix}_hits'] for r in arm_rows) / total if total else None
        summary['inference_cost_usd'] = sum(r['inference_cost_usd'] for r in arm_rows)
        summary['module_api_calls'] = sum(r['module_api_calls'] for r in arm_rows)
        summary['module_api_error_calls'] = sum(r['module_api_error_calls'] for r in arm_rows)
        summary['module_unpriced_calls'] = sum(r['module_unpriced_calls'] for r in arm_rows)
        summary['questions_with_incomplete_cost_usage'] = sum(r['cost_coverage'] != 'usage_available' for r in arm_rows)
        judge_calls = list(lines(DEST / arm / 'judge_api_usage.jsonl'))
        summary['judge_estimated_cost_usd'] = sum(c.get('estimated_cost_usd') or 0 for c in judge_calls)
        summary['judge_unpriced_calls'] = sum(c.get('estimated_cost_usd') is None for c in judge_calls)
        summary['total_cost_usd'] = summary['inference_cost_usd'] + summary['judge_estimated_cost_usd']
        summaries[arm] = summary
    prompt_audit = []
    for qid in ids:
        snapshots = [read_json(DEST / arm / 'queries' / qid / 'prompt_snapshot.json') for arm in ARMS]
        prompt_audit.append({'query_id': qid,
            'user_prompt_identical': all(snapshots) and snapshots[0].get('user_prompt') == snapshots[1].get('user_prompt'),
            'system_prompt_identical': all(snapshots) and snapshots[0].get('system_prompt') == snapshots[1].get('system_prompt')})
    output = {'subset': manifest, 'configuration': read_json(DEST / 'configuration.json'), 'prompt_audit': prompt_audit,
              'cost_note': 'USD estimates use locked pi-ai 0.74.0 token prices plus API-reported rerank costs; not an invoice. Unpriced calls are explicitly counted.',
              'summary': summaries, 'per_question': rows}
    (DEST / 'comparison.json').write_text(json.dumps(output, indent=2) + '\n')
    with (DEST / 'per_question.csv').open('w') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows({k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in row.items()} for row in rows)
    report = ['# BrowseComp-Plus paired 20-question comparison', '',
              f'Subset: seed {manifest["seed"]}; query IDs: {", ".join(ids)}.', '',
              'Accuracy uses all 20 selected questions in the denominator; failures are retained.', '',
              '| Metric | Pi-Serini | Question’s Gambit |', '|---|---:|---:|']
    fields = [('Completed', 'completed'), ('Valid judgments', 'judged'),
              ('Answer accuracy (%)', 'accuracy_pct_all_20'), ('Tool calls, mean', 'tool_calls_mean'),
              ('Latency, mean seconds', 'latency_seconds_mean'), ('Latency, median seconds', 'latency_seconds_median'),
              ('Inference cost, estimated USD', 'inference_cost_usd'), ('Judge cost, estimated USD', 'judge_estimated_cost_usd'),
              ('Total cost, estimated USD', 'total_cost_usd'), ('Unpriced module calls', 'module_unpriced_calls'),
              ('Questions with incomplete cost usage', 'questions_with_incomplete_cost_usage'),
              ('Questions with failures', 'questions_with_failures')]
    fields += [(f'{label.title()} {tier} recall, macro (%)', f'{label}_{tier}_macro_pct')
               for label in labels for tier in TIERS]
    for label, key in fields:
        values = [summaries[a].get(key) for a in ARMS]
        report.append('| ' + label + ' | ' + ' | '.join(f'{v:.4f}' if isinstance(v, float) else str(v) for v in values) + ' |')
    report += ['', output['cost_note'], '',
               f'Actual saved user and system prompts match in {sum(x["user_prompt_identical"] and x["system_prompt_identical"] for x in prompt_audit)}/20 pairs.', '',
               'This is a controlled first_move ablation in the released harness. Both arms retain its shared prompt, including references to first_move; the baseline does not expose that tool. It is not an independently checked upstream Pi-Serini prompt reproduction.', '',
               'Per-question answers, statuses, tool counts, recall and costs: `per_question.csv` and `comparison.json`.',
               'Full traces: `<condition>/queries/<query_id>/`; judge outputs: `<condition>/evaluation/per-query/`.',
               'Exact executed argument lists: `commands.jsonl`; shared settings: `configuration.json`.', '',
               'The smoke check initially stopped at the local recall postprocessor because of incorrect launcher argument names. The arguments were corrected and saved agent/judge outputs reused. No paid agent or judge call was repeated for that repair.', '']
    (DEST / 'REPORT.md').write_text('\n'.join(report))
    print(json.dumps(summaries, indent=2))


if __name__ == '__main__':
    main()
