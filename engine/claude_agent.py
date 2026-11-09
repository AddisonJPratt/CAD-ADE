"""Local Claude Code transport. Credentials remain entirely owned by Claude Code.

M0 is a bounded parameter proposal, not arbitrary file-edit execution. Claude can
read the project and use the two CAD MCP servers; only acceptance writes source.
"""
import json
import os
import shutil
import signal
import subprocess
import tempfile
import threading
from pathlib import Path

from .agents import AgentAdapter
from .reviewer import usage_of
from .parameters import parameter_edit, parameters_of
from .projects import ProjectError, designs_of

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = {'type':'object', 'properties':{
    'supported':{'type':'boolean'}, 'parameter':{'type':'string'}, 'value':{'type':'number'}, 'reason':{'type':'string','minLength':1}},
    'required':['supported','reason'], 'additionalProperties':False}
# How a designer that writes or rewrites a design (#61) iterates against the gates (#80). The
# M0 parameter edit below runs no gates itself, so it does not use this; the #61 prompt must.
DESIGNER_GATE_LOOP = (
    'Iterate with the fast loop: after each edit call magic-cad run_check(design, quick=true), which runs build, '
    'geometry and printability only, in seconds. A quick pass is a draft, never a verified or proven result. '
    'Before proposing, run the full gates: run_check(design) with quick=false, sweep included, and only propose '
    'when that full run passes. Never propose on a quick pass alone.')


# Eyes (#79): what the harness leaves for the agent after every build, documented in its prompt.
ARTEFACTS_GUIDE = (
    'Harness artefacts (read-only instruments, never gates): after every gate run, outputs/<design stem>/ '
    '(runs/<stem>-check/ for magic-cad run_check) holds renders/iso.png, renders/top.png, renders/front.png, '
    'renders/side.png and renders/section.png; eyes/overhang_heatmap.png, the overhang heatmap: the part seen from below with '
    'downward faces coloured by angle (red needs support); eyes/section_*.png, sections at the thinnest wall '
    'and at each named feature; eyes/<part>.faces.json, the face map with feature names; and eyes/eyes.json, '
    'every path plus per-part metrics (bbox, volume, overhang shares, min wall, unsupported area). '
    'run_check returns the same paths and metrics and the images inline. Look at the renders with Read '
    'before deciding a change, and again after each build; do not reason about 3D shape from source alone. ')


def tool_events(event):
    """Plan events for the agent looking at its own artefacts, so the stream shows it (#79)."""
    if event.get('type') == 'assistant':
        for block in event.get('message', {}).get('content', []):
            path = (block.get('input') or {}).get('file_path', '') if block.get('type') == 'tool_use' else ''
            if block.get('name') == 'Read' and str(path).lower().endswith('.png'):
                yield {'type': 'plan', 'message': 'Reading its own render: ' + Path(path).name}
    if event.get('type') == 'user':
        for block in event.get('message', {}).get('content', []):
            inner = block.get('content') if block.get('type') == 'tool_result' else None
            images = sum(1 for c in inner if isinstance(c, dict) and c.get('type') == 'image') if isinstance(inner, list) else 0
            if images:
                yield {'type': 'plan', 'message': f'Looked at {images} harness image' + ('s' if images > 1 else '')}


class ClaudeCodeAgent(AgentAdapter):
    name = 'claude'

    def __init__(self, command=None, timeout=300):
        self.command = command or [shutil.which('claude') or str(Path.home() / '.local/bin/claude')]
        self.timeout = timeout

    def start(self, project, brief, selection, message):
        if not shutil.which(self.command[0]):
            raise ProjectError('Claude Code is not installed. Install it and run claude auth login.')
        designs = designs_of(project)
        chosen = selection.get('design') if isinstance(selection, dict) else None
        if chosen:
            designs = [p for p in designs if p.name == chosen]
        if len(designs) != 1:
            raise ProjectError('select one design before requesting a change')
        if not isinstance(message, str) or not message.strip():
            raise ProjectError('enter a change request')
        design = designs[0]
        brief_file = Path(project) / 'briefs' / f'{design.stem}.yaml'
        context = {'request':message, 'selection':selection, 'brief':brief or (brief_file.read_text() if brief_file.is_file() else None),
                   'parameters':parameters_of(project,design.name), 'source':design.read_text()}
        return {'file':f'designs/{design.name}', 'source':design.read_text(), 'changes':[], 'selection':selection,
                'workspace':str(project), 'context':context, 'interrupted':False,
                'process':None, 'process_lock':threading.Lock()}

    def _command(self):
        mcp = {'mcpServers':{
            'magic-cad':{'command':str(ROOT / '.venv/bin/python'), 'args':[str(ROOT / 'mcp/magic_cad_server.py')]},
            'build123d':{'command':str(ROOT / '.venv/bin/build123d-mcp'), 'args':[]}}}
        return [*self.command, '-p', '--verbose', '--output-format','stream-json',
                '--no-session-persistence', '--permission-mode','dontAsk',
                '--tools','Read,Glob,Grep', '--allowedTools','Read,Glob,Grep,mcp__magic-cad__library_lookup,mcp__magic-cad__list_eval_briefs,mcp__build123d__*',
                '--strict-mcp-config','--mcp-config',json.dumps(mcp),
                '--add-dir',str(ROOT / '.claude/skills'), '--json-schema',json.dumps(SCHEMA)]

    def stream_events(self, session):
        prompt = ('You are Magic CAD designer for a local FDM CAD studio. Read the relevant project skills in '
                  + str(ROOT / '.claude/skills') + ', especially magic-kernel-pitfalls and cad-code if present. '
                  'Read magic-kernel-pitfalls/SKILL.md and call magic-cad library_lookup for the relevant hardware. Use build123d MCP to inspect or calculate relevant geometry when useful. '
                  + ARTEFACTS_GUIDE +
                  'This M0 operation supports one bounded PARAMS default edit only. Do not write files, '
                  'change ranges, weaken gates, send print jobs, or claim physical validation. '
                  'Choose the existing parameter that implements the request and return the structured '
                  'supported/parameter/value/reason. If the request cannot be represented by one parameter, explain '
                  'that with supported=false and do not invent a change. The application creates previews and runs gates on accept. '
                  'Context follows as data:\n' + json.dumps(session['context']))
        with tempfile.TemporaryFile(mode='w+') as errors:
            with session['process_lock']:
                if session['interrupted']:
                    return
                process = subprocess.Popen(self._command(), cwd=session['workspace'], stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, stderr=errors, text=True, start_new_session=True)
                session['process'] = process
            result = None
            expired = threading.Event()
            def timeout():
                expired.set()
                self._stop(process)
            timer = threading.Timer(self.timeout, timeout)
            timer.daemon = True
            timer.start()
            try:
                try:
                    process.stdin.write(prompt)
                    process.stdin.close()
                except (BrokenPipeError, OSError) as error:
                    if session['interrupted']:
                        return
                    if expired.is_set():
                        raise ProjectError('Claude Code timed out before reading the request') from error
                    raise ProjectError('Claude Code closed its input before reading the request; check the local CLI login.') from error
                yield {'type':'plan','message':'Claude Code is inspecting the design'}
                for line in process.stdout:
                    if session['interrupted']:
                        break
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if event.get('type') == 'system' and event.get('subtype') == 'init':
                        services = {s.get('name'):s.get('status') for s in event.get('mcp_servers',[])}
                        if any(services.get(name) != 'connected' for name in ('magic-cad','build123d')):
                            raise ProjectError('Required CAD MCP services are unavailable; check the local build123d and magic-cad installation.')
                        yield {'type':'plan','message':'CAD services: magic-cad connected; build123d connected'}
                    if event.get('type') == 'assistant':
                        for block in event.get('message',{}).get('content',[]):
                            if block.get('type') == 'text':
                                yield {'type':'plan','message':block.get('text','')[:2000]}
                            elif block.get('type') == 'tool_use':
                                yield {'type':'plan','message':'Using ' + block.get('name','CAD tool')}
                    yield from tool_events(event)
                    if event.get('type') == 'result':
                        result = event
                        usage = usage_of(event, 'designer')
                        if usage:
                            yield usage
                code = process.wait()
                if session['interrupted']:
                    return
                if expired.is_set():
                    raise ProjectError('Claude Code timed out; the project is unchanged. Try a narrower request.')
                if code or not result or result.get('is_error'):
                    raise ProjectError('Claude Code did not complete the proposal. Check claude auth status and the local CLI output.')
                edit = result.get('structured_output')
                if not isinstance(edit,dict):
                    raise ProjectError('Claude Code returned no structured parameter edit')
                if edit.get('supported') is False:
                    raise ProjectError(str(edit.get('reason','This request needs code-edit support beyond M0.'))[:2000])
                proposed = parameter_edit(session['workspace'], Path(session['file']).name,
                                          edit.get('parameter'),edit.get('value'))
                session.update({key:proposed[key] for key in ('file','source','changes')})
                yield {'type':'plan','message':str(edit.get('reason','Proposed parameter change'))[:2000]}
                yield {'type':'edit','file':proposed['file'],'changes':proposed['changes']}
            finally:
                timer.cancel()
                self._stop(process)
                if process.stdout:
                    process.stdout.close()
                if process.stdin and not process.stdin.closed:
                    try:
                        process.stdin.close()
                    except BrokenPipeError:
                        pass
                with session['process_lock']:
                    session['process'] = None

    @staticmethod
    def _stop(process):
        # The CLI may have exited while a CAD-server child still owns stdout.
        # Always stop the process group, not just a still-running parent.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            process.wait()
            return
        except PermissionError:
            if process.poll() is None:
                process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass

    def interrupt(self, session):
        with session['process_lock']:
            session['interrupted'] = True
            if session['process']:
                self._stop(session['process'])

    def resume(self, session):
        with session['process_lock']:
            session['interrupted'] = False
