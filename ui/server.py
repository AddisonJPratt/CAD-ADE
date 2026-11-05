#!/usr/bin/env python3
"""Magic CAD studio UI server. Read-only: it reports project files and never writes them.

Run from the project root: .venv/bin/python ui/server.py
"""
import base64
import hashlib
import json
import re
import sys
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

import yaml

HOST = "127.0.0.1"  # local workbench: never exposed beyond this machine
PORT = 8765

UI = Path(__file__).resolve().parent
ROOT = UI.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/styles.css": ("styles.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/assembly.css": ("assembly.css", "text/css; charset=utf-8"),
    "/assembly.js": ("assembly.js", "text/javascript; charset=utf-8"),
    "/studio.css": ("studio.css", "text/css; charset=utf-8"),
    "/studio.js": ("studio.js", "text/javascript; charset=utf-8"),
    "/studio-core.js": ("studio-core.js", "text/javascript; charset=utf-8"),
    "/vendor/three.module.js": ("vendor/three.module.js", "text/javascript; charset=utf-8"),
    "/vendor/OrbitControls.js": ("vendor/OrbitControls.js", "text/javascript; charset=utf-8"),
    "/vendor/STLLoader.js": ("vendor/STLLoader.js", "text/javascript; charset=utf-8"),
    "/vendor/BufferGeometryUtils.js": ("vendor/BufferGeometryUtils.js", "text/javascript; charset=utf-8"),
    "/vendor/RoomEnvironment.js": ("vendor/RoomEnvironment.js", "text/javascript; charset=utf-8"),
}
RUN_FILE_TYPES = {".png": "image/png", ".stl": "model/stl"}
IMPORT_MAP = re.compile(rb'<script type="importmap">(.*?)</script>', re.DOTALL)
STEM = re.compile(r"[A-Za-z0-9_-]{1,100}")
RUN_FOLDER = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]{0,99}")
ALLOWED_HOSTS = {f"localhost:{PORT}", f"127.0.0.1:{PORT}"}  # refuses DNS rebinding
TOLERANCE = re.compile(r"±\s*([0-9.]*[0-9])")


def rel(path):
    return path.relative_to(ROOT).as_posix()


def iso_mtime(path):
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds")


def source_of(path):
    return {"path": rel(path), "modified": iso_mtime(path)}


def read_json(path):
    """Parsed JSON, or None when the file is missing or unreadable (reported as absent)."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def run_mode(command):
    match = re.search(r"magic\.py\s+(\w+)", command) if isinstance(command, str) else None
    return match.group(1) if match else None


def gates_of(report):
    gates = report.get("gates")
    return [g for g in gates if isinstance(g, dict)] if isinstance(gates, list) else []


def all_runs():
    """Every readable runs/*/report.json, newest first. `_` folders are negative-control fixtures."""
    runs = []
    for path in (ROOT / "runs").glob("*/report.json"):
        if path.parent.name.startswith("_"):
            continue
        report = read_json(path)
        if isinstance(report, dict):
            runs.append((path.stat().st_mtime, path, report))
    runs.sort(key=lambda run: run[0], reverse=True)
    return runs


def runs_of(stem):
    # The report's own design field decides ownership, not the folder name: a run folder
    # can have any name, and negative-control fixtures also live under runs/.
    return [run for run in all_runs() if run[2].get("design") == f"{stem}.py"]


def run_summary(path, report):
    return {
        **source_of(path),
        "design": report.get("design"),
        "mode": run_mode(report.get("command")),
        "pass": report.get("pass"),
        "gates": [{"name": g.get("name"), "status": g.get("status")} for g in gates_of(report)],
    }


def is_full_run(report):
    """A run mode report whose every gate passed, exports included."""
    gates = gates_of(report)
    return run_mode(report.get("command")) == "run" and bool(gates) and all(g.get("status") == "PASS" for g in gates)


def last_full_run(stem, runs):
    return next(({**run_summary(p, r), "changed_since": changed_since(stem, p)} for _, p, r in runs if is_full_run(r)), None)


def changed_since(stem, path):
    """Inputs modified after this run, so its results may no longer describe them."""
    inputs = [ROOT / "designs" / f"{stem}.py", ROOT / "briefs" / f"{stem}.yaml",
              ROOT / "library" / "standard_parts.json", ROOT / "magic.py", *(ROOT / "harness").glob("*.py")]
    ran = path.stat().st_mtime
    return [rel(p) for p in inputs if p.exists() and p.stat().st_mtime > ran]


def brief_path(stem):
    for folder in ("briefs", "evals/briefs"):
        path = ROOT / folder / f"{stem}.yaml"
        if path.exists():
            return path
    return None


def newest_eval_path():
    paths = list((ROOT / "evals" / "results").glob("*/eval_report.json"))
    return max(paths, key=lambda p: p.stat().st_mtime) if paths else None


def last_full_eval():
    """Newest eval not in quick mode, because a quick eval skips the sweep."""
    paths = sorted((ROOT / "evals" / "results").glob("*/eval_report.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for path in paths:
        report = read_json(path)
        summary = report.get("summary") if isinstance(report, dict) else None
        if isinstance(summary, dict) and summary.get("mode") == "full":
            return {**source_of(path), "generated_at": report.get("generated_at"), "summary": summary, "briefs": [
                {"name": b.get("name"), "status": b.get("status"), "parametric": b.get("parametric")}
                for b in report.get("briefs", []) if isinstance(b, dict) and b.get("parametric")]}
    return None


def eval_payload():
    path = newest_eval_path()
    if path is None:
        return None
    report = read_json(path)
    if not isinstance(report, dict):
        return None
    runs = len(list((ROOT / "evals" / "results").glob("*/eval_report.json")))
    return {**report, "_source": source_of(path), "_eval_runs_on_disk": runs, "_last_full_eval": last_full_eval()}


def unverified_inputs():
    """What the harness leans on but nothing has measured, as CLAUDE.md itself declares it."""
    try:
        claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    except OSError:
        return {"printer_placeholder": None, "clearances_uncalibrated": None}
    return {"printer_placeholder": "EDIT ME" in claude, "clearances_uncalibrated": "not yet calibrated" in claude}


def prints_logged():
    prints = ROOT / "prints"
    return sum(1 for p in prints.iterdir() if not p.name.startswith(".")) if prints.exists() else 0


def all_stems():
    stems = {p.stem for p in (ROOT / "designs").glob("*.py") if not p.name.startswith("_")}
    return stems | {p.stem for folder in ("briefs", "evals/briefs") for p in (ROOT / folder).glob("*.yaml")}


def status_of(has_design, runs):
    if not has_design:
        return "NO_DESIGN"
    if not runs:
        return "NO_RUN"
    latest = runs[0][2].get("pass")
    return "PASS" if latest is True else "FAIL" if latest is False else None


def overview():
    stems = all_stems()
    evals = eval_payload()
    eval_status = {row.get("name"): row.get("status") for row in (evals or {}).get("briefs", [])}

    designs = []
    for stem in sorted(stems):
        has_design = (ROOT / "designs" / f"{stem}.py").exists()
        runs = runs_of(stem) if has_design else []
        latest = None
        if runs:
            _, path, report = runs[0]
            latest = {**run_summary(path, report), "changed_since": changed_since(stem, path)}
        designs.append({
            "stem": stem,
            "status": status_of(has_design, runs),
            "has_design": has_design,
            "has_brief": (ROOT / "briefs" / f"{stem}.yaml").exists(),
            "has_eval_brief": (ROOT / "evals" / "briefs" / f"{stem}.yaml").exists(),
            "eval_status": eval_status.get(stem),
            "run_count": len(runs),
            "latest_run": latest,
            "last_full_run": last_full_run(stem, runs),
        })
    # Designs with evidence first: they are what the reader came for.
    designs.sort(key=lambda d: (d["run_count"] == 0, not d["has_design"], d["stem"]))

    runs = all_runs()
    return {
        "designs": designs,
        "latest_eval": None if evals is None else {
            "summary": evals.get("summary"),
            "generated_at": evals.get("generated_at"),
            "source": evals.get("_source"),
            "sweep_skipped": any(g.get("name") == "Sweep" and g.get("status") == "NOT RUN"
                                 for b in evals.get("briefs", []) for g in b.get("gates", [])),
            "last_full": evals.get("_last_full_eval"),
        },
        "latest_run": run_summary(runs[0][1], runs[0][2]) if runs else None,
        "prints_logged": prints_logged(),
        "unverified": unverified_inputs(),
    }


def render_entry(path_text):
    """A report's render path (relative or absolute) as a servable URL, or None if gone."""
    path = Path(path_text)
    path = path if path.is_absolute() else ROOT / path
    try:
        resolved = path.resolve()
        resolved.relative_to(ROOT / "runs")
    except (OSError, ValueError):
        return {"view": path.stem, "url": None}
    return {"view": path.stem, "url": "/" + rel(resolved) if resolved.is_file() else None}


def design_payload(stem, run_folder=None):
    runs = runs_of(stem)
    if not (ROOT / "designs" / f"{stem}.py").exists():
        return HTTPStatus.NOT_FOUND, {"stem": stem, "status": "NO_DESIGN", "message": f"designs/{stem}.py does not exist."}
    if not runs:
        return HTTPStatus.NOT_FOUND, {"stem": stem, "status": "NO_RUN", "message": f"No runs/*/report.json names {stem}.py."}
    chosen = runs[0]
    if run_folder is not None:
        chosen = next((run for run in runs if run[1].parent.name == run_folder), None)
        if chosen is None:
            return HTTPStatus.NOT_FOUND, {"stem": stem, "status": "NO_RUN", "message": f"No run folder {run_folder} holds a report for {stem}.py."}
    _, path, report = chosen
    gates = {g.get("name"): g.get("detail") or "" for g in gates_of(report)}
    tolerance = TOLERANCE.search(gates.get("2 Geometry", ""))
    return HTTPStatus.OK, {
        **report,
        "_stem": stem,
        "_status": "OK",
        "_source": source_of(path),
        "_mode": run_mode(report.get("command")),
        "_is_newest": path == runs[0][1],
        "_changed_since": changed_since(stem, path),
        "_last_full_run": last_full_run(stem, runs),
        "_prints_logged": prints_logged(),
        "_unverified": unverified_inputs(),
        "_tolerance_mm": float(tolerance.group(1)) if tolerance else None,
        "_render_files": [render_entry(r) for r in report.get("renders", [])],
        "_runs": [{**run_summary(p, r), "folder": p.parent.name} for _, p, r in runs],
    }


def brief_payload(stem):
    path = brief_path(stem)
    if path is None:
        return HTTPStatus.NOT_FOUND, {"stem": stem, "status": "NO_BRIEF", "message": f"No {stem}.yaml in briefs/ or evals/briefs/."}
    try:
        brief = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, ValueError) as error:
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"stem": stem, "status": "BAD_BRIEF", "message": f"{rel(path)} is not valid YAML: {error}"}
    if not isinstance(brief, dict):
        return HTTPStatus.INTERNAL_SERVER_ERROR, {"stem": stem, "status": "BAD_BRIEF", "message": f"{rel(path)} is not a mapping."}
    return HTTPStatus.OK, {
        **brief,
        "_stem": stem,
        "_status": "OK",
        "_source": source_of(path),
        "_has_design": (ROOT / "designs" / f"{stem}.py").exists(),
    }


def library_payload(project=None):
    path = ROOT / "library" / "standard_parts.json"
    data = read_json(path)
    if not isinstance(data, dict):
        return HTTPStatus.NOT_FOUND, {"status": "NO_LIBRARY", "message": "library/standard_parts.json is missing or unreadable."}
    if project:
        from engine.catalogue import list_components
        from engine.projects import ProjectError
        try:
            components = list_components(project)
        except (ProjectError, ValueError, OSError) as error:
            return HTTPStatus.BAD_REQUEST, {"status": "BAD_PROJECT", "message": str(error)}
    else:
        components = read_json(ROOT / "library" / "components.json")
    return HTTPStatus.OK, {**data, "_components": components if isinstance(components, list) else [],
                           "_project": project or "", "_source": source_of(path)}


def model_run(runs):
    """The newest run whose folder holds STL files: a check run keeps no exports, so it can't be shown."""
    return next((run for run in runs if any(run[1].parent.glob("*.stl"))), None)


def studio_list():
    designs = []
    for stem in all_stems():
        has_design = (ROOT / "designs" / f"{stem}.py").exists()
        runs = runs_of(stem) if has_design else []
        chosen = model_run(runs)
        designs.append({"stem": stem, "status": status_of(has_design, runs), "has_model": chosen is not None,
                        "_model_time": chosen[0] if chosen else 0})
    designs.sort(key=lambda d: (not d["has_model"], d["stem"]))
    newest = max(designs, key=lambda d: d["_model_time"], default=None)
    for design in designs:
        del design["_model_time"]
    return {"designs": designs, "default": newest["stem"] if newest and newest["has_model"] else None}


def one_line_function(stem):
    """The brief's first sentence, or None when there is no readable brief."""
    path = brief_path(stem)
    try:
        brief = yaml.safe_load(path.read_text(encoding="utf-8")) if path else None
    except (yaml.YAMLError, ValueError):
        return None
    text = brief.get("function") if isinstance(brief, dict) else None
    return re.split(r"(?<=[.!?])\s", " ".join(text.split()))[0] if isinstance(text, str) and text.strip() else None


def run_digest(path, report):
    gates = gates_of(report)
    return {**source_of(path), "folder": path.parent.name, "mode": run_mode(report.get("command")), "pass": report.get("pass"),
            "gates": [{"name": g.get("name"), "status": g.get("status"), "detail": g.get("detail") or ""} for g in gates]}


def studio_payload(stem):
    has_design = (ROOT / "designs" / f"{stem}.py").exists()
    if stem not in all_stems():
        return HTTPStatus.NOT_FOUND, {"stem": stem, "status": "NOT_FOUND", "message": f"No design or brief called {stem}."}
    runs = runs_of(stem) if has_design else []
    chosen = model_run(runs)
    payload = {"stem": stem, "status": status_of(has_design, runs), "function": one_line_function(stem),
               "newest_run": run_digest(runs[0][1], runs[0][2]) if runs else None, "model": None}
    if chosen is not None:
        _, path, report = chosen
        geometry = report.get("geometry") if isinstance(report.get("geometry"), dict) else {}
        stls = sorted(path.parent.glob("*.stl"))
        payload["model"] = {
            **run_digest(path, report),
            "is_newest_run": path == runs[0][1],
            "changed_since": changed_since(stem, path),
            # A run that skipped exports can sit beside STLs left by an earlier run in the same folder.
            "exports_written": any(g.get("name") == "5 Exports" and g.get("status") == "PASS" for g in gates_of(report)),
            "bbox": geometry.get("bbox"),
            "volume": geometry.get("volume"),
            "parts": [{"name": stl.stem, "url": "/" + quote(rel(stl)), "bytes": stl.stat().st_size} for stl in stls],
        }
    return HTTPStatus.OK, payload


def inline_script_csp(html):
    """The page's one inline script is the import map; it is allowed by hash, not by 'unsafe-inline'."""
    match = IMPORT_MAP.search(html)
    return f" 'sha256-{base64.b64encode(hashlib.sha256(match.group(1)).digest()).decode()}'" if match else ""


class Handler(BaseHTTPRequestHandler):
    server_version = "MagicCADStudio/0"

    def respond(self, status, body, content_type, script_hash=""):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")  # the UI always reflects files on disk
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; script-src 'self'" + script_hash + "; style-src 'self'; style-src-attr 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; base-uri 'none'; form-action 'none'")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_json(self, status, data):
        self.respond(status, json.dumps(data, ensure_ascii=False, default=str).encode(), "application/json; charset=utf-8")

    def api(self, path):
        if path == "/api/assembly/demo":
            from assembly.demo import get_demo
            return HTTPStatus.OK, get_demo(ROOT)
        if path == "/api/overview":
            return HTTPStatus.OK, overview()
        if path == "/api/evals":
            data = eval_payload()
            if data is None:
                return HTTPStatus.NOT_FOUND, {"status": "NO_EVALS", "message": "No readable evals/results/*/eval_report.json."}
            return HTTPStatus.OK, data
        if path == "/api/library":
            project = parse_qs(urlsplit(self.path).query).get("project", [None])[0]
            return library_payload(project)
        if path == "/api/studio":
            return HTTPStatus.OK, studio_list()
        match = re.fullmatch(r"/api/(design|brief|studio)/([^/]+)", path)
        if match:
            stem = unquote(match.group(2))
            if not STEM.fullmatch(stem):
                return HTTPStatus.BAD_REQUEST, {"status": "BAD_STEM", "message": "A design stem has only letters, digits, _ and -."}
            if match.group(1) == "brief":
                return brief_payload(stem)
            if match.group(1) == "studio":
                return studio_payload(stem)
            run = parse_qs(urlsplit(self.path).query).get("run", [None])[0]
            if run is not None and not RUN_FOLDER.fullmatch(run):
                return HTTPStatus.BAD_REQUEST, {"status": "BAD_RUN", "message": "A run folder has only letters, digits, ., _ and -."}
            return design_payload(stem, run)
        return HTTPStatus.NOT_FOUND, {"status": "NOT_FOUND", "message": f"No endpoint at {path}."}

    def serve_run_file(self, path):
        # Only PNGs and STLs that really sit under runs/; resolve() defeats ../ and symlinks.
        name = unquote(path).lstrip("/")
        if "\0" in name:
            return self.send_json(HTTPStatus.NOT_FOUND, {"status": "NOT_FOUND", "message": "Not a render or model."})
        target = (ROOT / name).resolve()
        try:
            target.relative_to(ROOT / "runs")
        except ValueError:
            return self.send_json(HTTPStatus.NOT_FOUND, {"status": "NOT_FOUND", "message": "Not a render or model."})
        content_type = RUN_FILE_TYPES.get(target.suffix.lower())
        if content_type is None or not target.is_file():
            return self.send_json(HTTPStatus.NOT_FOUND, {"status": "NOT_FOUND", "message": "Not a render or model."})
        self.respond(HTTPStatus.OK, target.read_bytes(), content_type)

    def do_GET(self):
        path = urlsplit(self.path).path
        if self.headers.get("Host") not in ALLOWED_HOSTS:
            return self.send_json(HTTPStatus.FORBIDDEN, {"status": "BAD_HOST", "message": "This studio answers on localhost only."})
        try:
            if path.startswith("/api/"):
                status, data = self.api(path)
                return self.send_json(status, data)
            if path == "/assembly/assets/m3_socket_head.stl":
                asset_root = (ROOT / "assembly" / "assets").resolve()
                asset = (asset_root / "m3_socket_head.stl").resolve()
                if asset.parent != asset_root or not asset.is_file():
                    return self.send_json(HTTPStatus.NOT_FOUND, {"status": "NOT_FOUND", "message": "Assembly hardware mesh not found."})
                return self.respond(HTTPStatus.OK, asset.read_bytes(), "model/stl")
            if path.startswith("/runs/"):
                return self.serve_run_file(path)
            if path in STATIC:
                name, content_type = STATIC[path]
                body = (UI / name).read_bytes()
                return self.respond(HTTPStatus.OK, body, content_type, inline_script_csp(body) if name == "index.html" else "")
            return self.send_json(HTTPStatus.NOT_FOUND, {"status": "NOT_FOUND", "message": f"Nothing at {path}."})
        except Exception as error:  # a malformed project file must become a visible state, not a dropped connection
            return self.send_json(HTTPStatus.INTERNAL_SERVER_ERROR, {"status": "READ_ERROR", "message": f"{type(error).__name__} while answering {path}. A project file may be malformed."})

    do_HEAD = do_GET

    def log_message(self, *_):
        pass


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Magic CAD studio: http://localhost:{PORT}  (Ctrl-C to stop)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
