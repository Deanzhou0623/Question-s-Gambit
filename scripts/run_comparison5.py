#!/usr/bin/env python3
"""Run only the five authorized questions in two conditions; preserve all attempts."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import subprocess
import run_experiment20 as harness

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'runs/comparison5'
IDS = ['770', '781', '788', '792', '244']

def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')

def prepare():
    source = ROOT / 'data/browsecomp-plus/queries/browsecomp_plus_all.tsv'
    lookup = dict(line.split('\t', 1) for line in source.read_text().splitlines() if line.strip())
    rows = [qid + '\t' + lookup[qid] for qid in IDS]
    anchors = ['coordinator of a research group founded in 2009', '61,700 and 61,906',
               'capacity of over 150,000', 'publishing group that was launched in 2010', 'reference number 144']
    for row, anchor in zip(rows, anchors):
        if anchor not in row:
            raise ValueError('Question text verification failed')
    DEST.mkdir(parents=True, exist_ok=True)
    text = '\n'.join(rows) + '\n'
    target = DEST / 'questions.tsv'
    if target.exists() and target.read_text() != text:
        raise ValueError('Frozen questions changed')
    target.write_text(text)
    manifest = {'query_ids': IDS, 'max_distinct_questions': 5, 'initial_agent_runs': 10,
                'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'questions_sha256': hashlib.sha256(text.encode()).hexdigest(),
                'git_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'verification': 'Full dataset texts manually matched to user-supplied questions; anchors checked at launch.'}
    if not (DEST / 'manifest.json').exists(): save(DEST / 'manifest.json', manifest)
    return rows

def report():
    lines = ['# Five trace pairs', '', 'One initial run per condition and question. No automatic retries.', '']
    summary = []
    for qid in IDS:
        lines += [f'## Question {qid}', '']
        prompts = []
        for arm in harness.ARMS:
            unit = DEST / arm / 'queries' / qid
            path = unit / f'{qid}.json'
            if not path.exists():
                lines += [f'- {arm}: missing result; inspect launch log.', '']
                continue
            data = json.loads(path.read_text())
            snapshot = unit / 'prompt_snapshot.json'
            if snapshot.exists(): prompts.append(json.loads(snapshot.read_text()))
            transcript = []
            for raw in sorted((unit / 'raw-events').glob('*.jsonl')):
                for line in raw.read_text().splitlines():
                    event = json.loads(line)
                    if event.get('type') == 'message_end':
                        transcript += ['## Message', '', '```json', json.dumps(event['message'], indent=2), '```', '']
                    elif event.get('type') in ('tool_execution_start', 'tool_execution_end'):
                        transcript += [f"## {event['type']}", '', '```json', json.dumps(event, indent=2), '```', '']
            (unit / 'transcript.md').write_text('\n'.join(transcript))
            (unit / 'answer.json').write_text(json.dumps(data.get('result'), indent=2) + '\n')
            rel = f'{arm}/queries/{qid}'
            lines += [f'- **{arm}**: {data["status"]}; '
                      f'[transcript]({rel}/transcript.md), [answer]({rel}/answer.json), '
                      f'[result]({rel}/{qid}.json), [raw events]({rel}/raw-events/), '
                      f'[prompt]({rel}/prompt_snapshot.json).']
            if arm == 'questions_gambit':
                lines += [f'  [Clues, feedback, expansions, rankings, opening context]({rel}/first_move_audit/); '
                          f'[expansion logs]({rel}/expansion_calls/).']
            summary.append({'query_id': qid, 'arm': arm, 'status': data['status'],
                            'tool_calls': data.get('tool_call_counts'), 'stats': data.get('stats')})
        if len(prompts) == 2:
            equal = all(prompts[0][k] == prompts[1][k] for k in ('user_prompt', 'system_prompt'))
            lines += ['', f'Shared system/user prompts identical: {equal}.']
        lines += ['']
    (DEST / 'TRACE_PAIRS.md').write_text('\n'.join(lines))
    save(DEST / 'summary.json', summary)

def main():
    rows = prepare()
    harness.DEST = DEST
    env = harness.base_env()
    env['PI_SEARCH_AUDIT'] = '1'
    config = {k: env[k] for k in ('MODEL', 'THINKING', 'TIMEOUT_SECONDS', 'PI_BM25_K1', 'PI_BM25_B')}
    config.update(query_ids=IDS, agent_runs=10, concurrency=4, index='indexes/browsecomp-plus-bm25-tevatron',
                  treatment='first_move registration only', audit=True, automatic_retries=False)
    config_path = DEST / 'configuration.json'
    if config_path.exists() and json.loads(config_path.read_text()) != config:
        raise ValueError('Configuration changed')
    save(config_path, config)
    with (DEST / 'bm25.log').open('w') as log:
        server = subprocess.Popen([env['PYTHON'], 'scripts/bm25_server.py', '--index-path', config['index'],
            '--k1', '25', '--b', '1', '--threads', '8', '--transport', 'tcp', '--port', '0'],
            cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=log, text=True)
        try:
            for line in server.stdout:
                try: ready = json.loads(line)
                except ValueError: continue
                if ready.get('type') == 'server_ready': break
            else: raise RuntimeError('BM25 startup failed; see bm25.log')
            env.update(PI_BM25_RPC_HOST=ready['host'], PI_BM25_RPC_PORT=str(ready['port']))
            print('BM25 ready. Running exactly five pairs.', flush=True)
            jobs = [(arm, row) for i, row in enumerate(rows)
                    for arm in (harness.ARMS if i % 2 == 0 else harness.ARMS[::-1])]
            # Never relaunch an interrupted attempt under the same directory.
            for arm, row in jobs:
                qid = row.split('\t', 1)[0]
                unit = DEST / arm / 'queries' / qid
                if (unit / 'launch.log').exists() and not (unit / f'{qid}.json').exists():
                    raise RuntimeError(f'Incomplete previous attempt: {unit}; no automatic retry')
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                futures = [pool.submit(harness.agent_one, arm, row, env) for arm, row in jobs]
                for future in concurrent.futures.as_completed(futures):
                    try: future.result()
                    except Exception as exc: print(f'Run error preserved: {exc}', flush=True)
                    report()
        finally:
            server.terminate()
            server.wait(timeout=20)
            report()
    print('Trace pairs ready: runs/comparison5/TRACE_PAIRS.md', flush=True)

if __name__ == '__main__':
    main()
