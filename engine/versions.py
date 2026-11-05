"""Project creation, versions and rollback. Versions are commits of a git repository inside the
project folder; callers only ever see versions (number, id, message, timestamp, verdict).

What a version holds: the project's source files (designs, brief cards, the assembly file
later). Generated files in outputs/ are not versioned: they are rebuilt by the gates, which is
why a rollback re-runs them. The verdict each version earned is kept beside the repository in
.magic/verdicts/<id>.json, written whenever a run finishes on a clean, saved version.
"""
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from .projects import OUTPUTS, ProjectError, designs_of

ROOT = Path(__file__).resolve().parent.parent
STATE = ".magic"
IGNORED = [f"/{OUTPUTS}/", f"/{STATE}/", "__pycache__/", "*.py[cod]"]
# Identity and safety for the project's own repository: never the user's hooks, signing or editor.
GIT = ["git", "-c", "user.name=Magic CAD", "-c", "user.email=magic-cad@localhost",
       "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", "-c", "core.autocrlf=false"]


class VersionError(ProjectError):
    """A version request that cannot be honoured (no message, unknown version, no versions)."""


class Conflict(VersionError):
    """A valid request the project's current state refuses (nothing to save, unsaved edits)."""


def git(project, *args, check=True):
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": os.devnull}
    proc = subprocess.run([*GIT, *args], cwd=project, capture_output=True, text=True, env=env)
    if check and proc.returncode:
        raise VersionError(f"version store: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.stdout


def is_versioned(project):
    return (Path(project) / ".git").is_dir()


def require_versioned(project):
    project = Path(project).expanduser().resolve()
    designs_of(project)
    if not is_versioned(project):
        raise VersionError(f"{project} has no versions; create it as a project first")
    return project


def unsaved(project):
    """Source files changed since the last saved version."""
    return [line[3:] for line in git(project, "status", "--porcelain", "--untracked-files=all").splitlines()]


def head(project):
    return git(project, "rev-parse", "HEAD").strip()


def resolve_design(source):
    """A repo design stem ("wall_bracket") or a path to a design .py -> (design, brief or None)."""
    path = Path(source).expanduser()
    if path.suffix != ".py":
        path = ROOT / "designs" / f"{source}.py"
    if not path.is_file():
        raise ProjectError(f"no such design: {source}")
    candidates = [path.resolve().parent.parent / "briefs" / f"{path.stem}.yaml",
                  path.with_suffix(".yaml"), ROOT / "evals" / "briefs" / f"{path.stem}.yaml"]
    return path, next((c for c in candidates if c.is_file()), None)


def create_project(folder, from_design):
    """A new self-contained project folder holding one design (and its brief), as version 1."""
    folder = Path(folder).expanduser().resolve()
    if folder.exists() and any(folder.iterdir()):
        raise ProjectError(f"{folder} already exists and is not empty")
    design, brief = resolve_design(from_design)
    (folder / "designs").mkdir(parents=True, exist_ok=True)
    shutil.copy2(design, folder / "designs" / design.name)
    source_library = design.resolve().parent.parent / "library"
    if not (source_library / "__init__.py").is_file():
        source_library = ROOT / "library"
    shutil.copytree(source_library, folder / "library",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if brief:
        (folder / "briefs").mkdir(exist_ok=True)
        shutil.copy2(brief, folder / "briefs" / f"{design.stem}.yaml")
    (folder / ".gitignore").write_text("\n".join(IGNORED) + "\n")
    git(folder, "init", "--quiet", "--initial-branch=main")
    save_version(folder, f"Created from {design.stem}")
    return folder


def save_version(project, message):
    """Commit the project's current source files as a new version. Returns that version."""
    project = Path(project).expanduser().resolve()
    message = (message or "").strip()
    if not message:
        raise VersionError("a version needs a message")
    if is_versioned(project) and head_exists(project) and not unsaved(project):
        raise Conflict("nothing changed since the last version")
    git(project, "add", "--all")
    git(project, "commit", "--quiet", "--message", message)
    return list_versions(project)[0]


def head_exists(project):
    return bool(git(project, "rev-parse", "--verify", "--quiet", "HEAD", check=False).strip())


def list_versions(project):
    """The timeline, newest first: number (1 = first), id, message, timestamp, current, verdict."""
    project = require_versioned(project)
    lines = git(project, "log", "--format=%H%x1f%aI%x1f%B%x1e").split("\x1e")
    rows = [line.strip("\n").split("\x1f") for line in lines if line.strip()]
    current = head(project)
    total = len(rows)
    return [{"number": total - i, "id": vid, "timestamp": stamp, "message": body.strip(),
             "current": vid == current, "verdict": verdict_of(project, vid)}
            for i, (vid, stamp, body) in enumerate(rows)]


def find_version(project, ref):
    """A version by id (full or a unique prefix) or by number."""
    versions = list_versions(project)
    ref = str(ref).strip()
    matches = [v for v in versions if ref.isdigit() and v["number"] == int(ref)] or \
              [v for v in versions if len(ref) >= 7 and v["id"].startswith(ref)]
    if len(matches) != 1:
        raise VersionError(f"no such version: {ref}")
    return matches[0]


def restore_version(project, ref):
    """Make the project's files those of a past version, recorded as a new version on top.

    The timeline only ever grows: rolling back never discards a later version. Unsaved edits
    are refused rather than overwritten.
    """
    project = require_versioned(project)
    target = find_version(project, ref)
    changed = unsaved(project)
    if changed:
        raise Conflict(f"unsaved changes would be lost: {', '.join(changed[:5])}")
    if target["current"]:
        raise Conflict(f"version {target['number']} is already the current version")
    git(project, "rm", "-r", "--quiet", "--cached", "--ignore-unmatch", ".")
    for stale in git(project, "ls-files", "--others", "--exclude-standard").splitlines():
        (project / stale).unlink()
    git(project, "checkout", target["id"], "--", ".")  # exactly that version's files, no others
    git(project, "add", "--all")
    git(project, "commit", "--quiet", "--allow-empty", "--message",
        f"Rolled back to version {target['number']}: {target['message'].splitlines()[0]}")
    return list_versions(project)[0], target


def verdict_of(project, version_id):
    path = Path(project) / STATE / "verdicts" / f"{version_id}.json"
    if not path.is_file():
        return None
    verdict = json.loads(path.read_text())
    return {"pass": verdict["pass"], "finished": verdict.get("finished"),
            "designs": [{"design": d["design"], "pass": d["pass"]} for d in verdict["designs"]]}


def record_verdict(project, verdict):
    """Keep a run's verdict against the saved version it ran on. Unsaved edits: nothing recorded."""
    project = Path(project)
    if not is_versioned(project) or not head_exists(project) or unsaved(project):
        return None
    version_id = head(project)
    folder = project / STATE / "verdicts"
    folder.mkdir(parents=True, exist_ok=True)
    snapshot = Path(project) / STATE / "artifacts" / version_id / OUTPUTS
    if snapshot.exists():
        shutil.rmtree(snapshot)
    snapshot.mkdir(parents=True)
    for design in verdict["designs"]:
        for relative in design["artifacts"]:
            source = Path(project) / OUTPUTS / relative
            destination = snapshot / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    (folder / f"{version_id}.json").write_text(json.dumps(verdict, indent=2))
    return version_id


def rebuild_version_artifacts(project, ref):
    """Rebuild a historical version in isolation without changing the project timeline."""
    project = require_versioned(project)
    version = find_version(project, ref)
    with tempfile.TemporaryDirectory(prefix="magic-version-") as tmp:
        folder = Path(tmp) / "project"
        folder.mkdir()
        archive = Path(tmp) / "source.tar"
        with archive.open("wb") as stream:
            result = subprocess.run([*GIT, "archive", "--format=tar", version["id"]],
                                    cwd=project, stdout=stream, stderr=subprocess.PIPE)
        if result.returncode:
            raise VersionError("could not extract the saved version")
        with tarfile.open(archive) as source:
            source.extractall(folder, filter="data")
        from .projects import run_project
        _, verdict = run_project(folder)
        stored = Path(project) / STATE / "verdicts" / f"{version['id']}.json"
        if stored.exists():
            old = json.loads(stored.read_text())
            def evidence(data):
                return [(d["design"], d["pass"], [(g["name"], g["status"]) for g in d["gates"]])
                        for d in data["designs"]]
            if evidence(old) != evidence(verdict):
                raise VersionError("the rebuilt version's checks differ from its saved verdict; no model was saved")
        snapshot = project / STATE / "artifacts" / version["id"] / OUTPUTS
        if snapshot.exists():
            shutil.rmtree(snapshot)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(folder / OUTPUTS, snapshot)
        return version
