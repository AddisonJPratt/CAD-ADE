"""Purchased components and project-local, user-measured additions (millimetres)."""
import json
import math
import os
import tempfile
import re
from pathlib import Path

from .projects import ProjectError, designs_of
from .versions import Conflict, git, is_versioned

ROOT = Path(__file__).resolve().parent.parent
BUILTIN = ROOT / 'library' / 'components.json'


def project_path(project):
    if not isinstance(project, str) or not project.strip():
        raise ProjectError('project must be an existing directory')
    path = Path(project).expanduser().resolve()
    if not path.is_dir():
        raise ProjectError('project must be an existing directory')
    designs_of(path)
    catalogue = path / 'catalogue.json'
    if catalogue.is_symlink():
        raise ProjectError('project catalogue must not be a symlink')
    return catalogue


def list_components(project):
    path = project_path(project)
    builtin = json.loads(BUILTIN.read_text())
    custom = json.loads(path.read_text()) if path.exists() else []
    if not isinstance(custom, list):
        raise ProjectError('project catalogue must contain a list')
    return builtin + custom


def add_component(project, item):
    if not isinstance(item, dict):
        raise ProjectError('component must be an object')
    identifier, name, dims = item.get('id'), item.get('name'), item.get('dimensions')
    if not isinstance(identifier, str) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', identifier):
        raise ProjectError('component id must use lowercase letters, numbers and hyphens')
    if not isinstance(name, str) or not name.strip() or len(name) > 120:
        raise ProjectError('component needs a name')
    if not isinstance(dims, dict) or not all(k in dims for k in ('length', 'width', 'height')):
        raise ProjectError('length, width and height measurements are required')
    if any(not isinstance(k, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', k) or
           isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0
           for k, v in dims.items()):
        raise ProjectError('measurements must be finite positive numbers in millimetres')
    if any(c['id'] == identifier for c in list_components(project)):
        raise Conflict('component id already exists')
    component = {'id': identifier, 'name': name.strip(), 'source': 'user measurements',
                 'dimensions': {k: {'value': v, 'unit': 'mm', 'provenance': 'user-measured'}
                                for k, v in dims.items()},
                 'coordinate_system': 'Origin at centre of outline, z=0 at component bottom; length along y and width along x.',
                 'keepouts': [{'purpose': 'component', 'shape': 'box',
                               'dimensions': ['width', 'length', 'height'],
                               'placement': 'centred over outline, from z=0'}],
                 'mounting_points': [], 'notes': 'Envelope from user measurements; verify connector access separately.'}
    path = project_path(project)
    current = json.loads(path.read_text()) if path.exists() else []
    current.append(component)
    # Replace atomically so a concurrent reader never observes a partial catalogue.
    name = None
    try:
        with tempfile.NamedTemporaryFile('w', dir=path.parent, prefix='.catalogue-', delete=False) as out:
            name = out.name
            json.dump(current, out, indent=2, allow_nan=False)
            out.write('\n')
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
    if is_versioned(path.parent):
        # Save the catalogue as its own version so a new part never leaves the project with
        # unsaved changes (which blocks rollback and proposals); other unsaved edits stay unsaved.
        git(path.parent, 'add', '--', path.name)
        git(path.parent, 'commit', '--quiet', '--message', f"Add catalogue part: {component['name']}",
            '--', path.name)
    return component
