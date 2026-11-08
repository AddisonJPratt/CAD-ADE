"""Opt-in: the real local Claude Code CLI, with the user's existing login. Skipped by default.

    MAGIC_REAL_CLAUDE=1 .venv/bin/python -m unittest tests.test_claude_real

Spends model usage on the logged-in account (~1-2 minutes per case). Runs the M0 request
"make the bracket wall 1 mm thicker" through proposal, accept, gates and a saved version,
and separately interrupts a live request and checks the project is unchanged.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / 'evals/run_m0.py'


@unittest.skipUnless(os.environ.get('MAGIC_REAL_CLAUDE') == '1', 'set MAGIC_REAL_CLAUDE=1 to call the real Claude Code CLI')
class RealClaudeCodeTest(unittest.TestCase):
    def run_eval(self, *flags):
        with tempfile.TemporaryDirectory() as tmp:
            done = subprocess.run([sys.executable, str(EVAL), '--project', str(Path(tmp) / 'bracket'), *flags],
                                  capture_output=True, text=True, timeout=600)
            self.assertEqual(done.returncode, 0, done.stdout[-2000:] + done.stderr[-2000:])
            return [json.loads(line) for line in done.stdout.splitlines() if line.startswith('{')]

    def test_wall_one_mm_thicker_passes_gates_and_saves_a_version(self):
        lines = self.run_eval()
        changes = next(l['changes'] for l in lines if 'changes' in l)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]['parameter'], 'thickness')
        self.assertAlmostEqual(changes[0]['new'] - changes[0]['old'], 1.0)
        self.assertEqual(lines[-1]['pass'], True)
        self.assertEqual(lines[-1]['version'], 2)

    def test_interrupt_stops_the_cli_and_leaves_project_unchanged(self):
        # run_m0.py --interrupt asserts the CLI process exited and source, briefs and versions are unchanged.
        result = self.run_eval('--interrupt')[-1]
        self.assertTrue(result['interrupted'])
        self.assertTrue(result['unchanged'])
