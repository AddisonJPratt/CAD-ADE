"""Contract lint: design files may not hard-code dimensions outside PARAMS.

Allowed numeric literals are structural, not dimensional: 0, 1, 2 (halving, doubling,
counts), 0.5, and the right angles 90/180. Everything else must come from PARAMS, or
from the library / standard-parts database.
"""
import ast

ALLOWED = {0, 1, 2, 0.5, 90, 180}


def lint_design(path):
    """Return a list of 'line N: literal V' strings for forbidden numeric literals."""
    tree = ast.parse(open(path).read(), filename=str(path))
    params_nodes = set()
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else []
        if any(isinstance(t, ast.Name) and t.id == "PARAMS" for t in targets):
            params_nodes.update(id(n) for n in ast.walk(node))
    problems = []
    for node in ast.walk(tree):
        if id(node) in params_nodes or not isinstance(node, ast.Constant):
            continue
        value = node.value
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value not in ALLOWED:
            problems.append(f"line {node.lineno}: literal {value}")
    return problems
