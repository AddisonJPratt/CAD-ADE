"""Local subprocess fixture for Claude Code's stream-json transport; no model calls."""
import json
import sys
import time
import os
from pathlib import Path

if '--pid-file' in sys.argv:
    Path(sys.argv[sys.argv.index('--pid-file') + 1]).write_text(str(os.getpid()))
if '--pause-before-read' in sys.argv:
    time.sleep(100)
prompt = sys.stdin.read()
if '--prompt-file' in sys.argv:  # so a test can assert what the engine sent the CLI
    Path(sys.argv[sys.argv.index('--prompt-file') + 1]).write_text(prompt)
if '--argv-file' in sys.argv:  # the CLI arguments and auth-related environment the app passed
    auth = {k: v for k, v in os.environ.items() if k.startswith(('ANTHROPIC', 'CLAUDE'))}
    Path(sys.argv[sys.argv.index('--argv-file') + 1]).write_text(json.dumps({'argv': sys.argv[1:], 'auth_env': auth}))
build123d = 'failed' if '--mcp-down' in sys.argv else 'connected'
print(json.dumps({'type':'system', 'subtype':'init', 'mcp_servers':[
    {'name':'magic-cad','status':'connected'}, {'name':'build123d','status':build123d}]}), flush=True)
print(json.dumps({'type':'assistant','message':{'content':[{'type':'text','text':'Inspecting the selected design'}]}}), flush=True)
if '--cli-error' in sys.argv:  # e.g. not logged in: the CLI reports an error result and exits non-zero
    print(json.dumps({'type':'result','is_error':True,'result':'Invalid API key · Please run /login'}),flush=True)
    raise SystemExit(1)
if '--no-structured' in sys.argv:
    print(json.dumps({'type':'result','is_error':False,'result':'plain text only'}),flush=True)
    raise SystemExit(0)
USAGE = {'duration_ms': 4200, 'total_cost_usd': 0.0123,
         'usage': {'input_tokens': 1000, 'output_tokens': 200, 'cache_read_input_tokens': 300}}
if prompt.startswith('You are the Magic CAD reviewer'):  # the reviewer run (#28): read-only, structured verdict
    print(json.dumps({'type':'assistant','message':{'content':[
        {'type':'tool_use','name':'Read','input':{'file_path':'outputs/good_two_parts/report.json'}},
        {'type':'text','text':'The blocks read as blocks; the gap is a chosen number.'}]}}), flush=True)
    score = 1 if 'review: fail' in prompt else 4
    print(json.dumps({'type':'result','is_error':False, **USAGE, 'structured_output':{
        'scores':{'looks_like_the_thing':score,'detail':score,'dimensions':score,'proportion':score,'print_intent':score},
        'tells':[] if score == 4 else ['Dimension nobody chose'],
        'fixes':[] if score == 4 else [{'text':'Choose the gap for the fit','parameter':'gap','value':1.25}],
        'good':'Two clean blocks'}}), flush=True)
    raise SystemExit(0)
if 'unsupported request' in prompt:
    print(json.dumps({'type':'result','is_error':False,'structured_output':{'supported':False,'reason':'This needs geometry-code editing beyond M0.'}}),flush=True)
    raise SystemExit(0)
if 'slow request' in prompt:
    while True:
        time.sleep(1)
print(json.dumps({'type':'result','is_error':False, **USAGE,
                  'structured_output':{'supported':True,'parameter':'size','value':24,'reason':'Increase the requested size'}}), flush=True)
