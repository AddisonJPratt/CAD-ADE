"""Where projects live, so nobody has to type a path to find one (#66).

A browser page cannot learn a real folder path from the native folder picker, so the
engine supplies what the open screen shows:

    home()             the projects home: MAGIC_PROJECTS_HOME, or ~/Magic CAD Projects
    list_projects()    projects in the home plus recently opened ones, newest first
    remember(project)  record a project as opened (stored in <home>/.recent.json)
    starters()         the repo designs a new project can start from
    new_project(name, starter)   <home>/<name> as version 1
    browse(folder)     one folder's visible subfolders, with project folders marked
    choose_folder()    the macOS Finder folder panel, shown by the engine on this Mac

Everything stays on this computer. browse lists folder names only, never file contents.
"""
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from .projects import ProjectError
from .versions import ROOT, create_project, resolve_design

RECENT = ".recent.json"
RECENT_LIMIT = 12
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9 ._-]{0,79}")


def home():
    configured = os.environ.get("MAGIC_PROJECTS_HOME")
    return Path(configured or "~/Magic CAD Projects").expanduser().resolve()


def is_project(folder):
    folder = Path(folder)
    try:
        return folder.is_dir() and any(not p.name.startswith("_") for p in (folder / "designs").glob("*.py"))
    except OSError:
        return False


def _stamp(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat(timespec="seconds")


def _modified(folder):
    """The newest change to the project's own files: its designs, briefs and versions."""
    paths = [folder / "designs", folder / "briefs", folder / ".git" / "logs" / "HEAD", folder / "assembly.py"]
    paths += list((folder / "designs").glob("*.py"))
    times = [p.stat().st_mtime for p in paths if p.exists()]
    return max(times or [folder.stat().st_mtime])


def _recent():
    try:
        entries = json.loads((home() / RECENT).read_text())
    except (OSError, ValueError):
        return []
    return [e for e in entries if isinstance(e, dict) and isinstance(e.get("path"), str)
            and isinstance(e.get("opened"), str)]


def remember(project):
    """Record project as just opened. Only real projects are remembered."""
    project = Path(project).expanduser().resolve()
    if not is_project(project):
        raise ProjectError(f"not a project: {project}")
    entries = [e for e in _recent() if e["path"] != str(project)]
    entries.insert(0, {"path": str(project), "opened": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    home().mkdir(parents=True, exist_ok=True)
    (home() / RECENT).write_text(json.dumps(entries[:RECENT_LIMIT], indent=2) + "\n")
    return project


def list_projects():
    """Projects in the home folder and recently opened ones, most recently used first."""
    root = home()
    opened = {e["path"]: e["opened"] for e in _recent()}
    found = {}
    if root.is_dir():
        for child in root.iterdir():
            if not child.name.startswith(".") and is_project(child):
                found[str(child.resolve())] = child.resolve()
    for path in opened:
        if path not in found and is_project(path):
            found[path] = Path(path)
    projects = []
    for path, folder in found.items():
        projects.append({"name": folder.name, "path": path, "in_home": folder.parent == root,
                         "opened": opened.get(path), "modified": _stamp(_modified(folder))})
    projects.sort(key=lambda p: max(p["opened"] or "", p["modified"]), reverse=True)
    return {"home": str(root), "user_home": str(Path.home().resolve()), "projects": projects}


def _summary(brief):
    """The first sentence of a brief's function, for the starter list."""
    import yaml
    try:
        text = yaml.safe_load(brief.read_text()).get("function")
    except (OSError, ValueError, AttributeError, yaml.YAMLError):
        return ""
    words = " ".join(str(text or "").split())
    first = re.split(r"(?<=[a-z0-9)])\. ", words, maxsplit=1)[0].rstrip(".")
    return first + "." if first else ""


def _docstring_summary(design):
    """The design module's first docstring sentence, minus any "See <brief>" pointer."""
    import ast
    try:
        text = ast.get_docstring(ast.parse(design.read_text())) or ""
    except (OSError, SyntaxError, ValueError):
        return ""
    first = " ".join(text.split("\n\n")[0].split())
    first = re.split(r"\.?\s+See\b", first, maxsplit=1)[0].rstrip(".")
    return first + "." if first else ""


def starters():
    """Repo designs a new project can start from, with a one-line description from the brief."""
    items = []
    for design in sorted((ROOT / "designs").glob("*.py")):
        if design.name.startswith("_"):
            continue
        _, brief = resolve_design(str(design))
        items.append({"id": design.stem, "label": design.stem.replace("_", " ").capitalize(),
                      "summary": (_summary(brief) if brief else "") or _docstring_summary(design)})
    return items


def new_project(name, starter):
    """Create <home>/<name> from a starter design as version 1."""
    name = (name or "").strip() if isinstance(name, str) else ""
    if not NAME.fullmatch(name) or name.endswith((".", " ")):
        raise ProjectError("use a name of letters, numbers, spaces, dots, dashes or underscores (80 at most)")
    if starter not in {s["id"] for s in starters()}:
        raise ProjectError(f"no such starter: {starter}")
    folder = home() / name
    if folder.exists():
        raise ProjectError(f"a project named {name} already exists")
    home().mkdir(parents=True, exist_ok=True)
    create_project(folder, starter)
    remember(folder)
    return folder


def browse(folder=None):
    """One folder's visible subfolders, projects marked. Starts at the projects home once it
    exists, otherwise at the user's home folder."""
    target = Path(folder).expanduser() if folder else home() if home().is_dir() else Path.home()
    if not target.is_absolute():
        raise ProjectError("browse needs an absolute folder")
    target = target.resolve()
    if not target.is_dir():
        raise ProjectError(f"not a folder: {target}")
    entries = []
    try:
        children = list(target.iterdir())
    except PermissionError:
        raise ProjectError(f"this computer does not allow reading {target}")
    for child in children:
        try:
            if child.name.startswith(".") or not child.is_dir():
                continue
        except OSError:
            continue
        entries.append({"name": child.name, "path": str(child), "project": is_project(child)})
    entries.sort(key=lambda e: (not e["project"], e["name"].lower()))
    parent = target.parent if target.parent != target else None
    return {"path": str(target), "parent": str(parent) if parent else None,
            "project": is_project(target), "home": str(home()), "entries": entries}


CHOOSE = ["-e", "on run argv", "-e", "activate",
          "-e", "POSIX path of (choose folder with prompt (item 1 of argv) default location (POSIX file (item 2 of argv)))",
          "-e", "end run"]


def choose_folder(prompt="Choose a Magic CAD project folder"):
    """Show the native macOS folder panel. Returns the chosen folder, or None if cancelled."""
    if sys.platform != "darwin":
        raise ProjectError("the Finder folder panel is only available on macOS; use Browse")
    start = home() if home().is_dir() else Path.home()
    try:
        done = subprocess.run(["osascript", *CHOOSE, prompt, str(start)], capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return None
    if done.returncode:
        if "-128" in done.stderr:  # the user pressed Cancel
            return None
        raise ProjectError("the Finder folder panel could not open: " + done.stderr.strip()[:300])
    chosen = done.stdout.strip()
    return Path(chosen).resolve() if chosen else None
