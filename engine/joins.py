""""Join these two parts with a snap-fit": a joint proposed as an edit to the project's assembly.py (#54).

Deterministic, no language model: the request names a joint type and the selection names two
parts (a face picked on each). The proposal adds one line to `assemble()`,

    asm.join("snap_fit", "cap", "base")

and previews the assembly before and after through the assembly gate, so the joint's geometry,
its fit and the gate's verdict are seen before anything is kept. A joint whose gate fails is
not previewed as ready: the preview stops with the gate's own reason.
"""
import ast
import json
import re
from pathlib import Path

from library import joints as lib

from .agents import ScriptedFakeAgent, picks_of
from .projects import ProjectError

ASSEMBLY = 'assembly.py'
# Phrases for each joint kind, most specific first.
WORDS = [('print_in_place_hinge', r'print[- ]in[- ]place|pip hinge'), ('living_hinge', r'living hinge'),
         ('screw_insert', r'heat[- ]?set|insert'), ('dovetail', r'dovetail|sliding fit'),
         ('snap_fit', r'snap'), ('press_fit', r'press[- ]?fit|press')]


def requested_joint(message):
    """The joint kind a request asks for, or None when it is not a request to join parts."""
    if not isinstance(message, str) or not re.search(r'\b(join|connect|attach|fasten)\b', message, re.I):
        return None
    for kind, pattern in WORDS:
        if re.search(pattern, message, re.I):
            return kind
    return None


def _norm(text):
    return re.sub(r'[\s_-]+', ' ', str(text or '')).strip().lower()


def instance_for(pick, instances):
    """The assembly instance a picked body belongs to: by instance id, design, part or name."""
    body = _norm(pick.get('instance'))
    matches = []
    for inst in instances:
        if inst['kind'] != 'printed':
            continue
        spec = inst['spec']
        names = {_norm(inst['id']), _norm(inst['name']), _norm(Path(spec['design']).stem)}
        if spec.get('part'):
            names.add(_norm(spec['part']))
        if body in names:
            matches.append(inst['id'])
    if not matches:
        raise ProjectError(f"{pick.get('instance')!r} is not a printed part in the assembly")
    if len(matches) > 1:
        raise ProjectError(f"{pick.get('instance')!r} is used by {', '.join(matches)} in the assembly; "
                           f"join those instances in assembly.py by name")
    return matches[0]


def joined_source(source, kind, a, b):
    """assembly.py with `asm.join(kind, a, b)` as the last statement of assemble()."""
    tree = ast.parse(source)
    func = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'assemble'), None)
    if func is None or not func.args.args:
        raise ProjectError('assembly.py has no assemble(asm, ...) to add the joint to')
    asm = func.args.args[0].arg
    for node in ast.walk(func):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == 'join'
                and [getattr(x, 'value', None) for x in node.args[:3]] in ([kind, a, b], [kind, b, a])):
            raise ProjectError(f'{a} and {b} already have a {lib.LABELS[kind]}')
    lines = source.splitlines(keepends=True)
    last = func.body[-1]
    indent = ' ' * last.col_offset
    line = f'{indent}{asm}.join({json.dumps(kind)}, {json.dumps(a)}, {json.dumps(b)})\n'
    end = last.end_lineno
    if lines and not lines[end - 1].endswith('\n'):
        lines[end - 1] += '\n'
    return ''.join(lines[:end] + [line] + lines[end:])


class JoinAgent(ScriptedFakeAgent):
    """Proposes a joint between the two picked parts as an assembly.py edit."""

    def start(self, project, brief, selection, message):
        kind = requested_joint(message)
        if kind is None:
            raise ProjectError('Say which joint to use, such as "join these two parts with a snap-fit".')
        if kind not in lib.FACE_JOINTS:
            raise ProjectError(f'A {lib.LABELS[kind]} needs a joint frame placed by hand in assembly.py '
                               f'(asm.join("{kind}", ..., at=...)); from two picks Studio can add a '
                               f'{" or ".join(lib.LABELS[k] for k in lib.FACE_JOINTS)}.')
        project = Path(project)
        if not (project / ASSEMBLY).is_file():
            raise ProjectError('Joining parts needs an assembly: add assembly.py that places both parts first.')
        picks = [p for p in (selection or {}).get('picks') or [] if isinstance(p, dict)]
        bodies = []
        for pick in picks:
            if pick.get('instance') not in [b.get('instance') for b in bodies]:
                bodies.append(pick)
        if len(bodies) != 2:
            raise ProjectError(f'Pick a face on each of the two parts to join (Shift-click the second); '
                               f'{len(bodies)} part{"s are" if len(bodies) != 1 else " is"} picked.')
        from assembly.gate import evaluate_parts
        report = evaluate_parts(project / ASSEMBLY, project)
        failed = next((c for c in report['checks'] if c['status'] == 'FAIL'), None)
        if failed:
            raise ProjectError(f"assembly.py does not build yet: {failed['detail']}")
        a, b = (instance_for(p, report['instances']) for p in bodies)
        if a == b:
            raise ProjectError(f'Both picks are on {a}; pick a face on each of the two parts.')
        source = joined_source((project / ASSEMBLY).read_text(), kind, a, b)
        try:
            from engine.printers import project_printer
            material = project_printer(project)['material']
        except Exception:
            material = 'PLA'
        fit = lib.spec(kind)['fit']
        gap = lib.clearance(fit, material)
        label = lib.LABELS[kind]
        change = {'kind': 'joint', 'joint': kind, 'parts': [a, b], 'fit': fit, 'material': material,
                  'clearance': gap, 'parameter': 'joint', 'old': 'none', 'new': f'{label}, {a} to {b}'}
        events = [{'type': 'plan', 'message': f'Selected: {p}'} for p in picks_of(selection)]
        events.append({'type': 'plan', 'message': f'Joining {a} and {b} with a {label}: {material} {fit.replace("_", "-")} '
                                                  f'fit, {gap:g} mm per side, from the printer profile. '
                                                  f'Needs a physical test until a print result is recorded.'})
        events.append({'type': 'edit', 'file': ASSEMBLY, 'changes': [change]})
        return {'file': ASSEMBLY, 'source': source, 'changes': [change], 'events': events, 'cursor': 0,
                'interrupted': False, 'kind': 'assembly', 'selection': selection}


def preview_assembly(draft, out, timeout=180):
    """Build the draft's assembly through the gate; the printed parts as preview parts.

    {'ok', 'parts': [{'name', 'stl', 'bbox': {'size'}}], 'report'} like a design build; ok only
    when the gate passes, else 'traceback' carries the gate's failing checks.
    """
    import trimesh
    from assembly.gate import run_gate
    report = run_gate(Path(draft) / ASSEMBLY, draft, out, timeout=timeout)
    manifest = Path(out) / 'assembly.json'
    if not report['pass'] or not manifest.is_file():
        failed = '; '.join(f"{c['name']}: {c['detail']}" for c in report['checks'] if c['status'] == 'FAIL')
        return {'ok': False, 'traceback': f'The assembly gate failed: {failed or "no manifest written"}'}
    parts = []
    for inst in json.loads(manifest.read_text())['instances']:
        if inst['kind'] != 'printed':
            continue
        stl = Path(out) / inst['mesh']
        size = [float(x) for x in trimesh.load_mesh(stl).extents]
        parts.append({'name': inst['id'], 'stl': str(stl), 'bbox': {'size': size}})
    return {'ok': True, 'parts': parts, 'report': report}
