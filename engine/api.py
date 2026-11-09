"""The Magic CAD engine API: a local HTTP server over engine.projects. Test seam 1 of the spec.

    .venv/bin/python magic.py serve [--port 8766]

    GET  /health                         engine identity
    POST /runs                           {"project": "/abs/folder", "samples"?, "timeout"?, "wait"?, "slice"?}
                                         202 with the queued run; with "wait": true, 200 once it is done.
                                         "slice": true also slices passing designs with ElegooSlicer
                                         (engine/slicer.py) and keeps a 3MF; it never sends a print job
    GET  /runs                           every run since the engine started, newest first
    GET  /runs/<id>                      status (queued | running | done | error) and, when done, the verdict
    GET  /runs/<id>/events               Server-Sent Events: the whole history, then live events,
                                         then an "end" event. Honours Last-Event-ID.
    GET  /runs/<id>/artifacts/<path>     a file from the project's outputs folder (STL, STEP, PNG, report)

    GET  /workspace/projects             projects in the projects home plus recently opened ones
    GET  /workspace/starters             repo designs a new project can start from
    GET  /workspace/browse?path=...      a folder's subfolders with projects marked (default: ~)
    POST /workspace/projects             {"name", "starter"}: <projects home>/<name> as version 1 (201)
    POST /workspace/choose-folder        {}: show the macOS Finder folder panel; {"path"|null, "project"}
    POST /workspace/recent               {"project"}: remember a project as opened
    GET  /projects/parameters?project=...&design=...  literal defaults/ranges and brief units
    POST /proposals                      {"project", "message", "selection"?} a chat request to the agent, or
                                         {"project", "parameter":{"name","value"}, "selection"?} an explicit
                                         parameter edit; both are held for acceptance. selection is
                                         {"design", "picks":[{instance, kind, feature, parameters, description, point,
                                         normal, centroid, area, ...}], "measurement"?} and is handed to the
                                         agent as sent; GET /proposals/<id> echoes it back. A message asking to
                                         join the two picked parts ("join these with a snap-fit") is proposed by
                                         engine/joins.py as an assembly.py edit, previewed through the assembly gate
    POST /projects                       {"folder", "from_design"}: a new project as version 1 (201)
    GET  /projects/printer?project=...   current printer and material
    POST /projects/printer               {"project", "material", "printer"?}: select project settings
    GET  /projects/versions?project=...  the version timeline, newest first, with each version's verdict
    POST /projects/versions              {"project", "message"}: save the current files as a version (201)
    POST /projects/rollback              {"project", "version", "wait"?}: restore a version's files as a
                                         new version, then re-run the gates (202, or 200 with "wait")
    GET  /projects/pins?project=...&version=...  a version's note pins (engine/pins.py)
    POST /projects/pins                  {"project", "version", "pins":[...]}: replace that version's pins

    Make mode (engine/make.py): Ask -> Make -> Prove -> Shelf
    GET  /make/form                      the holder templates, their measured ranges and materials
    POST /make                           {"object", "shape", measurements, "material", "mount"}: a new
                                         project sized to the ask, gates queued (202); or {"project"}:
                                         remake it with the current calibrated clearance as a new version
    GET  /make/proof?project=&version=   one version's make record, verdict, print file and outcome
    POST /make/print                     {"project", "version", "fits": {fit: result}, "measurements"?:
                                         {feature: mm}, "photo"?: data URL} ("result" alone still
                                         rates the primary fit): record a physical print result
    GET  /make/photo?project=&version=   the photo recorded with that version's print
    GET  /make/shelf                     every project with its version history and print outcomes

Version requests on a project that has a run queued or in progress are refused (409), so a
run never sees its files change underneath it.

Bound to 127.0.0.1 and checks the Host header (refuses DNS rebinding). POST needs
Content-Type: application/json, which a web page cannot send cross-origin without a
preflight this server never answers. Runs execute one at a time, in order: the gates share
the CPU and the renderer, and a verdict must never depend on what else was running.
"""
import ast
import json
import queue
import re
import shutil
import tempfile
import threading
import traceback
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from harness.execute import run_worker
from harness.pipeline import material_fits
from harness.sweep import plan_samples

from . import make
from .proposal_session import ProposalSession
from .agents import ScriptedFakeAgent, ParameterEditAgent
from .joins import JoinAgent, preview_assembly, requested_joint
from .reviewer import ScriptedFakeReviewer, review_context, send_back_message
from .workspace import browse, choose_folder, is_project, list_projects, new_project, remember, starters
from .catalogue import BUILTIN, add_component, list_components, project_path
from .parameters import parameters_of, accepted_brief_edit
from .printers import PROFILE, project_printer, select_printer
from .pins import pin_document, save_pins
from .projects import (ARTIFACT_TYPES, ProjectError, artifact_path, designs_of, project_parts_list,
                       run_project, verdict_artifacts)
from .versions import (Conflict, create_project, list_versions, record_review, require_versioned,
                       restore_version, save_version, find_version, rebuild_version_artifacts, head, unsaved, git)

HOST = "127.0.0.1"
PORT = 8766  # the plain-JS UI server keeps 8765
API_VERSION = 1
TERMINAL = ("done", "error")  # "reviewing" (#28) is not terminal: the project stays busy
RUN_PATH = re.compile(r"^/runs/([0-9a-f]{32})(/events|/artifacts/(.+))?$")


class Run:
    def __init__(self, project, samples, timeout, slice=False):
        self.id = uuid.uuid4().hex
        self.project, self.samples, self.timeout, self.slice = project, samples, timeout, slice
        self.status, self.verdict, self.error = "queued", None, None
        self.created = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.events = []
        self.artifact_project = None
        self.changed = threading.Condition()
        # Set for a run started by accepting a proposal: what the reviewer judges after the gates pass (#28).
        self.review_request, self.review, self.send_back = None, None, None

    def emit(self, event):
        with self.changed:
            self.events.append({"id": len(self.events) + 1, **event})
            self.changed.notify_all()

    def set_status(self, status):
        with self.changed:
            self.status = status
            self.changed.notify_all()

    def summary(self):
        return {"id": self.id, "project": str(self.project), "status": self.status,
                "created": self.created, "slice": self.slice, "events": len(self.events), "verdict": self.verdict,
                "review": self.review,
                "error": self.error, "links": {"self": f"/runs/{self.id}",
                                               "events": f"/runs/{self.id}/events",
                                               "artifacts": f"/runs/{self.id}/artifacts/"}}


class Busy(Conflict):
    """The project has a run queued or in progress."""


class Engine:
    """The run registry and its single worker thread."""

    def __init__(self, agent=None, reviewer=None):
        self.runs, self.pending = {}, queue.Queue()
        self.proposals = {}
        self.agent = agent or ScriptedFakeAgent()
        self.reviewer = reviewer or ScriptedFakeReviewer()
        self.artifacts = tempfile.TemporaryDirectory(prefix="magic-cad-runs-")
        self.lock = threading.Lock()
        self.execution = threading.Lock()
        threading.Thread(target=self.work, name="engine-runs", daemon=True).start()

    def close(self):
        """Stop pending agent processes when the local service shuts down."""
        with self.lock:
            pending = [p for p in self.proposals.values() if p['state'] == 'pending']
        for proposal in pending:
            proposal['session'].reject()
            proposal['agent'].interrupt(proposal)
        self.reviewer.interrupt()

    def submit(self, project, samples=None, timeout=180, slice=False):
        project = Path(project).expanduser().resolve()
        designs_of(project)  # refuse a non-project before it is queued
        with self.lock:
            return self.queue(project, samples, timeout, slice)

    def queue(self, project, samples, timeout, slice=False):  # caller holds self.lock
        run = Run(project, samples, timeout, slice)
        self.runs[run.id] = run
        run.emit({"type": "queued", "project": str(project)})
        self.pending.put(run)
        return run

    def change(self, project, action, ignore=None):
        """Run a version change while no run of this project is queued or running (except `ignore`)."""
        project = require_versioned(project)
        with self.lock:
            if any(r.project == project and r.status not in TERMINAL and r is not ignore for r in self.runs.values()):
                raise Busy(f"{project} has a run in progress; try again when it finishes")
            return action(project)

    def save(self, project, message):
        return self.change(project, lambda p: save_version(p, message))

    def rollback(self, project, version, samples=None, timeout=180, slice=False):
        def act(p):
            new, target = restore_version(p, version)
            return new, target, self.queue(p, samples, timeout, slice)
        return self.change(project, act)

    def work(self):
        while True:
            run = self.pending.get()
            run.set_status("running")
            try:
                with self.execution:
                    _, run.verdict = run_project(run.project, run.emit, run.samples, run.timeout, run.slice)
                snapshot = Path(self.artifacts.name) / run.id
                for relative in ["verdict.json", *verdict_artifacts(run.verdict)]:
                    source = artifact_path(run.project, relative)
                    if source is None:
                        raise ProjectError(f"missing run artifact: {relative}")
                    target = snapshot / "outputs" / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)
                run.artifact_project = snapshot
                if run.review_request and run.verdict.get("pass"):
                    run.set_status("reviewing")  # not terminal: the project stays busy until the verdict lands
                    threading.Thread(target=self.review, args=(run,), name="engine-review", daemon=True).start()
                else:
                    run.set_status("done")
            except Exception as err:  # the run fails; the engine keeps serving
                run.error = f"{type(err).__name__}: {err}"
                run.emit({"type": "error", "error": run.error, "traceback": traceback.format_exc()})
                run.set_status("error")

    def review(self, run):
        """The independent reviewer's verdict on a passed run; a failed review goes back to the designer once."""
        request = run.review_request
        try:
            run.emit({"type": "review_started", "design": request["file"]})
            run.review = self.reviewer.review(review_context(run.project, request), run.emit)
            record_review(run.project, run.review)   # the verdict belongs to the version, like the gates'
            run.emit({"type": "review_finished", "review": run.review})
            if not run.review["pass"]:
                message = send_back_message(run.review)
                if request["round"] >= 1 or message is None or run.send_back is None:
                    run.emit({"type": "review_kept", "reason": "a reviewer fix was already sent back once for this change"
                              if request["round"] >= 1 else "the review named no fix the designer can act on"})
                else:
                    try:
                        proposal = run.send_back(message)
                        run.emit({"type": "sent_back", "proposal": proposal, "message": message})
                    except Exception as err:  # the review stands even if the designer cannot start
                        run.emit({"type": "send_back_failed", "error": str(err)})
        except Exception as err:  # an unavailable reviewer leaves the design unreviewed, not the run failed
            run.emit({"type": "review_error", "error": str(err)[:2000]})
        finally:
            run.set_status("done")

    def get(self, run_id):
        with self.lock:
            return self.runs.get(run_id)

    def all(self):
        with self.lock:
            return sorted(self.runs.values(), key=lambda r: r.created, reverse=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "MagicCADEngine/1"
    engine = None  # set by make_server

    def log_message(self, fmt, *args):  # quiet: the CLI prints its own lines
        pass

    def host_ok(self):
        port = self.server.server_address[1]
        if self.headers.get("Host") in {f"localhost:{port}", f"127.0.0.1:{port}"}:
            return True
        self.reply(HTTPStatus.FORBIDDEN, {"error": "unexpected Host header"})
        return False

    def reply(self, status, body):
        data = json.dumps(body, indent=2).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if not self.host_ok():
            return
        path = urlsplit(self.path).path
        if path == "/health":
            return self.reply(HTTPStatus.OK, {"engine": "magic-cad", "api": API_VERSION, "agent": getattr(self.engine.agent, "name", "scripted")})
        session_events = re.fullmatch(r"/proposals/([0-9a-f]{32})/events", path)
        if session_events:
            proposal = self.engine.proposals.get(session_events.group(1))
            if not proposal:
                return self.reply(HTTPStatus.NOT_FOUND, {"error": "no such session"})
            session = proposal["session"]
            try:
                sent = max(0, int(self.headers.get("Last-Event-ID", 0)))
            except ValueError:
                sent = 0
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                while True:
                    with session.changed:
                        session.changed.wait_for(lambda: len(session.events) > sent or session.state in ("ready", "error", "rejected"), timeout=15)
                        events = session.events[sent:]
                        ended = session.state in ("ready", "error", "rejected")
                    for event in events:
                        self.wfile.write(f"id: {event['id']}\nevent: {event['type']}\ndata: {json.dumps(event)}\n\n".encode())
                    sent += len(events)
                    if ended:
                        self.wfile.write(b"event: end\ndata: {}\n\n")
                        self.wfile.flush()
                        return
                    if not events:
                        self.wfile.write(b": keep-alive\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError):
                return
        proposal_match = re.fullmatch(r"/proposals/([0-9a-f]{32})", path)
        if proposal_match:
            proposal = self.engine.proposals.get(proposal_match.group(1))
            if not proposal:
                return self.reply(HTTPStatus.NOT_FOUND, {"error": "no such proposal"})
            return self.reply(HTTPStatus.OK, self.proposal_summary(proposal))
        preview = re.fullmatch(r"/proposals/([0-9a-f]{32})/preview/(before|after)/(\d+)", path)
        if preview:
            ident, side, index = preview.groups()
            proposal = self.engine.proposals.get(ident)
            parts = proposal["session"].previews.get(side, []) if proposal else []
            files = [part["stl"] for part in parts]
            if int(index) >= len(files):
                return self.reply(HTTPStatus.NOT_FOUND, {"error": "no such preview"})
            data = Path(files[int(index)]).read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "model/stl")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/make/photo":
            query = parse_qs(urlsplit(self.path).query)
            return self.guarded(lambda: self.make_photo(query.get("project", [""])[0], query.get("version", [""])[0]))
        if path in ("/make/form", "/make/shelf", "/make/proof"):
            query = parse_qs(urlsplit(self.path).query)
            if path == "/make/form":
                return self.guarded(lambda: (HTTPStatus.OK, make.form_spec()))
            if path == "/make/shelf":
                return self.guarded(lambda: (HTTPStatus.OK, make.shelf()))
            return self.guarded(lambda: (HTTPStatus.OK, make.proof(query.get("project", [""])[0],
                                                                   query.get("version", [""])[0])))
        if path == "/catalogue":
            project = parse_qs(urlsplit(self.path).query).get("project", [""])[0]
            return self.guarded(lambda: self.catalogue(project))
        if path == "/runs":
            return self.reply(HTTPStatus.OK, {"runs": [r.summary() for r in self.engine.all()]})
        if path == "/projects/parameters":
            query = parse_qs(urlsplit(self.path).query)
            project = query.get("project", [""])[0]
            design = query.get("design", [""])[0]
            return self.guarded(lambda: (HTTPStatus.OK, {"parameters": parameters_of(require_versioned(project), design)}))
        if path == "/workspace/projects":
            return self.guarded(lambda: (HTTPStatus.OK, list_projects()))
        if path == "/workspace/starters":
            return self.guarded(lambda: (HTTPStatus.OK, {"starters": starters()}))
        if path == "/workspace/browse":
            folder = parse_qs(urlsplit(self.path).query).get("path", [""])[0]
            return self.guarded(lambda: (HTTPStatus.OK, browse(folder or None)))
        if path == "/projects/designs":
            project = parse_qs(urlsplit(self.path).query).get("project", [""])[0]
            return self.guarded(lambda: (HTTPStatus.OK, {"designs": [p.name for p in designs_of(project)]}))
        if path == "/projects/printer":
            project = parse_qs(urlsplit(self.path).query).get("project", [""])[0]
            return self.guarded(lambda: (HTTPStatus.OK, project_printer(project)))
        if path == "/projects/versions":
            project = parse_qs(urlsplit(self.path).query).get("project", [""])[0]
            return self.guarded(lambda: (HTTPStatus.OK, {"project": project,
                                                         "versions": list_versions(project)}))
        if path == "/projects/parts-list":
            query = parse_qs(urlsplit(self.path).query)
            return self.guarded(lambda: self.parts_list(query))
        if path == "/projects/version-details":
            query = parse_qs(urlsplit(self.path).query)
            return self.guarded(lambda: self.version_details(query))
        if path == "/projects/version-artifacts":
            query = parse_qs(urlsplit(self.path).query)
            return self.guarded(lambda: self.version_artifact(query))
        if path == "/projects/pins":
            query = parse_qs(urlsplit(self.path).query)
            return self.guarded(lambda: (HTTPStatus.OK, pin_document(query.get("project", [""])[0], query.get("version", [""])[0])))
        match = RUN_PATH.match(path)
        run = self.engine.get(match.group(1)) if match else None
        if not run:
            return self.reply(HTTPStatus.NOT_FOUND, {"error": "no such run"})
        if match.group(2) == "/events":
            return self.stream(run)
        if match.group(3):
            return self.artifact(run, unquote(match.group(3)))
        return self.reply(HTTPStatus.OK, run.summary())

    def catalogue(self, project):
        components = list_components(project)
        builtin_count = len(json.loads(BUILTIN.read_text()))
        custom = project_path(project)
        def source(path):
            return {"path": str(path), "modified": path.stat().st_mtime} if path.is_file() else None
        shared_source, custom_source = source(BUILTIN), source(custom)
        return HTTPStatus.OK, {"components": [{**item, "_catalogue_file": shared_source if i < builtin_count else custom_source}
                                               for i, item in enumerate(components)]}

    def parts_list(self, query):
        document = project_parts_list(query.get("project", [""])[0])
        if query.get("format", ["json"])[0] != "csv":
            return HTTPStatus.OK, document
        from assembly.parts_list import to_csv
        data = to_csv(document).encode()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ARTIFACT_TYPES[".csv"])
        self.send_header("Content-Disposition", 'attachment; filename="parts_list.csv"')
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)
        return None

    def version_details(self, query):
        project = require_versioned(query.get("project", [""])[0])
        version = find_version(project, query.get("version", [""])[0])
        version_id = version["id"]
        paths = git(project, "ls-tree", "-r", "-z", "--name-only", version_id).split("\0")
        def files(prefix, suffixes):
            return [{"name": path, "content": git(project, "show", f"{version_id}:{path}")}
                    for path in paths if path.startswith(prefix) and path.endswith(suffixes)]
        report_path = project / ".magic" / "verdicts" / f"{version_id}.json"
        report = json.loads(report_path.read_text()) if report_path.is_file() else None
        return HTTPStatus.OK, {"briefs": files("briefs/", (".yaml", ".yml")),
                               "designs": files("designs/", (".py",)), "report": report}

    def version_artifact(self, query):
        project = require_versioned(query.get("project", [""])[0])
        version = find_version(project, query.get("version", [""])[0])
        snapshot = project / ".magic" / "artifacts" / version["id"]
        relative = query.get("path", [""])[0]
        if not relative:
            outputs = snapshot / "outputs"
            files = sorted(p.relative_to(outputs).as_posix() for p in outputs.rglob("*.stl")) if outputs.exists() else []
            return HTTPStatus.OK, {"models": files}
        target = artifact_path(snapshot, relative)
        if target is None:
            return HTTPStatus.NOT_FOUND, {"error": "no such artifact"}
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ARTIFACT_TYPES[target.suffix])
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)
        return None

    def make_photo(self, project, version):
        path = make.photo_path(project, version)
        if path is None:
            return HTTPStatus.NOT_FOUND, {"error": "no photo was recorded with this print"}
        data = path.read_bytes()
        kind = next(k for k, (suffix, _) in make.PHOTO_TYPES.items() if suffix == path.suffix)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(data)
        return None

    def guarded(self, act):
        """Reply with act()'s (status, body); a refused request becomes 400, 409 or 404."""
        try:
            result = act()
            if result is None:
                return
            status, body = result
        except Conflict as err:
            return self.reply(HTTPStatus.CONFLICT, {"error": str(err)})
        except ProjectError as err:
            return self.reply(HTTPStatus.BAD_REQUEST, {"error": str(err)})
        except (KeyError, TypeError, ValueError, AttributeError) as err:
            return self.reply(HTTPStatus.BAD_REQUEST, {"error": f"bad request: {err!r}"})
        if status is not None:
            return self.reply(status, body)

    def do_POST(self):
        if not self.host_ok():
            return
        path = urlsplit(self.path).path
        routes = {"/proposals": self.post_proposal, "/catalogue": self.post_catalogue, "/projects/printer": self.post_printer, "/runs": self.post_run, "/projects": self.post_project,
                  "/workspace/projects": self.post_workspace_project, "/workspace/recent": self.post_recent,
                  "/workspace/choose-folder": self.post_choose_folder,
                  "/projects/versions": self.post_version, "/projects/rollback": self.post_rollback,
                  "/projects/version-artifacts": self.post_version_artifacts, "/projects/pins": self.post_pins,
                  "/make": self.post_make, "/make/print": self.post_make_print}
        proposal_match = re.fullmatch(r"/proposals/([0-9a-f]{32})/(reject|accept|interrupt|resume)", path)
        if proposal_match:
            ident, action = proposal_match.groups()
            if action == "reject":
                routes[path] = lambda body: self.reject_proposal(ident)
            elif action == "accept":
                routes[path] = lambda body: self.accept_proposal(ident, body)
            else:
                routes[path] = lambda body: self.control_agent(ident, action)
        if path not in routes:
            return self.reply(HTTPStatus.NOT_FOUND, {"error": "no such endpoint"})
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            return self.reply(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, {"error": "send application/json"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            if not isinstance(body, dict):
                raise ValueError("send a JSON object")
        except ValueError as err:
            return self.reply(HTTPStatus.BAD_REQUEST, {"error": f"bad request: {err}"})
        return self.guarded(lambda: routes[path](body))

    @staticmethod
    def run_options(body):
        samples = body.get("samples")
        slice = body.get("slice", False)
        if not isinstance(slice, bool):
            raise ValueError("slice must be true or false")
        return (int(samples) if samples is not None else None), int(body.get("timeout", 180)), slice

    @staticmethod
    def finished(run, wait):
        if not wait:
            return HTTPStatus.ACCEPTED
        with run.changed:
            run.changed.wait_for(lambda: run.status in TERMINAL)
        return HTTPStatus.OK

    @staticmethod
    def proposal_summary(proposal):
        session = proposal["session"]
        with session.changed:
            previews = {side: [f"/proposals/{session.id}/preview/{side}/{i}" for i in range(len(parts))]
                        for side, parts in session.previews.items()}
            dimensions = {side: [part["bbox"]["size"] for part in parts]
                          for side, parts in session.previews.items()}
            return {"id": session.id, "state": session.state, "error": session.error,
                    "origin": proposal.get("origin"), "message": proposal.get("message"),
                    "changes": proposal["changes"], "previews": previews, "preview_dimensions": dimensions,
                    "selection": proposal.get("selection")}

    def post_proposal(self, body, origin=None, ignore=None):
        """origin: set when the engine itself proposes, sending a failed review's top fix back (#28)."""
        project = require_versioned(body["project"])
        ident = uuid.uuid4().hex
        folder = Path(self.engine.artifacts.name) / ("proposal-" + ident)
        draft = folder / "project"
        def prepare(project):
            if unsaved(project):
                raise Conflict("save project changes before proposing an edit")
            shutil.copytree(project, draft, ignore=shutil.ignore_patterns(".git", ".magic", "outputs", "__pycache__"))
            return head(project)
        base = self.engine.change(project, prepare, ignore=ignore)
        try:
            # Previews build with the same material fits an accepted run's gates use.
            fits = material_fits(project_printer(draft))
            agent = (ParameterEditAgent() if "parameter" in body else
                     JoinAgent() if requested_joint(body.get("message")) else self.engine.agent)
            proposal = agent.start(draft, body.get("brief"), body.get("selection"), body["parameter"] if "parameter" in body else body["message"])
        except Exception:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        proposal.update({"id": ident, "project": str(project), "state": "pending", "base": base, "agent": agent,
                         "origin": origin, "review_round": (origin or {}).get("round", 0), "message": body.get("message")})
        def build(side, cancel):
            if side == "after":
                (draft / proposal["file"]).write_text(proposal["source"])
            out = folder / side
            shutil.rmtree(out, ignore_errors=True)
            out.mkdir(parents=True)
            while not self.engine.execution.acquire(timeout=0.2):
                if cancel.is_set():
                    return {"ok": False, "interrupted": True}
            try:
                if proposal.get("kind") == "assembly":   # a joint (#54): the assembly gate is the preview
                    return preview_assembly(draft, out)
                return run_worker(draft / proposal["file"], out, fits=fits, cancel_event=cancel)
            finally:
                self.engine.execution.release()
        proposal["session"] = ProposalSession(ident, build, lambda: proposal["agent"].stream_events(proposal))
        with self.engine.lock:
            self.engine.proposals[ident] = proposal
        proposal["session"].start()
        return HTTPStatus.ACCEPTED, self.proposal_summary(proposal)

    def control_agent(self, ident, action):
        with self.engine.lock:
            proposal = self.engine.proposals.get(ident)
            if not proposal or proposal["state"] != "pending":
                raise ProjectError("no pending session")
            session = proposal["session"]
            if action == "resume":
                if session.state != "interrupted":
                    raise ValueError("session is not interrupted")
                proposal["agent"].resume(proposal)
                session.resume()
            else:
                session.interrupt()
                proposal["agent"].interrupt(proposal)
            return HTTPStatus.OK, {"id": ident, "state": session.state}

    def reject_proposal(self, ident):
        with self.engine.lock:
            proposal = self.engine.proposals.get(ident)
            if not proposal or proposal["state"] != "pending":
                raise ProjectError("no pending proposal")
            proposal["state"] = "rejected"
            proposal["session"].reject()
            proposal["agent"].interrupt(proposal)
            return HTTPStatus.OK, {"id": ident, "state": "rejected"}

    def accept_proposal(self, ident, body):
        proposal = self.engine.proposals.get(ident)
        if not proposal or proposal["state"] != "pending" or proposal["session"].state != "ready":
            raise ProjectError("no ready proposal")
        options = self.run_options(body)
        if options[0] is not None and options[0] <= 0 or options[1] <= 0:
            raise ProjectError("samples and timeout must be positive")
        tree = ast.parse(proposal["source"])
        params = next(node.value for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == "PARAMS" for target in node.targets))
        plan_samples(ast.literal_eval(params), options[0])
        def accept(project):
            if proposal["state"] != "pending" or proposal["session"].state != "ready":
                raise Conflict("proposal is no longer ready")
            if head(project) != proposal["base"] or unsaved(project):
                raise Conflict("project changed since this proposal; make a new proposal")
            target = project / proposal["file"]
            original = target.read_text()
            brief_edit = accepted_brief_edit(project, proposal["file"], proposal["changes"])
            try:
                target.write_text(proposal["source"])
                if brief_edit:
                    brief_edit[0].write_text(brief_edit[2])
                version = save_version(project, "Accepted proposed change")
            except Exception:
                target.write_text(original)
                if brief_edit:
                    brief_edit[0].write_text(brief_edit[1])
                raise
            proposal["state"] = "accepted"
            run = self.engine.queue(project, *options)
            # The design reviewer reads a design file; an assembly edit gets the gates' verdict only.
            run.review_request = None if proposal.get("kind") == "assembly" else {
                "file": proposal["file"], "changes": proposal["changes"], "round": proposal.get("review_round", 0)}
            run.send_back = lambda message: self.post_proposal(
                {"project": str(project), "message": message, "selection": {"design": Path(proposal["file"]).name}},
                origin={"run": run.id, "round": run.review_request["round"] + 1}, ignore=run)[1]["id"]
            return version, run
        version, run = self.engine.change(proposal["project"], accept)
        status = self.finished(run, body.get("wait"))
        return status, {"version": version, "run": run.summary()}

    def post_make(self, body):
        """Ask -> a sized version with its gates queued. {"project"} remakes an existing make."""
        options = self.run_options(body)
        if body.get("project"):
            folder, ask = body["project"], None
        else:
            folder, ask = make.create(body)
        def act(project):
            version = make.size(project, ask)
            return version, self.engine.queue(project, *options)
        version, run = self.engine.change(folder, act)
        return self.finished(run, body.get("wait")), {"project": str(run.project), "version": version,
                                                      "run": run.summary()}

    def post_make_print(self, body):
        return HTTPStatus.OK, make.record_print(body["project"], body["version"], body.get("result"),
                                                body.get("fits"), body.get("measurements"), body.get("photo"))

    def post_printer(self, body):
        project = Path(body["project"]).expanduser().resolve()
        designs_of(project)
        with self.engine.lock:
            if any(r.project == project and r.status not in TERMINAL for r in self.engine.runs.values()):
                raise Busy(f"{project} has a run in progress; try again when it finishes")
            result = select_printer(project, body.get("printer", PROFILE["id"]), body["material"])
        return HTTPStatus.OK, result

    def post_version_artifacts(self, body):
        version = rebuild_version_artifacts(body["project"], body["version"])
        return HTTPStatus.OK, {"version": version}

    def post_pins(self, body):
        save_pins(body["project"], body["version"], body["pins"])
        return HTTPStatus.OK, pin_document(body["project"], body["version"])

    def post_catalogue(self, body):
        with self.engine.lock:
            return HTTPStatus.CREATED, {"component": add_component(body["project"], body["component"])}

    def post_run(self, body):
        run = self.engine.submit(body["project"], *self.run_options(body))
        return self.finished(run, body.get("wait")), run.summary()

    def post_project(self, body):
        folder = create_project(body["folder"], body["from_design"])
        return HTTPStatus.CREATED, {"project": str(folder), "versions": list_versions(folder)}

    def post_workspace_project(self, body):
        folder = new_project(body.get("name"), body.get("starter"))
        return HTTPStatus.CREATED, {"project": str(folder), "versions": list_versions(folder)}

    def post_choose_folder(self, body):
        chosen = choose_folder()
        return HTTPStatus.OK, {"path": str(chosen) if chosen else None,
                               "project": bool(chosen) and is_project(chosen)}

    def post_recent(self, body):
        return HTTPStatus.OK, {"project": str(remember(body["project"]))}

    def post_version(self, body):
        return HTTPStatus.CREATED, {"version": self.engine.save(body["project"], body["message"])}

    def post_rollback(self, body):
        new, target, run = self.engine.rollback(body["project"], body["version"], *self.run_options(body))
        status = self.finished(run, body.get("wait"))
        if status == HTTPStatus.OK:  # the re-run has finished: report the verdict it earned
            new = next(v for v in list_versions(run.project) if v["id"] == new["id"])
        return status, {"version": new, "restored": target, "run": run.summary()}

    def stream(self, run):
        """SSE: replay from Last-Event-ID, then follow live until the run ends."""
        try:
            sent = int(self.headers.get("Last-Event-ID", 0))
        except ValueError:
            sent = 0
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            while True:
                with run.changed:
                    run.changed.wait_for(lambda: len(run.events) > sent or run.status in TERMINAL,
                                         timeout=15)
                    fresh, ended = run.events[sent:], run.status in TERMINAL
                for event in fresh:
                    self.wfile.write(f"id: {event['id']}\nevent: {event['type']}\n"
                                     f"data: {json.dumps(event)}\n\n".encode())
                sent += len(fresh)
                if ended and not fresh:
                    self.wfile.write(f"event: end\ndata: {json.dumps({'status': run.status})}\n\n".encode())
                    self.wfile.flush()
                    return
                if not fresh:
                    self.wfile.write(b": keep-alive\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return  # the client went away; the run carries on

    def artifact(self, run, relative):
        target = artifact_path(run.artifact_project, relative) if run.artifact_project else None
        if not target:
            return self.reply(HTTPStatus.NOT_FOUND, {"error": "no such artifact"})
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", ARTIFACT_TYPES[target.suffix])
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)


def make_server(port=PORT, engine=None):
    """A ready, not yet serving, engine server. port=0 picks a free port (tests)."""
    handler = type("EngineHandler", (Handler,), {"engine": engine or Engine()})
    server = ThreadingHTTPServer((HOST, port), handler)
    server.daemon_threads = True
    return server


def serve(port=PORT, agent="claude"):
    from .claude_agent import ClaudeCodeAgent
    from .reviewer import ClaudeCodeReviewer
    real = agent == "claude"
    server = make_server(port, Engine(agent=ClaudeCodeAgent() if real else ScriptedFakeAgent(),
                                      reviewer=ClaudeCodeReviewer() if real else ScriptedFakeReviewer()))
    print(f"Magic CAD engine API on http://{HOST}:{server.server_address[1]}  (Ctrl-C stops)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.RequestHandlerClass.engine.close()
        server.server_close()
    return 0
