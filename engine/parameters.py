"""Read PARAMS and prepare bounded edits without executing project code."""
import ast
import io
import math
import re
import tokenize
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


_LINE_UNIT = re.compile(r'(?:^|[,;:])\s*(?P<unit>mm|deg|count|ratio)\s*(?P<sep>[,;:]|$)')
_HEADER_UNIT = re.compile(r'\bmm\b')
_HEADER_LEGEND = re.compile(r'\([^)]*\bdefault\b[^)]*\)')


def _comment_metadata(source, node):
    """Unit and intent from the house-style comments inside the PARAMS literal."""
    comments = {}
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.start[0] > node.end_lineno:
            break
        if token.type == tokenize.COMMENT and token.start[0] >= node.lineno:
            comments[token.start[0]] = token.string.lstrip('#').strip()
    first = node.keys[0].lineno if node.keys else node.end_lineno
    header = _HEADER_LEGEND.sub('', ' '.join(text for line, text in comments.items() if line < first))
    default_unit = 'mm' if _HEADER_UNIT.search(header) else None
    # A comment shared by entries on one line describes none of them in particular.
    ends = [value.end_lineno for value in node.values]
    metadata = {}
    for key, value in zip(node.keys, node.values):
        line = next((n for n in (value.end_lineno, key.lineno) if n in comments and ends.count(n) <= 1), None)
        text, unit = comments.get(line, ''), default_unit
        # A unit word stands alone between separators: "deg", "mm, object width",
        # "tab width, deg", "lean, deg; clamped", "ratio: rib length / leg length".
        if found := _LINE_UNIT.search(text):
            unit = found.group('unit')
            text = (text[:found.start()] + found.group('sep') + text[found.end():]).strip(' ,;:')
        metadata[key.value] = {'unit': unit, 'intent': text[:1].upper() + text[1:]}
    return metadata


def parameters_of(project, design):
    design, source, node, values = _read(project, design)
    comments = _comment_metadata(source, node)
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
    def declared(name, field):
        """The brief's declaration wins, even an explicit null; otherwise the code comment."""
        brief = metadata.get(name, {})
        return brief[field] if field in brief else comments[name][field]
    return [{'name': name, 'value': spec[0], 'min': spec[1], 'max': spec[2],
             'unit': declared(name, 'unit'),
             'intent': declared(name, 'intent') or '',
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
            'events': [{'type': 'plan', 'message': f'Change {name} to {value}'},
                       {'type': 'edit', 'file': str(Path('designs') / design.name),
                        'changes': [{'parameter': name, 'old': old, 'new': value}]}],
            'cursor': 0, 'interrupted': False}


def accepted_brief_edit(project, design_file, changes):
    """Synchronize only approved editable defaults; never alter hard requirements."""
    path = Path(project) / 'briefs' / (Path(design_file).stem + '.yaml')
    if not path.is_file():
        return None
    original = path.read_text()
    brief = yaml.safe_load(original)
    if not isinstance(brief, dict) or not isinstance(brief.get('params'), dict):
        raise ProjectError('brief has no parameter metadata')
    for change in changes:
        if change.get('old') is None and change['parameter'] not in brief['params']:
            # A parameter the change added (a texture's pitch, say): declare it in the brief too.
            brief['params'][change['parameter']] = {
                'value': change['new'], 'min': change['min'], 'max': change['max'],
                'unit': change.get('unit'), 'intent': change.get('intent', '')}
            continue
        metadata = brief['params'].get(change['parameter'])
        if not isinstance(metadata, dict) or metadata.get('value') != change['old']:
            raise ProjectError('brief parameter default is stale; resolve it before accepting')
        if not metadata['min'] <= change['new'] <= metadata['max']:
            raise ProjectError('proposed value is outside the brief parameter range')
        metadata = dict(metadata)
        metadata['value'] = change['new']
        brief['params'][change['parameter']] = metadata
    return path, original, yaml.safe_dump(brief, sort_keys=False)
