#!/usr/bin/env python3
"""Run a capped, paired BrowseComp-Plus comparison after freezing q20."""
import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'runs/comparison20'
ARMS = ('pi_serini', 'questions_gambit')


def run(command, env, log):
    with (DEST / 'commands.jsonl').open('a') as output:
        output.write(json.dumps({'time': time.time(), 'argv': command, 'log': str(log),
                                 'condition': env.get('PI_SEARCH_FIRST_MOVE_ENABLED')}) + '\n')
    with log.open('w') as output:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT)
    if result.returncode:
        raise RuntimeError(f'Command exited {result.returncode}; see {log}')


def load_subset():
    manifest = json.loads((DEST / 'subset.json').read_text())
    source = DEST / 'q20.tsv'
    if hashlib.sha256(source.read_bytes()).hexdigest() != manifest['subset_sha256']:
        raise ValueError('Frozen subset checksum mismatch')
    rows = [x for x in source.read_text().splitlines() if x.strip()]
    ids = [x.split('\t', 1)[0] for x in rows]
    if len(rows) != 20 or len(set(ids)) != 20 or ids != manifest['query_ids']:
        raise ValueError('Refusing to run: must have exactly the frozen 20 unique questions')
    return manifest, rows


def base_env():
    # The calling shell sources .env. Never print or persist credentials.
    env = os.environ.copy()
    for key in ('OPENAI_API_KEY', 'OPENROUTER_API_KEY'):
        if not env.get(key):
            raise ValueError(f'{key} is required')
    env.update({
        'MODEL': 'openai/gpt-5.5', 'TIMEOUT_SECONDS': '900', 'THINKING': 'medium',
        'PI_BM25_K1': '25', 'PI_BM25_B': '1', 'PI_BM25_THREADS': '8',
        'PYTHON': str(ROOT / '.cache/experiment20/venv/bin/python'),
        'JAVA_HOME': '/opt/homebrew/opt/openjdk@25/libexec/openjdk.jdk/Contents/Home',
        'PI_BIN': str(ROOT / 'node_modules/.bin/pi'),
        'NODE_OPTIONS': f'--import={ROOT}/scripts/experiment20_usage.mjs',
        '_JAVA_OPTIONS': '-Xmx12g -Xms2g -XX:MaxDirectMemorySize=2g',
        'MPLCONFIGDIR': str(ROOT / '.cache/matplotlib'),
    })
    env['PATH'] = env['JAVA_HOME'] + '/bin:' + env['PATH']
    return env


def validate_run(path, arm, require_success=False):
    data = json.loads(path.read_text())
    errors = []
    if require_success and data['status'] != 'completed':
        errors.append('not completed')
    if require_success and data['stats'].get('pi_search_failures', 0):
        errors.append('retrieval tool failure')
    if arm == 'pi_serini' and data['tool_call_counts'].get('first_move', 0):
        errors.append('baseline unexpectedly used first_move')
    if arm == 'questions_gambit' and require_success and not data['tool_call_counts'].get('first_move', 0):
        errors.append('smoke did not exercise first_move')
    if errors:
        raise RuntimeError(f'{path}: {", ".join(errors)}')


def agent_one(arm, row, env):
    qid = row.split('\t', 1)[0]
    unit = DEST / arm / 'queries' / qid
    unit.mkdir(parents=True, exist_ok=True)
    query = unit / 'query.tsv'
    query.write_text(row + '\n')
    result = unit / f'{qid}.json'
    if not result.exists():
        local = dict(env, OUTPUT_DIR=str(unit), PI_SEARCH_FIRST_MOVE_ENABLED='0' if arm == 'pi_serini' else '1',
                     EXPERIMENT_USAGE_FILE=str(unit / 'api_usage.jsonl'))
        command = [str(ROOT / 'node_modules/.bin/tsx'), 'src/orchestration/run_pi_benchmark.ts',
                   '--benchmark', 'browsecomp-plus', '--querySet', 'q50', '--query', str(query), '--limit', '1',
                   '--model', env['MODEL'], '--timeoutSeconds', '900', '--thinking', 'medium',
                   '--pi', env['PI_BIN'], '--outputDir', str(unit)]
        run(command, local, unit / 'launch.log')
    validate_run(result, arm)
    merged = DEST / arm / 'merged'
    merged.mkdir(exist_ok=True)
    shutil.copy2(result, merged / result.name)
    print(f'{arm} {qid}: {json.loads(result.read_text())["status"]}', flush=True)


def judge(arm, env):
    arm_dir = DEST / arm
    allowed = set(json.loads((DEST / 'subset.json').read_text())['query_ids'])
    actual = {x.stem for x in (arm_dir / 'merged').glob('*.json')}
    if not actual or not actual <= allowed or len(actual) > 20:
        raise ValueError('Judge input violates the frozen 20-question cap')
    local = dict(env, EXPERIMENT_USAGE_FILE=str(arm_dir / 'judge_api_usage.jsonl'))
    command = [str(ROOT / 'node_modules/.bin/tsx'), 'scripts/judge_arm_concurrent.ts',
               '--arm-dir', str(arm_dir), '--query-file', str(DEST / 'q20.tsv'),
               '--benchmark', 'browsecomp-plus', '--judge-model', 'openai-codex/gpt-5.3-codex',
               '--judge-mode', 'gold-answer', '--timeout-seconds', '180', '--concurrency', '4',
               '--eval-dir', str(arm_dir / 'evaluation'), '--no-summary']
    run(command, local, arm_dir / 'judge.log')
    for label, name in [('evidence', 'qrel_evidence.txt'), ('gold', 'qrel_gold.txt')]:
        command = [str(ROOT / 'node_modules/.bin/tsx'), 'scripts/recall_against_qrels.ts',
                   '--perQueryDir', str(arm_dir / 'evaluation/per-query'),
                   '--qrelsPath', str(ROOT / 'data/browsecomp-plus/qrels' / name),
                   '--label', label, '--outputPath', str(arm_dir / f'{label}_recall.json')]
        run(command, local, arm_dir / f'{label}_recall.log')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['smoke', 'remaining'])
    args = parser.parse_args()
    manifest, rows = load_subset()
    env = base_env()
    if args.stage == 'remaining':
        marker = json.loads((DEST / 'smoke_passed.json').read_text())
        if marker['subset_sha256'] != manifest['subset_sha256']:
            raise ValueError('Smoke gate belongs to a different subset')
        rows = rows[1:]
    else:
        rows = rows[:1]
    public_keys = ['MODEL', 'TIMEOUT_SECONDS', 'THINKING', 'PI_BM25_K1', 'PI_BM25_B',
                   'PI_BM25_THREADS', 'JAVA_HOME', 'PYTHON', 'PI_BIN', 'NODE_OPTIONS', '_JAVA_OPTIONS']
    config = {k: env[k] for k in public_keys}
    config.update({'prompt': 'plain_minimal, byte-identical shared template',
                   'treatment': 'first_move registration only', 'agent_concurrency': 4,
                   'judge': 'gpt-5.3-codex', 'judge_mode': 'gold-answer', 'judge_timeout_seconds': 180,
                   'judge_concurrency': 4, 'index': 'indexes/browsecomp-plus-bm25-tevatron',
                   'subset_sha256': manifest['subset_sha256'], 'max_distinct_questions': 20})
    config_path = DEST / 'configuration.json'
    if config_path.exists() and json.loads(config_path.read_text()) != config:
        raise ValueError('Configuration changed between stages')
    config_path.write_text(json.dumps(config, indent=2) + '\n')
    server_log = (DEST / f'bm25-{args.stage}.log').open('w')
    command = [env['PYTHON'], 'scripts/bm25_server.py', '--index-path', config['index'],
               '--k1', '25', '--b', '1', '--threads', '8', '--transport', 'tcp', '--port', '0']
    server = subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=server_log, text=True)
    try:
        while True:
            line = server.stdout.readline()
            if not line:
                raise RuntimeError(f'BM25 server failed; see bm25-{args.stage}.log')
            try:
                ready = json.loads(line)
            except ValueError:
                continue
            if ready.get('type') == 'server_ready':
                break
        env.update(PI_BM25_RPC_HOST=ready['host'], PI_BM25_RPC_PORT=str(ready['port']))
        # Alternating condition order reduces a systematic startup/order advantage.
        jobs = [(arm, row) for i, row in enumerate(rows) for arm in (ARMS if i % 2 == 0 else ARMS[::-1])]
        with concurrent.futures.ThreadPoolExecutor(max_workers=4 if args.stage == 'remaining' else 1) as pool:
            futures = [pool.submit(agent_one, arm, row, env) for arm, row in jobs]
            for future in concurrent.futures.as_completed(futures):
                future.result()
        if args.stage == 'smoke':
            for arm in ARMS:
                validate_run(DEST / arm / 'merged' / f'{manifest["smoke_query_id"]}.json', arm, require_success=True)
            snapshots = [json.loads((DEST / arm / 'queries' / manifest['smoke_query_id'] / 'prompt_snapshot.json').read_text())
                         for arm in ARMS]
            for field in ('user_prompt', 'system_prompt'):
                if snapshots[0][field] != snapshots[1][field]:
                    raise RuntimeError(f'Smoke conditions have different {field}')
        for arm in ARMS:
            judge(arm, env)
        if args.stage == 'smoke':
            for arm in ARMS:
                qid = manifest['smoke_query_id']
                validate_run(DEST / arm / 'merged' / f'{qid}.json', arm, require_success=True)
                evaluation = json.loads((DEST / arm / 'evaluation/per-query' / f'{qid}_eval.json').read_text())
                if evaluation.get('judge_result', {}).get('correct') not in (True, False):
                    raise RuntimeError(f'{arm}: judge smoke must produce a valid correctness result')
            (DEST / 'smoke_passed.json').write_text(json.dumps({'subset_sha256': manifest['subset_sha256']}) + '\n')
        print(f'{args.stage}: complete', flush=True)
    finally:
        server.terminate()
        server.wait(timeout=20)
        server_log.close()


if __name__ == '__main__':
    main()
