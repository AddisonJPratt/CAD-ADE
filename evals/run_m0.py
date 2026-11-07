"""Opt-in real Claude Code M0 evaluation; never runs in the ordinary test suite.

    .venv/bin/python evals/run_m0.py --project /tmp/magic-m0-demo

Creates a wall-bracket project if absent; asks Claude for the change, accepts its
proposal, runs every gate and saves a version. Uses the existing CLI login.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.api import Engine, Handler
from engine.claude_agent import ClaudeCodeAgent
from engine.versions import create_project, list_versions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--interrupt', action='store_true', help='Verify process cancellation without accepting')
    parser.add_argument('--request', default='Make the bracket wall 1 mm thicker')
    args = parser.parse_args()
    project = args.project.resolve()
    if not project.exists():
        create_project(project, ROOT / 'designs/wall_bracket.py')
    handler = Handler.__new__(Handler)
    handler.engine = Engine(agent=ClaudeCodeAgent())
    _, pending = handler.post_proposal({'project':str(project), 'message':args.request,
                                        'selection':{'design':'wall_bracket.py'}})
    proposal = handler.engine.proposals[pending['id']]
    session = proposal['session']
    if args.interrupt:
        original = {str(p):p.read_bytes() for folder in ('designs','briefs') for p in (project / folder).glob('*') if p.is_file()}
        versions = [v['id'] for v in list_versions(project)]
        deadline = time.monotonic() + 10
        while proposal['process'] is None and time.monotonic() < deadline:
            time.sleep(.05)
        process = proposal['process']
        if process is None:
            raise RuntimeError('Claude Code did not start')
        handler.control_agent(pending['id'], 'interrupt')
        assert session.wait_for('interrupted',10), session.error
        assert process.poll() is not None
        assert all(Path(p).read_bytes() == data for p,data in original.items())
        assert [v['id'] for v in list_versions(project)] == versions
        handler.reject_proposal(pending['id'])
        print(json.dumps({'interrupted':True,'unchanged':True,'project':str(project)}),flush=True)
        return 0
    sent = 0
    while session.state not in ('ready','error'):
        with session.changed:
            session.changed.wait(timeout=1)
            events = session.events[sent:]
            sent = len(session.events)
        for event in events:
            print(json.dumps(event),flush=True)
    if session.state == 'error':
        print(session.error, file=sys.stderr)
        return 1
    print(json.dumps(handler.proposal_summary(proposal)),flush=True)
    _, result = handler.accept_proposal(pending['id'], {'wait':True})
    passed = result['run']['status'] == 'done' and result['run']['verdict']['pass']
    print(json.dumps({'pass':passed,'version':list_versions(project)[0]['number'],
                      'project':str(project)}),flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
