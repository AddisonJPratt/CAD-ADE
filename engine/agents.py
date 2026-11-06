"""Agent session interface and a deterministic fake for the app seam."""
import ast
import re
from abc import ABC, abstractmethod
from pathlib import Path

from .projects import ProjectError, designs_of


class AgentAdapter(ABC):
    @abstractmethod
    def start(self, project, brief, selection, message):
        """Return a session promptly; produce events and edits while streaming."""

    @abstractmethod
    def stream_events(self, session):
        """Yield undelivered events until interrupted or complete."""

    @abstractmethod
    def interrupt(self, session):
        """Interrupt a running session."""

    @abstractmethod
    def resume(self, session):
        """Resume an interrupted session."""


class ScriptedFakeAgent(AgentAdapter):
    """A predictable parameter edit for integration tests, not a language model."""
    def start(self, project, brief, selection, message):
        designs = designs_of(project)
        chosen = selection.get('design') if isinstance(selection, dict) else None
        if chosen:
            designs = [path for path in designs if path.name == chosen]
        if len(designs) != 1:
            raise ProjectError('select one design before requesting a change')
        design = designs[0]
        source = design.read_text()
        tree = ast.parse(source)
        params = next((node.value for node in tree.body if isinstance(node, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == 'PARAMS' for t in node.targets)), None)
        if not isinstance(params, ast.Dict):
            raise ProjectError('design has no PARAMS dictionary')
        match = re.search(r'\b([A-Za-z_]\w*)\s+(?:to\s+)?(-?\d+(?:\.\d+)?)', message)
        if not match:
            raise ProjectError('fake agent expects a parameter and value, such as size 24')
        name, value = match.group(1), float(match.group(2))
        for key, entry in zip(params.keys, params.values):
            if isinstance(key, ast.Constant) and key.value == name and isinstance(entry, (ast.Tuple, ast.List)):
                old, low, high = (ast.literal_eval(n) for n in entry.elts[:3])
                if isinstance(old, int) and not isinstance(old, bool):
                    if not value.is_integer():
                        raise ProjectError(f'{name} must be an integer')
                    value = int(value)
                if not low <= value <= high:
                    raise ProjectError(f'{name} must be between {low} and {high}')
                if value == old:
                    raise ProjectError(f'{name} is already {old}')
                node = entry.elts[0]
                lines = source.splitlines(keepends=True)
                lines[node.lineno-1] = (lines[node.lineno-1][:node.col_offset] + repr(value)
                                         + lines[node.end_lineno-1][node.end_col_offset:])
                return {'file': str(Path('designs') / design.name), 'source': ''.join(lines),
                        'changes': [{'parameter': name, 'old': old, 'new': value}],
                        'events': [{'type': 'plan', 'message': f'Change {name} to {value}'}],
                        'cursor': 0, 'interrupted': False}
        raise ProjectError(f'unknown parameter: {name}')

    def stream_events(self, session):
        while not session['interrupted'] and session['cursor'] < len(session['events']):
            event = session['events'][session['cursor']]
            session['cursor'] += 1
            yield event

    def interrupt(self, session):
        session['interrupted'] = True

    def resume(self, session):
        session['interrupted'] = False
