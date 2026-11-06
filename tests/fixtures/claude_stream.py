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
print(json.dumps({'type':'system', 'subtype':'init', 'mcp_servers':[
    {'name':'magic-cad','status':'connected'}, {'name':'build123d','status':'connected'}]}), flush=True)
print(json.dumps({'type':'assistant','message':{'content':[{'type':'text','text':'Inspecting the selected design'}]}}), flush=True)
if 'unsupported request' in prompt:
    print(json.dumps({'type':'result','is_error':False,'structured_output':{'supported':False,'reason':'This needs geometry-code editing beyond M0.'}}),flush=True)
    raise SystemExit(0)
if 'slow request' in prompt:
    while True:
        time.sleep(1)
print(json.dumps({'type':'result','is_error':False,
                  'structured_output':{'supported':True,'parameter':'size','value':24,'reason':'Increase the requested size'}}), flush=True)
