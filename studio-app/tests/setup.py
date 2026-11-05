"""Create two real, independently checked versions for the browser test."""
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engine.versions import create_project, save_version
from engine.projects import run_project
project = Path(os.environ['MAGIC_TEST_PROJECT'])
create_project(project, ROOT / 'tests/fixtures/good_two_parts.py')
assert run_project(project, samples=5)[1]['pass']
design = project / 'designs/good_two_parts.py'
design.write_text(design.read_text().replace('"size": (20.0,', '"size": (24.0,'))
save_version(project, 'Changed height')
assert run_project(project, samples=5)[1]['pass']
print(project)
