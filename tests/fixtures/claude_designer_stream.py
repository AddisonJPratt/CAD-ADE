"""Local stand-in for the Claude Code CLI as the designer (#61) drives it; no model calls.

It plays a designer that writes designs/block.py in its working folder (the proposal draft), as
Claude's Edit tool would: a hard-coded design on the first attempt, and a passing one once the
prompt carries a gate report. Flags: --log <file> appends each run's argv and prompt as JSON;
--pid-file <file>; --slow never finishes (for interrupt tests).
"""
import json
import os
import sys
import time
from pathlib import Path

HARDCODED = '''from build123d import Box

PARAMS = {"width": (20.0, 10.0, 30.0)}


def build(width):
    return Box(width, 13, 13)
'''

GOOD = '''"""A block sized by the brief."""
from build123d import Align, Box

PARAMS = {
    "width": (20.0, 10.0, 30.0),   # mm, 10..30: block width along X
    "height": (10.0, 8.0, 12.0),   # mm, 8..12: block height
}


def build(width, height):
    block = Box(width, height, height, align=(Align.CENTER, Align.CENTER, Align.MIN))
    block.label = "block"
    return block
'''

prompt = sys.stdin.read()
if '--pid-file' in sys.argv:
    Path(sys.argv[sys.argv.index('--pid-file') + 1]).write_text(str(os.getpid()))
if '--log' in sys.argv:
    with open(sys.argv[sys.argv.index('--log') + 1], 'a') as log:
        log.write(json.dumps({'argv': sys.argv[1:], 'prompt': prompt, 'cwd': os.getcwd()}) + '\n')
print(json.dumps({'type': 'system', 'subtype': 'init', 'mcp_servers': [
    {'name': 'magic-cad', 'status': 'connected'}, {'name': 'build123d', 'status': 'connected'}]}), flush=True)
print(json.dumps({'type': 'assistant', 'message': {'content': [
    {'type': 'text', 'text': 'Reading the brief card'},
    {'type': 'tool_use', 'name': 'Write', 'input': {'file_path': 'designs/block.py'}}]}}), flush=True)
if '--slow' in sys.argv:
    while True:
        time.sleep(1)
first = '"last_gate_report": null' in prompt
Path('designs').mkdir(exist_ok=True)
Path('designs/block.py').write_text(HARDCODED if first else GOOD)
print(json.dumps({'type': 'result', 'is_error': False, 'duration_ms': 1000, 'total_cost_usd': 0.01,
                  'usage': {'input_tokens': 10, 'output_tokens': 5},
                  'structured_output': {'summary': 'A block to the brief', 'files': ['designs/block.py']}}), flush=True)
