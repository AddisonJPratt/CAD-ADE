"""Resumable preview work with replayable, ordered session events."""
import threading


class ProposalSession:
    def __init__(self, ident, build, stream=None):
        self.id = ident
        self.build = build
        self.stream = stream
        self.changed = threading.Condition()
        self.cancel = threading.Event()
        self.events = []
        self.previews = {}
        self.state = 'created'
        self.error = None

    def _emit(self, kind, **data):
        self.events.append({'id': len(self.events) + 1, 'type': kind, **data})
        self.changed.notify_all()

    def start(self):
        with self.changed:
            if self.state != 'created':
                raise ValueError('session already started')
            self.state = 'running'
            self._emit('started')
        threading.Thread(target=self._work, daemon=True).start()

    def interrupt(self):
        with self.changed:
            if self.state != 'running':
                raise ValueError('session is not running')
            self.cancel.set()

    def reject(self):
        with self.changed:
            if self.state in ('ready', 'error', 'rejected'):
                self.state = 'rejected'
            else:
                self.state = 'rejected'
                self.cancel.set()
            self._emit('rejected')
            self.changed.notify_all()

    def resume(self):
        with self.changed:
            if self.state != 'interrupted':
                raise ValueError('session is not interrupted')
            self.cancel.clear()
            self.state = 'running'
            self._emit('resumed')
            self.changed.notify_all()

    def wait_for(self, state, timeout=None):
        with self.changed:
            return self.changed.wait_for(lambda: self.state == state, timeout)

    def _work(self):
        try:
            if self.stream:
                while True:
                    for event in self.stream():
                        with self.changed:
                            if self.state == 'rejected':
                                return
                            self._emit(event['type'], **{k: v for k, v in event.items() if k != 'type'})
                    with self.changed:
                        if self.state == 'rejected':
                            return
                        if not self.cancel.is_set():
                            break
                        self.state = 'interrupted'
                        self._emit('interrupted')
                        self.changed.wait_for(lambda: self.state in ('running', 'rejected'))
                        if self.state == 'rejected':
                            return
            for side in ('before', 'after'):
                while True:
                    with self.changed:
                        if self.state == 'rejected':
                            return
                        if self.cancel.is_set():
                            self.state = 'interrupted'
                            self._emit('interrupted')
                            self.changed.wait_for(lambda: self.state in ('running', 'rejected'))
                            if self.state == 'rejected':
                                return
                    result = self.build(side, self.cancel)
                    with self.changed:
                        if self.state == 'rejected':
                            return
                        if result.get('interrupted') or self.cancel.is_set():
                            continue
                        if not result['ok']:
                            raise ValueError(result.get('traceback', 'preview failed'))
                        self.previews[side] = result['parts']
                        self._emit('preview', side=side)
                        break
            with self.changed:
                if self.state == 'rejected':
                    return
                if self.cancel.is_set():
                    self.state = 'interrupted'
                    self._emit('interrupted')
                    self.changed.wait_for(lambda: self.state in ('running', 'rejected'))
                    if self.state == 'rejected':
                        return
                self.state = 'ready'
                self._emit('ready')
        except Exception as err:
            with self.changed:
                if self.state == 'rejected':
                    return
                self.error = str(err)
                self.state = 'error'
                self._emit('error', message=self.error)
