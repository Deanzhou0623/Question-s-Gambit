import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import contextlib
import io

spec = importlib.util.spec_from_file_location('prepare', Path(__file__).parents[1] / 'scripts/prepare_experiment20.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
runner_spec = importlib.util.spec_from_file_location('runner', Path(__file__).parents[1] / 'scripts/run_experiment20.py')
runner = importlib.util.module_from_spec(runner_spec)
runner_spec.loader.exec_module(runner)
report_spec = importlib.util.spec_from_file_location('report', Path(__file__).parents[1] / 'scripts/report_experiment20.py')
reporter = importlib.util.module_from_spec(report_spec)
report_spec.loader.exec_module(reporter)

class SubsetTest(unittest.TestCase):
    def setUp(self):
        self.stdout = contextlib.redirect_stdout(io.StringIO())
        self.stdout.__enter__()

    def tearDown(self):
        self.stdout.__exit__(None, None, None)

    def test_subset_is_unique_stable_and_order_independent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'q50.tsv'
            rows = [f'{i}\tSynthetic question {i}' for i in range(50)]
            source.write_text('\n'.join(rows))
            module.prepare(source, root / 'one', 42)
            source.write_text('\n'.join(reversed(rows)))
            module.prepare(source, root / 'two', 42)
            self.assertEqual((root / 'one/q20.tsv').read_bytes(), (root / 'two/q20.tsv').read_bytes())
            manifest = json.loads((root / 'one/subset.json').read_text())
            self.assertEqual(len(set(manifest['query_ids'])), 20)
            self.assertEqual(len((root / 'one/smoke.tsv').read_text().splitlines()), 1)
            self.assertEqual(len((root / 'one/remaining.tsv').read_text().splitlines()), 19)

    def test_rejects_non_q50_source_and_subset_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'q50.tsv'
            source.write_text('1\tSynthetic question\n')
            with self.assertRaises(ValueError): module.prepare(source, root / 'out')
            source.write_text('\n'.join(f'{i}\tSynthetic {i}' for i in range(50)))
            module.prepare(source, root / 'out', 42)
            with self.assertRaises(ValueError): module.prepare(source, root / 'out', 43)

    def test_runner_rejects_changed_or_oversized_subset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'q50.tsv'
            source.write_text('\n'.join(f'{i}\tSynthetic {i}' for i in range(50)))
            module.prepare(source, root / 'out', 42)
            previous = runner.DEST
            try:
                runner.DEST = root / 'out'
                manifest, rows = runner.load_subset()
                self.assertEqual(len(rows), 20)
                target = runner.DEST / 'q20.tsv'
                target.write_text(target.read_text() + '100\tExtra synthetic question\n')
                with self.assertRaises(ValueError): runner.load_subset()
                import hashlib
                manifest['subset_sha256'] = hashlib.sha256(target.read_bytes()).hexdigest()
                manifest['query_ids'].append('100')
                (runner.DEST / 'subset.json').write_text(json.dumps(manifest))
                with self.assertRaises(ValueError): runner.load_subset()
            finally:
                runner.DEST = previous

    def test_report_keeps_failures_in_denominator_and_includes_all_costs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / 'runs/comparison20'
            destination.mkdir(parents=True)
            ids = [str(i) for i in range(20)]
            (destination / 'subset.json').write_text(json.dumps({'query_ids': ids, 'seed': 42}))
            qrels = root / 'data/browsecomp-plus/qrels'
            qrels.mkdir(parents=True)
            for name in ['qrel_evidence.txt', 'qrel_gold.txt']:
                (qrels / name).write_text('\n'.join(f'{i} 0 123 1' for i in ids))
            for arm in reporter.ARMS:
                base = destination / arm
                (base / 'merged').mkdir(parents=True)
                (base / 'evaluation/per-query').mkdir(parents=True)
                unit = base / 'queries/0'
                (unit / 'raw-events').mkdir(parents=True)
                (base / 'merged/0.json').write_text(json.dumps({'status': 'completed', 'surfaced_docids': ['123'],
                    'stats': {'tool_calls_total': 2, 'elapsed_seconds': 3}, 'result': []}))
                (base / 'evaluation/per-query/0_eval.json').write_text(json.dumps({'judge_result': {'correct': True, 'parse_error': False}}))
                (unit / 'raw-events/0.jsonl').write_text(json.dumps({'type': 'message_end', 'message': {'role': 'assistant', 'usage': {'cost': {'total': 0.1}}}}))
                (unit / 'api_usage.jsonl').write_text(json.dumps({'reported_cost_usd': 0.02}))
                (base / 'judge_api_usage.jsonl').write_text(json.dumps({'estimated_cost_usd': 0.01}))
            previous = reporter.ROOT, reporter.DEST
            try:
                reporter.ROOT, reporter.DEST = root, destination
                reporter.main()
                report = json.loads((destination / 'comparison.json').read_text())
                for summary in report['summary'].values():
                    self.assertEqual(summary['accuracy_pct_all_20'], 5)
                    self.assertEqual(summary['evidence_surfaced_macro_pct'], 5)
                    self.assertEqual(summary['questions_with_failures'], 19)
                    self.assertAlmostEqual(summary['total_cost_usd'], 0.13)
                self.assertEqual(len(report['per_question']), 40)
            finally:
                reporter.ROOT, reporter.DEST = previous

if __name__ == '__main__': unittest.main()
