"""Read PARAMS and prepare bounded edits without executing project code."""
import ast
import math
from pathlib import Path

import yaml

from .projects import ProjectError, designs_of


def _read(project, name):
    designs = designs_of(project)
    if name:
        designs = [path for path in designs if path.name == name]
    if len(designs) != 1:
        raise ProjectError('select one design before editing parameters')
    design = designs[0]
    source = design.read_text()
    try:
        tree = ast.parse(source)
        node = next((n.value for n in tree.body if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'PARAMS' for t in n.targets)), None)
        values = ast.literal_eval(node)
        if not isinstance(node, ast.Dict) or not isinstance(values, dict):
            raise ValueError('PARAMS must be a literal dictionary')
        if len(node.keys) != len(values):
            raise ValueError('duplicate parameter names are not supported')
        for key, spec in values.items():
            if not isinstance(key, str) or not isinstance(spec, (tuple, list)) or len(spec) != 3:
                raise ValueError('each parameter must declare default, minimum and maximum')
            if any(type(v) not in (int, float) or not math.isfinite(v) for v in spec):
                raise ValueError('parameter bounds must be finite numbers')
            if not spec[1] <= spec[0] <= spec[2]:
                raise ValueError('parameter default is outside its bounds')
    except (SyntaxError, ValueError, TypeError) as error:
        raise ProjectError(f'invalid PARAMS: {error}') from error
    return design, source, node, values


def parameters_of(project, design):
    design, _, _, values = _read(project, design)
    brief_path = Path(project) / 'briefs' / f'{design.stem}.yaml'
    metadata = {}
    if brief_path.is_file():
        try:
            metadata = (yaml.safe_load(brief_path.read_text()) or {}).get('params', {})
            if not isinstance(metadata, dict) or any(not isinstance(m, dict) for m in metadata.values()):
                raise ValueError('parameter metadata must be a mapping')
            if any((m.get('unit') is not None and not isinstance(m['unit'], str))
                   or not isinstance(m.get('intent', ''), str) for m in metadata.values()):
                raise ValueError('parameter units and intent must be text')
        except (yaml.YAMLError, AttributeError, ValueError) as error:
            raise ProjectError(f'invalid parameter brief: {error}') from error
    return [{'name': name, 'value': spec[0], 'min': spec[1], 'max': spec[2],
             'unit': metadata.get(name, {}).get('unit'),
             'intent': metadata.get(name, {}).get('intent', ''),
             'integer': type(spec[0]) is int} for name, spec in values.items()]


def parameter_edit(project, design, name, value):
    design, source, node, values = _read(project, design)
    if not isinstance(name, str) or name not in values:
        raise ProjectError(f'unknown parameter: {name}')
    old, low, high = values[name]
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ProjectError('parameter value must be a finite number')
    if type(old) is int:
        if not float(value).is_integer():
            raise ProjectError(f'{name} must be an integer')
        value = int(value)
    else:
        value = float(value)
    if not low <= value <= high:
        raise ProjectError(f'{name} must be between {low} and {high}')
    if value == old:
        raise ProjectError(f'{name} is already {old}')
    index = list(values).index(name)
    target = node.values[index].elts[0]
    lines = source.encode().splitlines(keepends=True)
    start = sum(map(len, lines[:target.lineno - 1])) + target.col_offset
    end = sum(map(len, lines[:target.end_lineno - 1])) + target.end_col_offset
    updated = source.encode()[:start] + repr(value).encode() + source.encode()[end:]
    return {'file': str(Path('designs') / design.name), 'source': updated.decode(),
            'changes': [{'parameter': name, 'old': old, 'new': value}],
            'events': [{'type': 'plan', 'message': f'Change {name} to {value}'}],
            'cursor': 0, 'interrupted': False}
