"""Create two real, independently checked versions for the browser test."""
import os
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from engine.versions import create_project, save_version, list_versions
from engine.projects import run_project
project = Path(os.environ['MAGIC_TEST_PROJECT'])
create_project(project, ROOT / 'tests/fixtures/good_two_parts.py')
assert run_project(project, samples=5)[1]['pass']
design = project / 'designs/good_two_parts.py'
design.write_text(design.read_text().replace('"size": (20.0,', '"size": (24.0,'))
(project / 'briefs').mkdir(exist_ok=True)
(project / 'briefs' / 'café.yaml').write_text('note: saved Unicode filename\n')
save_version(project, 'Changed height')
assert run_project(project, samples=5)[1]['pass']
design.write_text(design.read_text().replace('size, size, size,', 'size, size, 37.5,'))
save_version(project, 'Invalid height')
assert not run_project(project, samples=5)[1]['pass']
oldest = list_versions(project)[-1]["id"]
shutil.rmtree(project / '.magic' / 'artifacts' / oldest)
(project / 'catalogue.json').write_text(json.dumps([{'id': 'measured-test', 'name': 'Measured test part', 'source': 'user measurements', 'dimensions': {'width': {'value': 17.2, 'unit': 'mm', 'provenance': 'user-measured'}}}]))
print(project)
