import ast
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('proof_server', Path(__file__).resolve().parents[1] / 'server.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)


class ProofTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old = p.DATA, p.BRIEFS, p.PRINT_LOG
        p.DATA, p.BRIEFS, p.PRINT_LOG = self.root / 'data', self.root / 'briefs', self.root / 'PRINT_LOG.md'
        self.form = {'object': 'Pump <script>', 'shape': 'round', 'diameter': '42', 'length': '200', 'mount': 'screws', 'material': 'PETG'}

    def tearDown(self):
        p.DATA, p.BRIEFS, p.PRINT_LOG = self.old
        self.temp.cleanup()

    def test_generated_design_uses_requested_value_and_matching_brief(self):
        meta, dest, design, brief_path = p.prepare(self.form)
        tree = ast.parse(design.read_text())
        params = ast.literal_eval(next(n.value for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'PARAMS' for t in n.targets)))
        self.assertEqual(params['barrel_dia'][0], 42)
        brief = json.loads(brief_path.read_text())
        self.assertEqual(brief['params']['barrel_dia']['value'], 42)
        self.assertEqual(meta['readings']['length'], 200)
        self.assertNotIn('Pump <script>', design.read_text())
        self.assertIn('Pump &lt;script&gt;', p.result_html({**meta, 'status': 'passed'}))

    def test_finite_range_validation(self):
        for value in ('nan', 'inf', '-1', '51'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                p.prepare({**self.form, 'diameter': value})

    def test_only_complete_success_exports_and_feedback_once(self):
        meta, dest, design, brief = p.prepare(self.form)
        report = {'pass': True, 'gates': [{'name': name, 'status': 'PASS'} for name in p.GATES], 'exports':['holder_clip.stl']}
        out = dest / 'run'; out.mkdir(); (out / 'holder_clip.stl').write_bytes(b'stl')
        (out / 'report.json').write_text(json.dumps(report))
        with patch.object(p.subprocess, 'run') as run:
            run.return_value.returncode = 0
            p.run_make(meta, dest, design, brief)
        self.assertEqual(meta['status'], 'passed')
        p.feedback(meta['id'], 'too_tight')
        self.assertAlmostEqual(json.loads((p.DATA / 'profile.json').read_text())['adjustments_mm']['holder_clip'], .2)
        with self.assertRaises(ValueError): p.feedback(meta['id'], 'too_tight')
        self.assertEqual(len((p.DATA / 'outcomes.jsonl').read_text().splitlines()), 1)
        self.assertIn('too tight', p.PRINT_LOG.read_text().lower())

    def test_stale_and_out_of_bounds_outcomes_are_recorded_without_adjustment(self):
        first, first_dest, _, _ = p.prepare(self.form)
        second, second_dest, _, _ = p.prepare(self.form)
        for meta, dest in ((first, first_dest), (second, second_dest)):
            meta['status'] = 'passed'
            p.write_json(dest / 'make.json', meta)
        p.feedback(first['id'], 'too_tight')
        stale = p.feedback(second['id'], 'too_tight')['outcome']
        self.assertEqual(stale['adjustment_mm'], 0)
        self.assertTrue(stale['review_needed'])
        self.assertAlmostEqual(json.loads((p.DATA / 'profile.json').read_text())['adjustments_mm']['holder_clip'], .2)
        self.assertEqual(len((p.DATA / 'outcomes.jsonl').read_text().splitlines()), 2)

    def test_reconciles_durable_event_after_interrupted_materialization(self):
        meta, dest, _, _ = p.prepare(self.form)
        meta['status'] = 'passed'; p.write_json(dest / 'make.json', meta)
        p.feedback(meta['id'], 'too_tight')
        (p.DATA / 'profile.json').unlink()
        (p.DATA / 'outcomes.jsonl').unlink()
        p.reconcile_events()
        p.reconcile_events()
        self.assertAlmostEqual(json.loads((p.DATA / 'profile.json').read_text())['adjustments_mm']['holder_clip'], .2)
        self.assertEqual(len((p.DATA / 'outcomes.jsonl').read_text().splitlines()), 1)
        self.assertEqual(p.PRINT_LOG.read_text().count('magic-proof:' + meta['id']), 1)

    def test_not_run_never_releases_export(self):
        meta, dest, design, brief = p.prepare(self.form)
        out = dest / 'run'; out.mkdir(); (out / 'holder_clip.stl').write_bytes(b'stl')
        report = {'pass': True, 'gates': [{'name': n, 'status': 'NOT RUN' if n == 'Sweep' else 'PASS'} for n in p.GATES], 'exports':['holder_clip.stl']}
        (out / 'report.json').write_text(json.dumps(report))
        with patch.object(p.subprocess, 'run') as run:
            run.return_value.returncode = 0
            p.run_make(meta, dest, design, brief)
        self.assertEqual(meta['status'], 'failed')
        with self.assertRaises(ValueError): p.feedback(meta['id'], 'perfect')

if __name__ == '__main__': unittest.main()
