"""Printer capabilities and project material selection.

Fit values are starting assumptions, not measured calibration. Selection is stored
with project source so versions and rollback preserve the settings used for a run.
"""
import json
from pathlib import Path

from .projects import ProjectError, designs_of

from library.printer_profiles import PROFILE

SETTINGS = 'printer.json'


def project_printer(project):
    project = Path(project).expanduser().resolve()
    designs_of(project)
    path = project / SETTINGS
    try:
        settings = json.loads(path.read_text()) if path.exists() else {'printer': PROFILE['id'], 'material': 'PLA'}
        if not isinstance(settings, dict) or settings.get('printer') != PROFILE['id'] or settings.get('material') not in PROFILE['materials']:
            raise ValueError('unknown printer or material')
    except (OSError, ValueError, TypeError) as err:
        raise ProjectError(f'invalid printer settings: {err}') from err
    return {'profile': PROFILE, 'material': settings['material']}


def select_printer(project, printer, material):
    project = Path(project).expanduser().resolve()
    designs_of(project)
    if printer != PROFILE['id'] or material not in PROFILE['materials']:
        raise ProjectError('unknown printer or material')
    (project / SETTINGS).write_text(json.dumps({'printer': printer, 'material': material}, indent=2) + '\n')
    return project_printer(project)
