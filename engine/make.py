"""Make mode: the guided Ask -> Make -> Prove -> Shelf flow (#14), ported from the first-proof app.

The first-proof app (proof/server.py) kept each make in its own folder and ran magic.py on it.
Here every make is an ordinary engine project, so the Shelf, Studio and Mission Control all see
the same folders, versions and verdicts:

    Ask    form_spec()            the templates, their measured ranges and the materials
    Make   create(ask)            <projects home>/<object> holder as version 1 (the template)
           size(project, ask)     the template sized to the measurements, as the next version;
                                  the caller queues the gates on it
    Prove  proof(project, ver)    the version's make record, verdict, files and print outcome
           record_print(...)      a physical fit result; it may adjust the next clearance
    Shelf  shelf()                every project with its version history and print outcomes

A make record (make.json) is versioned with the project's source, so every version knows what it
was asked to fit. Print outcomes are calibration data shared across projects: one immutable event
per project version in <projects home>/.calibration/events/, from which the clearance profile, an outcomes
log and prints/PRINT_LOG.md are rebuilt (reconcile()).

Only a version whose six gates all PASS with exactly one exported STL is "proven"; anything else,
including a NOT RUN gate, never offers a print file or takes a print result.
"""
import hashlib
import json
import math
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from library.printer_profiles import PROFILE

from .parameters import _read, parameter_edit
from .printers import SETTINGS
from .projects import ProjectError
from .versions import ROOT, STATE, Conflict, find_version, git, list_versions, require_versioned, save_version, unsaved
from .workspace import NAME, home, list_projects, new_project

MAKE_FILE = "make.json"
TEMPLATES = {"round": "holder_clip", "rectangular": "holder_cradle"}
# Ask field -> template parameter it sizes (None: recorded for reference only).
FIELDS = {"round": [("diameter", "barrel_dia"), ("length", None)],
          "rectangular": [("width", "obj_w"), ("depth", "obj_d"), ("height", "obj_h")]}
LENGTH_RANGE = (1.0, 2000.0)
GATES = ["1 Execute", "2 Geometry", "3 Printability", "4 Renders", "Sweep", "5 Exports"]
RESULTS = {"perfect": "Perfect", "too_tight": "Too tight", "too_loose": "Too loose", "broke": "It broke"}
STEP_MM = {"too_tight": 0.2, "too_loose": -0.2}
LOCK = threading.RLock()


def calibration_dir():
    return Path(os.environ.get("MAGIC_CALIBRATION") or home() / ".calibration").expanduser().resolve()


def print_log():
    return Path(os.environ.get("MAGIC_PRINT_LOG") or ROOT / "prints" / "PRINT_LOG.md").expanduser().resolve()


def _read_json(path, default):
    try:
        return json.loads(Path(path).read_text())
    except (FileNotFoundError, ValueError):
        return default


def _write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n")
    os.replace(temp, path)


def template(shape):
    """(template name, {param: (default, min, max)}) read from the repo design, never executed."""
    if shape not in TEMPLATES:
        raise ProjectError("Choose a round or rectangular object.")
    name = TEMPLATES[shape]
    _, _, _, declared = _read(ROOT, f"{name}.py")
    return name, declared


def adjustment(joint):
    with LOCK:
        return float(_read_json(calibration_dir() / "profile.json", {}).get("adjustments_mm", {}).get(joint, 0))


def form_spec():
    """What the Ask step offers: each shape's fields with the template's tested ranges."""
    shapes = {}
    for shape, name in TEMPLATES.items():
        _, declared = template(shape)
        fields = []
        for field, param in FIELDS[shape]:
            low, high = (declared[param][1], declared[param][2]) if param else LENGTH_RANGE
            default = declared[param][0] if param else 250.0
            fields.append({"name": field, "min": low, "max": high, "default": default, "sizes": bool(param)})
        clearance = round(declared["clearance"][0] + adjustment(name), 5)
        shapes[shape] = {"template": name, "fields": fields, "clearance_mm": clearance,
                         "calibrated": clearance != declared["clearance"][0]}
    return {"shapes": shapes, "materials": list(PROFILE["materials"]), "mounts": ["screws"],
            "printer": PROFILE["name"]}


def _number(form, name, low, high):
    try:
        value = float(form[name])
    except (KeyError, ValueError, TypeError):
        raise ProjectError(f"Enter a valid {name.replace('_', ' ')} in millimetres.")
    if not math.isfinite(value) or not low <= value <= high:
        raise ProjectError(f"{name.replace('_', ' ').capitalize()} must be between {low:g} and {high:g} mm.")
    return value


def validate(form):
    """The Ask form -> a clean make request. Every error message is shown to the maker as is."""
    if not isinstance(form, dict):
        raise ProjectError("Send the Ask form as an object.")
    shape = form.get("shape", "")
    name, declared = template(shape)
    obj = form.get("object", "")
    obj = obj.strip() if isinstance(obj, str) else ""
    if not obj or len(obj) > 100 or any(ord(c) < 32 for c in obj):
        raise ProjectError("Enter an object name, up to 100 characters.")
    material = form.get("material", "PLA")
    if material not in PROFILE["materials"] or form.get("mount", "screws") != "screws":
        raise ProjectError("Choose a supported material and screw mounting.")
    readings = {}
    for field, param in FIELDS[shape]:
        low, high = (declared[param][1], declared[param][2]) if param else LENGTH_RANGE
        readings[field] = _number(form, field, low, high)
    return {"object": obj, "shape": shape, "template": name, "joint_type": name,
            "material": material, "mount": "screws", "readings": readings}


def project_name(obj):
    """A free project folder name for the object: '<object> holder', then '... 2', '... 3'."""
    words = re.sub(r"[^A-Za-z0-9 ._-]+", " ", obj)
    base = " ".join(words.split()).strip(" ._-")[:60].rstrip(" ._-") or "Make"
    base = f"{base} holder"
    if not NAME.fullmatch(base):
        base = "Holder"
    for n in range(1, 1000):
        candidate = base if n == 1 else f"{base} {n}"
        if not (home() / candidate).exists():
            return candidate
    raise ProjectError("Too many projects share this name; rename one on the Shelf first.")


def create(form):
    """Ask -> a new project holding the unsized template as version 1. Returns (folder, ask)."""
    ask = validate(form)
    folder = new_project(project_name(ask["object"]), ask["template"])
    return folder, ask


def record(project, version=None):
    """The make record of the current files, or of a saved version; None for a non-Make project."""
    project = Path(project)
    if version is None:
        return _read_json(project / MAKE_FILE, None)
    text = git(project, "show", f"{version}:{MAKE_FILE}", check=False)
    try:
        return json.loads(text) if text.strip() else None
    except ValueError:
        return None


def size(project, ask=None):
    """Write the template sized to the ask, with the current calibrated clearance, as a new
    version. ask=None remakes the project's own record (an adjusted fit). Caller holds the
    engine's change lock, so no run sees these files change."""
    project = require_versioned(project)
    if ask is None:
        ask = record(project)
        if not ask:
            raise ProjectError("This project was not made in Make mode.")
        ask = validate({**ask, **ask["readings"]})
    name, declared = template(ask["shape"])
    design = project / "designs" / f"{name}.py"
    if not design.is_file():
        raise ProjectError(f"This project no longer holds {name}.py.")
    clearance = round(declared["clearance"][0] + adjustment(ask["joint_type"]), 5)
    overrides = {"clearance": clearance}
    for field, param in FIELDS[ask["shape"]]:
        if param:
            overrides[param] = ask["readings"][field]
    for key, value in overrides.items():
        if not math.isfinite(value) or not declared[key][1] <= value <= declared[key][2]:
            raise ProjectError("The saved fit adjustment is outside the tested range. "
                               "Reset the calibration before making another holder.")
    previous = record(project)
    if previous == {**ask, "clearance_used_mm": clearance}:
        raise Conflict(f"This holder already uses the current clearance ({clearance:g} mm).")
    if unsaved(project):
        raise Conflict("This project has unsaved changes; save or discard them in Studio first.")
    _, _, _, current = _read(project, design.name)
    for key, value in overrides.items():
        if current[key][0] != value:
            design.write_text(parameter_edit(project, design.name, key, value)["source"])
    sized = {k: overrides.get(k, v[0]) for k, v in current.items()}
    brief_path = project / "briefs" / f"{name}.yaml"
    brief = yaml.safe_load(brief_path.read_text()) if brief_path.is_file() else {}
    brief["function"] = f"Wall holder for {ask['object']}"
    for key, value in sized.items():
        brief.setdefault("params", {}).setdefault(key, {"unit": "mm", "intent": key.replace("_", " ")})
        brief["params"][key].update({"value": value, "min": declared[key][1], "max": declared[key][2]})
    if "clip_height" in sized and "clip_height" in brief.get("hard_dimensions", {}):
        brief["hard_dimensions"]["clip_height"] = sized["clip_height"]
    brief.setdefault("assumptions", [])
    note = "Fit, retention and load are not validated by the harness; clearance is not physically calibrated."
    if note not in brief["assumptions"]:
        brief["assumptions"].append(note)
    brief_path.parent.mkdir(exist_ok=True)
    brief_path.write_text(yaml.safe_dump(brief, sort_keys=False))
    ask = {**ask, "clearance_used_mm": clearance}
    _write_json(project / MAKE_FILE, ask)
    (project / SETTINGS).write_text(json.dumps({"printer": PROFILE["id"], "material": ask["material"]}, indent=2) + "\n")
    if previous and previous.get("readings") == ask["readings"]:
        message = f"Adjusted fit: clearance {clearance:g} mm"
    else:
        message = f"Sized for {ask['object']}: {describe(ask)}"
    return save_version(project, message)


def describe(ask):
    r = ask["readings"]
    if ask["shape"] == "round":
        return f"{r['diameter']:g} mm diameter"
    return f"{r['width']:g} × {r['depth']:g} × {r['height']:g} mm"


def _full_verdict(project, version_id):
    return _read_json(Path(project) / STATE / "verdicts" / f"{version_id}.json", None)


def judge(verdict):
    """(proven, stl, render, failure) from a stored project verdict. Proven means one design,
    all six gates PASS, and exactly one STL export: the first-proof app's release rule."""
    if verdict is None:
        return False, None, None, None
    designs = verdict.get("designs", [])
    entry = designs[0] if len(designs) == 1 else None
    gates = {g.get("name"): g.get("status") for g in (entry or {}).get("gates", [])}
    stls = [a for a in (entry or {}).get("artifacts", []) if a.endswith(".stl") and a.count("/") == 1]
    render = next((a for a in (entry or {}).get("artifacts", []) if a.endswith("/renders/iso.png")), None)
    proven = bool(entry) and verdict.get("pass") is True and entry.get("pass") is True \
        and all(gates.get(g) == "PASS" for g in GATES) and len(stls) == 1
    failure = None
    if not proven:
        failed = next((g for g in (entry or {}).get("gates", []) if g.get("status") in ("FAIL", "ERROR")), None)
        missing = next((g for g in GATES if gates.get(g) != "PASS"), None)
        failure = (f"{failed['name']}: {failed.get('detail', '')}".strip() if failed else
                   f"The {missing} check did not run, so this holder is not released." if missing else
                   "The verification run did not complete successfully.")
    return proven, (stls[0] if proven else None), render, failure


def event_key(project, version_id):
    """One print event per (project, version): identical makes can share a commit id."""
    return hashlib.sha1(f"{Path(project).resolve()}\0{version_id}".encode()).hexdigest()


def outcome(project, version_id):
    with LOCK:
        return _read_json(calibration_dir() / "events" / f"{event_key(project, version_id)}.json", None)


def proof(project, ref):
    """Everything the Prove step shows for one version."""
    project = require_versioned(project)
    version = find_version(project, ref)
    ask = record(project, version["id"])
    proven, stl, render, failure = judge(_full_verdict(project, version["id"]))
    result = outcome(project, version["id"])
    next_clearance = None
    if ask:
        name, declared = template(ask["shape"])
        next_clearance = round(declared["clearance"][0] + adjustment(ask["joint_type"]), 5)
    return {"project": str(project), "version": version, "make": ask, "checked": version["verdict"] is not None,
            "proven": proven, "stl": stl, "render": render, "failure": failure,
            "gates": [{"name": g["name"], "status": g["status"], "detail": g.get("detail", "")}
                      for d in (_full_verdict(project, version["id"]) or {}).get("designs", []) for g in d["gates"]],
            "outcome": result, "next_clearance_mm": next_clearance,
            "can_remake": bool(ask and next_clearance is not None and ask.get("clearance_used_mm") != next_clearance
                               and version["current"])}


def reconcile():
    """Rebuild the profile, outcomes log and print log from the immutable events. Idempotent."""
    with LOCK:
        base = calibration_dir()
        events = [_read_json(p, None) for p in (base / "events").glob("*.json")
                  if re.fullmatch(r"[0-9a-f]{40}\.json", p.name)]
        events = sorted((e for e in events if e), key=lambda e: (e["ts"], e["key"]))
        profile = {"adjustments_mm": {}}
        for event in events:
            joint = event["joint_type"]
            profile["adjustments_mm"][joint] = round(profile["adjustments_mm"].get(joint, 0) + event["adjustment_mm"], 5)
        _write_json(base / "profile.json", profile)
        target = base / "outcomes.jsonl"
        temp = target.with_name(target.name + "." + uuid.uuid4().hex + ".tmp")
        temp.write_text("".join(json.dumps(e, ensure_ascii=True) + "\n" for e in events))
        os.replace(temp, target)
        log = print_log()
        log.parent.mkdir(parents=True, exist_ok=True)
        existing = log.read_text() if log.exists() else ""
        for e in events:
            marker = f"<!-- magic-make:{e['key']} -->"
            if marker in existing:
                continue
            verdict = (f"adjust clearance by {e['adjustment_mm']} mm" if e["adjustment_mm"]
                       else "recorded; no clearance adjustment")
            entry = (f"\n{marker}\n## {e['ts'][:10]} — {e['template']} — {e['printer']}, {e['material']}, nozzle {PROFILE['nozzle_mm']} mm\n"
                     f"- Modelled vs measured: not recorded\n"
                     f"- Fit results: {e['joint_type']}: {RESULTS[e['result']]}, per-side clearance {e['clearance_used_mm']} mm\n"
                     f"- Failures: {'reported broken; review needed' if e['result'] == 'broke' else 'not recorded'}\n"
                     f"- Verdict: {verdict}\n")
            with log.open("a") as stream:
                stream.write(entry)
            existing += entry
        return profile


def record_print(project, ref, result):
    """A physical print's fit, once per proven version. Too tight or too loose moves the next
    clearance for that template by 0.2 mm, but only while the profile is the one the print used
    and the new value stays in the tested range; otherwise it is kept for review, unapplied."""
    if result not in RESULTS:
        raise ProjectError("Choose a fit result.")
    project = require_versioned(project)
    version = find_version(project, ref)
    with LOCK:
        reconcile()
        ask = record(project, version["id"])
        proven, *_ = judge(_full_verdict(project, version["id"]))
        if not ask or not proven:
            raise ProjectError("A completed, checked design is needed before recording a print.")
        key = event_key(project, version["id"])
        path = calibration_dir() / "events" / f"{key}.json"
        if path.exists():
            raise Conflict("A fit result has already been recorded for this print.")
        requested = STEP_MM.get(result, 0)
        _, declared = template(ask["shape"])
        current = adjustment(ask["joint_type"])
        next_clearance = round(declared["clearance"][0] + current + requested, 5)
        in_range = declared["clearance"][1] <= next_clearance <= declared["clearance"][2]
        fresh = abs(declared["clearance"][0] + current - ask["clearance_used_mm"]) < 1e-6
        allowed = in_range and (fresh or not requested)
        reason = None if allowed else (
            "The saved calibration has changed since this print; review this result before adjusting it."
            if not fresh else "Requested adjustment exceeds the tested clearance range.")
        event = {"ts": datetime.now(timezone.utc).isoformat(), "project": str(project),
                 "key": key, "version": version["id"], "version_number": version["number"], "object": ask["object"],
                 "template": ask["template"], "joint_type": ask["joint_type"], "material": ask["material"],
                 "printer": PROFILE["name"], "clearance_used_mm": ask["clearance_used_mm"], "result": result,
                 "adjustment_mm": requested if allowed else 0,
                 "review_needed": result == "broke" or not allowed, "adjustment_reason": reason}
        # One atomic event is the record; everything else is rebuilt from the events.
        _write_json(path, event)
        reconcile()
    return proof(project, version["id"])


def shelf():
    """Every project, newest first, with its make record, version history and print outcomes."""
    items = []
    for entry in list_projects()["projects"]:
        folder = Path(entry["path"])
        try:
            versions = list_versions(folder)
        except ProjectError:
            versions = []
        for version in versions:
            version["outcome"] = outcome(folder, version["id"])
        items.append({**entry, "make": record(folder), "versions": versions})
    return {"home": str(home()), "projects": items}
