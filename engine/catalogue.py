"""Purchased components and project-local, user-measured additions (millimetres)."""
import json
import math
import os
import tempfile
import re
from pathlib import Path

from .projects import ProjectError
from .versions import Conflict

ROOT = Path(__file__).resolve().parent.parent
BUILTIN = ROOT / 'library' / 'components.json'


def project_path(project):
    if not isinstance(project, str) or not project.strip():
        raise ProjectError('project must be an existing directory')
    path = Path(project).expanduser().resolve()
    if not path.is_dir():
        raise ProjectError('project must be an existing directory')
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
                 'keepouts': [{'purpose': 'component', 'shape': 'box',
                               'dimensions': ['length', 'width', 'height']}],
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
    return component
