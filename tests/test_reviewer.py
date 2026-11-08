"""The reviewer agent in the loop (#28), at the engine seam with the scripted agents.

good_two_parts: size (20, 10..30), gap (1, 0.5..2). The scripted reviewer fails a change that
puts a setting at the end of its range and names the range midpoint as its top fix.
"""
import json
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from engine.api import Engine, make_server
from engine.reviewer import ClaudeCodeReviewer, Reviewer, ScriptedFakeReviewer, verdict_of
from engine.versions import create_project, list_versions
from tests import test_parameters as parameter_cases

ROOT = parameter_cases.ROOT
FIXTURE = ROOT / 'tests/fixtures/good_two_parts.py'


class ReviewLoopTest(unittest.TestCase):
    request = parameter_cases.ParameterApiTest.request
    tearDown = parameter_cases.ParameterApiTest.tearDown
    reviewer = None

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = create_project(Path(self.tmp.name) / 'project', FIXTURE)
        self.engine = Engine(reviewer=self.reviewer)
        self.server = make_server(port=0, engine=self.engine)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def propose(self, message):
        status, pending = self.request('POST', '/proposals', {'project': str(self.project), 'message': message})
        self.assertEqual(status, 202, pending)
        return self.ready(pending['id'])

    def ready(self, ident):
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            state = self.request('GET', '/proposals/' + ident)[1]
            if state['state'] in ('ready', 'error'):
                self.assertEqual(state['state'], 'ready', state.get('error'))
                return state
            time.sleep(.1)
        self.fail('proposal never became ready')

    def accept(self, ident):
        status, accepted = self.request('POST', f'/proposals/{ident}/accept', {'wait': True, 'samples': 6})
        self.assertEqual(status, 200, accepted)
        run = self.engine.get(accepted['run']['id'])
        return run, [e['type'] for e in run.events]


class ScriptedReviewLoopTest(ReviewLoopTest):
    def test_passing_review_is_shown_and_the_designer_edit_is_streamed(self):
        proposal = self.propose('size 24')
        events = self.engine.proposals[proposal['id']]['session'].events
        edit = next(e for e in events if e['type'] == 'edit')
        self.assertEqual((edit['file'], edit['changes']), ('designs/good_two_parts.py', [{'parameter': 'size', 'old': 20.0, 'new': 24.0}]))
        run, kinds = self.accept(proposal['id'])
        self.assertTrue(run.verdict['pass'])
        self.assertEqual(run.status, 'done')
        self.assertLess(kinds.index('review_started'), kinds.index('review_finished'))
        self.assertIn('review_note', kinds)
        self.assertNotIn('sent_back', kinds)
        self.assertTrue(run.review['pass'])
        self.assertEqual(run.review['band'], 'adopt-ready')
        self.assertEqual(self.request('GET', f'/runs/{run.id}')[1]['review']['total'], run.review['total'])

    def test_failing_review_sends_the_top_fix_back_once_and_the_owner_still_approves(self):
        run, kinds = self.accept(self.propose('size 30')['id'])     # 30 is the end of size's range
        self.assertFalse(run.review['pass'])
        self.assertEqual(run.review['fixes'][0]['parameter'], 'size')
        self.assertEqual(list_versions(self.project)[0]['review'],                 # kept with the version
                         {'total': run.review['total'], 'band': 'rework', 'pass': False})
        sent = next(e for e in run.events if e['type'] == 'sent_back')
        self.assertTrue(sent['message'].startswith('size to 20.0'))
        back = self.ready(sent['proposal'])                         # a proposal, not an applied change
        self.assertEqual(back['origin'], {'run': run.id, 'round': 1})
        self.assertEqual(back['changes'], [{'parameter': 'size', 'old': 30.0, 'new': 20.0}])
        self.assertEqual(len(list_versions(self.project)), 2)        # nothing saved until the owner keeps it
        again, kinds = self.accept(back['id'])
        self.assertTrue(again.review['pass'])
        self.assertNotIn('sent_back', kinds)

    def test_a_second_failing_review_lists_its_fixes_without_sending_back(self):
        back_id = None
        run, _ = self.accept(self.propose('size 30')['id'])
        back_id = next(e for e in run.events if e['type'] == 'sent_back')['proposal']
        self.engine.reviewer = AlwaysFails()
        again, kinds = self.accept(self.ready(back_id)['id'])
        self.assertFalse(again.review['pass'])
        self.assertIn('review_kept', kinds)
        self.assertNotIn('sent_back', kinds)


class AlwaysFails(Reviewer):
    def review(self, context, emit):
        return verdict_of({'scores': {'looks_like_the_thing': 1, 'detail': 1, 'dimensions': 1, 'proportion': 1, 'print_intent': 1},
                           'fixes': [{'text': 'make it a different object'}], 'good': ''})


class Unavailable(Reviewer):
    def review(self, context, emit):
        raise RuntimeError('reviewer offline')


class UnavailableReviewerTest(ReviewLoopTest):
    reviewer = Unavailable()

    def test_an_unavailable_reviewer_leaves_the_design_unreviewed_not_failed(self):
        run, kinds = self.accept(self.propose('size 24')['id'])
        self.assertEqual(run.status, 'done')
        self.assertTrue(run.verdict['pass'])
        self.assertIsNone(run.review)
        self.assertIn('review_error', kinds)
        self.assertIsNone(list_versions(self.project)[0]['review'])               # labelled unreviewed


class ClaudeReviewerTest(ReviewLoopTest):
    def setUp(self):
        self.argv_file = Path(tempfile.mkdtemp()) / 'argv.json'
        self.prompt_file = self.argv_file.with_name('prompt.txt')
        self.reviewer = ClaudeCodeReviewer(command=[sys.executable, str(ROOT / 'tests/fixtures/claude_stream.py'),
                                                    '--argv-file', str(self.argv_file), '--prompt-file', str(self.prompt_file)])
        super().setUp()

    def test_claude_reviewer_is_read_only_independent_and_reports_usage(self):
        run, kinds = self.accept(self.propose('size 24')['id'])
        self.assertTrue(run.review['pass'])
        self.assertEqual(run.review['total'], 20)
        notes = [e['message'] for e in run.events if e['type'] == 'review_note']
        self.assertIn('Reading report.json', notes)
        usage = next(e for e in run.events if e['type'] == 'usage')
        self.assertEqual((usage['agent'], usage['tokens'], usage['cost_usd']), ('reviewer', 1500, 0.0123))
        argv = json.loads(self.argv_file.read_text())['argv']
        self.assertEqual(argv[argv.index('--tools') + 1], 'Read,Glob,Grep')       # cannot edit the design
        self.assertIn('--no-session-persistence', argv)                           # a fresh context every time
        prompt = self.prompt_file.read_text()
        self.assertIn('magic-cad-reviewer/SKILL.md', prompt)
        self.assertIn('report.json', prompt)
        self.assertNotIn('size 24', prompt)                                       # never the designer's conversation


if __name__ == '__main__':
    unittest.main()
