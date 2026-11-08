"""Agent session interface and a deterministic fake for the app seam."""
import re
from abc import ABC, abstractmethod

from .projects import ProjectError
from .parameters import parameter_edit


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
        match = re.search(r'\b([A-Za-z_]\w*)\s+(?:to\s+)?(-?\d+(?:\.\d+)?)', message)
        if not match:
            raise ProjectError('fake agent expects a parameter and value, such as size 24')
        chosen = selection.get('design') if isinstance(selection, dict) else None
        session = parameter_edit(project, chosen, match.group(1), float(match.group(2)))
        session['selection'] = selection  # echoed by GET /proposals/<id>, so a test can see it arrived
        for pick in picks_of(selection):
            session['events'].append({'type': 'plan', 'message': f"Selected: {pick}"})
        for pin in picks_of(selection, 'pins'):
            session['events'].append({'type': 'plan', 'message': f"Pinned: {pin}"})
        return session

    def stream_events(self, session):
        while not session['interrupted'] and session['cursor'] < len(session['events']):
            event = session['events'][session['cursor']]
            session['cursor'] += 1
            yield event

    def interrupt(self, session):
        session['interrupted'] = True

    def resume(self, session):
        session['interrupted'] = False


def picks_of(selection, key='picks'):
    """One line per pick (or, with key='pins', per note pin) in a selection payload, as Studio describes it, or nothing."""
    picks = selection.get(key) if isinstance(selection, dict) else None
    if not isinstance(picks, list):
        return []
    return [p['description'] for p in picks if isinstance(p, dict) and isinstance(p.get('description'), str)]


class ParameterEditAgent(ScriptedFakeAgent):
    """Direct numeric edits use the same resumable proposal lifecycle, without an LLM."""
    def start(self, project, brief, selection, message):
        if not isinstance(message, dict):
            raise ProjectError('parameter edit must contain name and value')
        chosen = selection.get('design') if isinstance(selection, dict) else None
        session = parameter_edit(project, chosen, message.get('name'), message.get('value'))
        session['selection'] = selection
        return session
