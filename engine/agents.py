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
        return parameter_edit(project, chosen, match.group(1), float(match.group(2)))

    def stream_events(self, session):
        while not session['interrupted'] and session['cursor'] < len(session['events']):
            event = session['events'][session['cursor']]
            session['cursor'] += 1
            yield event

    def interrupt(self, session):
        session['interrupted'] = True

    def resume(self, session):
        session['interrupted'] = False


class ParameterEditAgent(ScriptedFakeAgent):
    """Direct numeric edits use the same resumable proposal lifecycle, without an LLM."""
    def start(self, project, brief, selection, message):
        if not isinstance(message, dict):
            raise ProjectError('parameter edit must contain name and value')
        chosen = selection.get('design') if isinstance(selection, dict) else None
        return parameter_edit(project, chosen, message.get('name'), message.get('value'))
