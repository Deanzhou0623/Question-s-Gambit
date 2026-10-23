#!/usr/bin/env python3
"""Package sanitized copies of five trace pairs without changing local raw artifacts."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tarfile
import run_comparison5 as runner

ROOT, DEST, IDS = runner.ROOT, runner.DEST, runner.IDS
PUBLIC = DEST / 'public'

def sanitize(text):
    for key, value in os.environ.items():
        if any(word in key.upper() for word in ('API_KEY', 'ACCESS_TOKEN', 'AUTH_TOKEN')) and len(value) > 12:
            text = text.replace(value, '[REDACTED_CREDENTIAL]')
    text = re.sub(r'\bsk-[A-Za-z0-9_-]{20,}', '[REDACTED_CREDENTIAL]', text)
    text = re.sub(r'\bgh[pousr]_[A-Za-z0-9]{20,}', '[REDACTED_CREDENTIAL]', text)
    text = re.sub(r'\borg-[A-Za-z0-9]+', '[REDACTED_ORGANIZATION]', text)
    text = text.replace(str(ROOT), '<workspace>')
    return text

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sanitize(text))

def main():
    for arm in runner.harness.ARMS:
        actual = {p.name for p in (DEST / arm / 'queries').iterdir() if p.is_dir()}
        if actual != set(IDS):
            raise ValueError(f'Unexpected question directories in {arm}: {actual}')
        for qid in IDS:
            if not (DEST / arm / 'queries' / qid / f'{qid}.json').exists():
                raise ValueError(f'Run has not finished: {arm} {qid}')
    runner.report()
    PUBLIC.mkdir(parents=True, exist_ok=True)
    rows = ['# Five paired traces', '',
            'Exactly five questions, two conditions each; one initial attempt per condition.', '',
            'No answer judging or qualitative scoring was run. Completion is not correctness.', '',
            'Rate limiting affected this experiment. Treat latency and failed-run differences as '
            'confounded by API availability; this batch does not establish a method-level performance '
            'advantage. There was one initial attempt per condition, with four concurrent runs at most.', '',
            'Full sanitized artifacts are in each pair archive. Extract it to inspect raw events, '
            'prompts, tool responses, API usage, and first-move audit JSON. '
            'Readable transcripts are also linked directly.', '',
            '| Question | Gambit | Baseline | Complete pair artifacts |',
            '|---|---|---|---|']
    validation = []
    for qid in IDS:
        pair = PUBLIC / qid
        pair.mkdir(exist_ok=True)
        archive = pair / 'traces.tar.gz'
        snapshots, statuses = [], {}
        record = {'query_id': qid}
        with tarfile.open(archive, 'w:gz') as tar:
            for arm in runner.harness.ARMS:
                unit = DEST / arm / 'queries' / qid
                data = json.loads((unit / f'{qid}.json').read_text())
                statuses[arm] = data['status']
                snapshots.append(json.loads((unit / 'prompt_snapshot.json').read_text()))
                calls = [r.get('tool_name') for r in data.get('result', []) if r.get('type') == 'tool_call']
                record[arm] = {'status': data['status'], 'first_tool': calls[0] if calls else None,
                    'first_move_calls': data.get('tool_call_counts', {}).get('first_move', 0),
                    'tool_failures': data.get('stats', {}).get('pi_search_failures', 0)}
                api_errors = []
                for raw in (unit / 'raw-events').glob('*.jsonl'):
                    for line in raw.read_text().splitlines():
                        event = json.loads(line)
                        if event.get('type') == 'message_end':
                            error = event.get('message', {}).get('errorMessage')
                            if error: api_errors.append(sanitize(error))
                record[arm]['api_errors'] = api_errors
                for path in sorted(unit.rglob('*')):
                    if not path.is_file() or path.name == 'answer.json': continue
                    content = sanitize(path.read_text()).encode()
                    info = tarfile.TarInfo(f'{arm}/{path.relative_to(unit)}')
                    info.size = len(content)
                    tar.addfile(info, io.BytesIO(content))
                for name in ('transcript.md', 'answer.md'):
                    write(pair / f'{arm}-{name}', (unit / name).read_text())
        record['shared_prompts_identical'] = all(snapshots[0][k] == snapshots[1][k]
                                                  for k in ('user_prompt', 'system_prompt'))
        record['archive_sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
        validation.append(record)
        rows += [f'| {qid} | [{statuses["questions_gambit"]}]({qid}/questions_gambit-transcript.md) '
                 f'([answer]({qid}/questions_gambit-answer.md)) | '
                 f'[{statuses["pi_serini"]}]({qid}/pi_serini-transcript.md) '
                 f'([answer]({qid}/pi_serini-answer.md)) | [archive]({qid}/traces.tar.gz) |']
    rows += ['', 'Gambit–770 and baseline–244 failed after repeated API token-rate-limit errors and '
             'produced no completed answers. Their partial traces are preserved; no replacement '
             'attempts were run. See validation.json for all final statuses and API errors, including '
             'errors recovered within completed runs.', '',
             'Public copies redact credentials, API organization identifiers, and the local workspace path. '
             'Local raw artifacts remain unchanged. Obsolete answer.json files are omitted: they were '
             'intermediate full-result exports rather than final-answer files. Use answer.md.', '',
             'Each archive includes per-run prompts/configuration and logs. The manifests and configuration '
             'below describe the entire experiment. Agent-call retries within the original runtime, '
             'including recovered API errors, remain visible in the traces.', '',
             '- [Protocol validation](validation.json)', '- [Run summary](summary.json)',
             '- [Configuration](configuration.json)', '- [Manifest](manifest.json)',
             '- [Attribution and license](NOTICE.md)']
    write(PUBLIC / 'TRACE_PAIRS.md', '\n'.join(rows) + '\n')
    write(PUBLIC / 'validation.json', json.dumps(validation, indent=2) + '\n')
    for name in ('summary.json', 'configuration.json', 'manifest.json'):
        write(PUBLIC / name, (DEST / name).read_text())
    print('Packaged exactly five pairs:', PUBLIC)

if __name__ == '__main__':
    main()
