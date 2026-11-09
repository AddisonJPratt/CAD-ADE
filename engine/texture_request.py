"""Texture requests on a selection (#52): "Add knurling to this face" becomes a source edit.

Like a direct parameter edit, this needs no language model: the request names a texture, the
selection names one face, and the edit is fixed in shape. It adds two PARAMS (pitch and depth,
ranges from library.surface.texture_ranges, so every swept corner is printable) and wraps
build() so the texture goes on the picked face of the picked part. The face is chosen by what
it is (facing direction, named feature, or outermost upright cylinder), not by coordinates, so
the edit survives parameter changes and passes the hard-coded-literal lint.
"""
import ast
import io
import re
import tokenize
from pathlib import Path

from .agents import ScriptedFakeAgent
from .projects import ProjectError, designs_of

WORDS = {"knurl": "knurl", "knurling": "knurl", "knurled": "knurl",
         "diamond": "diamond", "crosshatch": "diamond", "cross-hatch": "diamond",
         "hex": "hex", "hexagon": "hex", "hexagons": "hex", "hexagonal": "hex",
         "rib": "ribbing", "ribs": "ribbing", "ribbing": "ribbing", "ribbed": "ribbing"}
INTENT = {"knurl": "straight knurl", "diamond": "diamond knurl", "hex": "hex studs", "ribbing": "raised ribs"}
SQUARE = 0.999   # a flat pick's normal this close to an axis is that axis
UPRIGHT = 0.05   # a curved pick's normal this level is on an upright cylinder
_WORD = re.compile(r"[a-z][a-z-]*")


def texture_kind(message):
    """The texture a chat request asks for, or None."""
    if not isinstance(message, str):
        return None
    words = _WORD.findall(message.lower())
    if not any(w in ("add", "apply", "put", "texture", "knurl", "knurled") for w in words):
        return None
    return next((WORDS[w] for w in words if w in WORDS), None)


def face_pick(selection):
    """The one face pick a texture goes on; ProjectError when there is not exactly one."""
    picks = selection.get("picks") if isinstance(selection, dict) else None
    faces = [p for p in picks or [] if isinstance(p, dict) and p.get("kind") == "face"]
    if len(faces) != 1:
        raise ProjectError("pick the one face to texture, then ask again")
    return faces[0]


def texture_request(message, selection):
    """True when a request is a texture on a selection this agent handles."""
    return bool(texture_kind(message)) and isinstance(selection, dict) and bool(selection.get("picks"))


def selector(pick):
    """pick_face() keyword source for a pick, and a plain description of it."""
    normal = [float(c) for c in pick.get("normal") or (0, 0, 0)]
    feature = pick.get("feature")
    if pick.get("flat") is False:
        if abs(normal[2]) > UPRIGHT:
            raise ProjectError("that curved surface is not an upright cylinder; textures go on flat faces "
                               "or on a cylinder standing along print-up")
        return 'kind="cylinder"', "the outermost upright cylinder"
    axis = max(range(3), key=lambda i: abs(normal[i]))
    if abs(normal[axis]) < SQUARE:
        raise ProjectError("that face is not square to an axis; pick a face facing up, down or to a side")
    facing = ("+" if normal[axis] > 0 else "-") + "XYZ"[axis]
    if feature:
        return f'facing="{facing}", feature={feature!r}', f"the {facing} face of {feature!r}"
    return f'facing="{facing}"', f"the outermost face facing {facing}"


def _params_node(tree):
    return next(n.value for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == "PARAMS" for t in n.targets))


def _offset(lines, lineno, col):
    return sum(map(len, lines[:lineno - 1])) + col


def add_params(source, entries):
    """Insert PARAMS entries (name, (default, min, max), comment) before the dict's closing brace."""
    tree = ast.parse(source)
    node = _params_node(tree)
    if not isinstance(node, ast.Dict):
        raise ProjectError("PARAMS must be a literal dictionary")
    lines = source.splitlines(keepends=True)
    close = _offset(lines, node.end_lineno, node.end_col_offset) - 1
    text = source
    if node.values:   # make sure the last entry ends in a comma (comments may follow it)
        last = node.values[-1]
        end = _offset(lines, last.end_lineno, last.end_col_offset)
        between = "".join(t.string for t in tokenize.generate_tokens(io.StringIO(text[end:close]).readline)
                          if t.type == tokenize.OP)
        if "," not in between:
            text, close = text[:end] + "," + text[end:], close + 1
    indent = " " * (node.values[0].col_offset if False else 4)
    body = "".join(f'{indent}"{name}": {spec!r},{" " * max(1, 22 - len(name))}# {comment}\n'
                   for name, spec, comment in entries)
    head = text[:close]
    if not head.endswith("\n"):
        head += "\n"
    return head + body + text[close:]


class TextureEditAgent(ScriptedFakeAgent):
    """Adds a texture to the picked face through the same resumable proposal lifecycle."""

    def start(self, project, brief, selection, message):
        from library.surface import texture_ranges
        kind = texture_kind(message)
        if not kind:
            raise ProjectError("name a texture: knurl, diamond, hex or ribbing")
        pick = face_pick(selection)
        designs = designs_of(project)
        chosen = selection.get("design")
        if chosen:
            designs = [p for p in designs if p.name == chosen]
        if len(designs) != 1:
            raise ProjectError("select one design before requesting a change")
        design = designs[0]
        source = design.read_text()
        try:
            declared = ast.literal_eval(_params_node(ast.parse(source)))
        except (SyntaxError, ValueError, StopIteration) as error:
            raise ProjectError(f"invalid PARAMS: {error}") from error
        base, n = kind, 1
        while f"{base}_pitch" in declared or f"{base}_depth" in declared:
            n += 1
            base = f"{kind}{n}"
        pitch_name, depth_name = f"{base}_pitch", f"{base}_depth"
        ranges = texture_ranges(kind)
        where, said = selector(pick)
        part = pick.get("instance") or ""
        intent = INTENT[kind]
        entries = [(pitch_name, ranges["pitch"], f"mm, {intent} pitch on {said} (texture added in Studio)"),
                   (depth_name, ranges["depth"], f"mm, {intent} depth; bounds from the print rules")]
        edited = add_params(source, entries)
        build_before = f"_build_before_{base}"
        edited = edited.rstrip("\n") + f'''


# Texture: {intent} on {said} of "{part}", added from a Studio selection (#52).
# The face is picked by what it is, so it survives parameter changes; bounds come from print_rules.
from library.surface import on_part as _on_part, pick_face as _pick_face, texture as _texture  # noqa: E402

{build_before} = build


def build({pitch_name}, {depth_name}, **params):
    return _on_part({build_before}(**params), {part!r}, lambda part: _texture(
        part, _pick_face(part, {where}), {kind!r}, pitch={pitch_name}, depth={depth_name},
        params=({pitch_name!r}, {depth_name!r})).shape)
'''
        file = str(Path("designs") / design.name)
        changes = [{"parameter": name, "old": None, "new": spec[0], "min": spec[1], "max": spec[2],
                    "unit": "mm", "intent": comment.split(", ", 1)[1]} for name, spec, comment in entries]
        plan = (f"Add {intent} to {said} of {part or 'the part'}: pitch {ranges['pitch'][0]} mm, "
                f"depth {ranges['depth'][0]} mm, both new parameters bounded by the 0.4 mm nozzle rules")
        return {"file": file, "source": edited, "changes": changes, "selection": selection,
                "events": [{"type": "plan", "message": plan},
                           {"type": "edit", "file": file, "changes": changes}],
                "cursor": 0, "interrupted": False}
