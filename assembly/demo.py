"""Illustrative wall-clip assembly; no inference of safety or physical performance.

The two screws are a schematic envelope, with an assumed under-head length. All
coordinates are mm in the clip export's frame. Source and mesh hashes are pinned
so a changed artifact cannot silently be passed off as the pictured assembly.
"""
import hashlib
import json
import math
from pathlib import Path

CLIP = 'runs/holder_clip/holder_clip.stl'
SCREW = 'assembly/assets/m3_socket_head.stl'
REPORT = 'runs/holder_clip/report.json'
STEP = 'runs/holder_clip/holder_clip.step'
SOURCE_FILES = ('designs/holder_clip.py', 'designs/cable_clip.py', 'briefs/holder_clip.yaml',
                'library/standard_parts.json', 'library/__init__.py', 'library/features.py')
MESH_URLS = {CLIP: '/runs/holder_clip/holder_clip.stl', SCREW: '/assembly/assets/m3_socket_head.stl'}


def digest(path):
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def _vector(value, name):
    if not isinstance(value, list) or len(value) != 3 or any(
        isinstance(x, bool) or not isinstance(x, (float, int)) or not math.isfinite(x) for x in value
    ):
        raise ValueError(f'{name} must be three finite coordinates')


def validate(data):
    """Validate IDs, transforms, BOM and assembly-step references for UI use."""
    if data.get('units') != 'mm':
        raise ValueError('assembly units must be mm')
    parts = data.get('parts')
    if not isinstance(parts, list) or not parts:
        raise ValueError('assembly needs parts')
    ids = set()
    for part in parts:
        ident = part.get('id')
        if not isinstance(ident, str) or not ident or ident in ids:
            raise ValueError('part IDs must be unique nonempty strings')
        ids.add(ident)
        _vector(part.get('position'), f'{ident} position')
        _vector(part.get('exploded_offset'), f'{ident} exploded offset')
        if part.get('mesh') not in MESH_URLS.values():
            raise ValueError('part mesh is not an approved asset')
    visited = []
    for i, step in enumerate(data.get('steps', []), 1):
        if step.get('number') != i or not step.get('text') or not step.get('part_ids'):
            raise ValueError('invalid assembly step')
        for ident in step['part_ids']:
            if ident not in ids or ident in visited:
                raise ValueError('steps must reference each part exactly once')
            visited.append(ident)
    if set(visited) != ids:
        raise ValueError('steps must include every part exactly once')
    for row in data.get('bom', []):
        related = row.get('part_ids', [])
        if not related or not set(related) <= ids or row.get('quantity') != len(related):
            raise ValueError('BOM quantity must match listed parts')
    bom_parts = [ident for row in data.get('bom', []) for ident in row['part_ids']]
    if len(bom_parts) != len(ids) or set(bom_parts) != ids:
        raise ValueError('BOM must list each part exactly once')
    return True


def get_demo(root):
    """Describe the pinned holder example and report source or asset drift honestly."""
    root = Path(root)
    hashes = json.loads((Path(__file__).parent / 'demo_hashes.json').read_text())
    observed = {name: digest(root / name) for name in hashes}
    changed = [p for p in SOURCE_FILES if observed[p] != hashes[p]]
    warnings = []
    if changed:
        warnings.append('Source or brief changed since this assembly snapshot; the shown model may be stale: ' + ', '.join(changed))
    for p, label in ((CLIP, 'Holder mesh'), (SCREW, 'Screw reference mesh'), (REPORT, 'Holder report'), (STEP, 'Holder STEP')):
        if observed[p] is None:
            warnings.append(f'{label} is missing.')
        elif observed[p] != hashes[p]:
            warnings.append(f'{label} differs from the pinned assembly snapshot.')
    if observed.get('assembly/create_hardware.py') != hashes['assembly/create_hardware.py']:
        warnings.append('Screw mesh generator changed since the snapshot.')

    # These coordinates are pinned to the recorded 38 mm holder and M3 dimensions:
    # cylinder head front = -19.45; local mesh head extends x=0..3.
    # The clip is in its original print orientation; the wall face is at negative X.
    head_base = -22.45
    parts = [
        {'id': 'clip', 'name': 'Wall clip', 'kind': 'printed', 'mesh': MESH_URLS[CLIP],
         'position': [0, 0, 0], 'exploded_offset': [0, 0, 0], 'color': '#dedbd3',
         'mesh_available': observed[CLIP] == hashes[CLIP]},
        *[{'id': f'screw_{i}', 'name': f'M3 screw {i}', 'kind': 'hardware', 'mesh': MESH_URLS[SCREW],
           'position': [head_base, 0, z], 'exploded_offset': [32 + (i-1)*12, 0, 0], 'color': '#777c7c',
           'mesh_available': observed[SCREW] == hashes[SCREW]} for i, z in enumerate((8, 24), 1)],
    ]
    data = {'id': 'holder_demo', 'name': 'Wall clip assembly', 'units': 'mm',
            'disclaimer': 'Illustrative assembly of a 38 mm holder and two simplified M3 screw envelopes. The 12 mm screw length is an example, not a verified fastener specification. The wall, mounting substrate, screw socket and threads are not modeled. Exploded positions and steps illustrate assembly, not validated tool paths or motion. Fit, retention and strength are not physically tested.',
            'parts': parts,
            'bom': [
                {'name': '38 mm wall clip', 'quantity': 1, 'category': 'Printed part', 'part_ids': ['clip'],
                 'note': 'Based on the saved holder run; material and real-world fit remain unverified.'},
                {'name': 'M3 socket-head screw (example)', 'quantity': 2, 'category': 'Hardware', 'part_ids': ['screw_1', 'screw_2'],
                 'note': 'Simplified envelope, assumed 12 mm under-head length. Select length for the actual substrate; not a validated specification.'}],
            'steps': [
                {'number': 1, 'text': 'Place the clip against the mounting surface.', 'part_ids': ['clip']},
                {'number': 2, 'text': 'Insert the two example screws through the clip into a suitable mounting surface.', 'part_ids': ['screw_1', 'screw_2']}],
            'warnings': warnings,
            'provenance': {'snapshot': '38 mm holder; source hashes pinned locally',
                           'report': REPORT, 'clip_mesh': CLIP, 'hardware_mesh': SCREW,
                           'source_matches_snapshot': not changed,
                           'report_matches_snapshot': observed[REPORT] == hashes[REPORT],
                           'step_matches_snapshot': observed[STEP] == hashes[STEP],
                           'physical_assembly_tested': False}}
    validate(data)
    return data
