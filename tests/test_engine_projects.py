#!/usr/bin/env python
"""Project folders, versions and rollback, through the engine API's public HTTP seam.

    .venv/bin/python tests/test_engine_projects.py

Projects are created through the API itself: from the wall bracket (the ticket's example),
and from the two-part positive control, whose fast gates carry the save / rollback timeline.
"""
import json
import sys
import tempfile
import threading
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.api import make_server  # noqa: E402
from test_engine_api import Client, check, results  # noqa: E402  (same client and tally)

TWO_PARTS = ROOT / "tests" / "fixtures" / "good_two_parts.py"


def versions(api, project):
    status, body = api.json("GET", f"/projects/versions?project={project}")
    assert status == 200, body
    return body["versions"]


def test_create_from_wall_bracket(api, tmp):
    folder = tmp / "wall_bracket"
    status, body = api.json("POST", "/projects", {"folder": str(folder), "from_design": "wall_bracket"})
    check("create from the wall bracket: 201", status == 201, str(status))
    same = (folder / "designs" / "wall_bracket.py").read_bytes() == (ROOT / "designs" / "wall_bracket.py").read_bytes() \
        and (folder / "briefs" / "wall_bracket.yaml").read_bytes() == (ROOT / "briefs" / "wall_bracket.yaml").read_bytes()
    check("project holds its own design and brief card", same)
    timeline = body["versions"]
    check("it starts with one version", len(timeline) == 1 and timeline[0]["number"] == 1
          and timeline[0]["current"] and timeline[0]["message"] == "Created from wall_bracket", str(timeline))
    check("timeline never mentions git", "git" not in json.dumps(timeline).lower())

    status, done = api.json("POST", "/runs", {"project": str(folder), "wait": True})
    check("the copied project passes every gate on its own", status == 200 and done["verdict"]["pass"],
          f"{done['verdict']['seconds']} s")
    check("version 1 now carries that verdict", versions(api, folder)[0]["verdict"]["pass"] is True)
    claims = versions(api, folder)[0]["verdict"]["designs"][0]["claims"]
    check("saved verdict identifies computed checks and untested physical fit",
          any(c["tier"] == "computed" for c in claims) and
          any(c["tier"] == "needs physical test" for c in claims) and
          not any(c["tier"] == "physically tested" for c in claims))
    check("individual measured dimensions and sweep samples carry evidence",
          any(c["claim"].startswith("Dimension:") and c["tier"] == "computed" for c in claims)
          and any(c["claim"].startswith("Sweep sample:") and c["tier"] == "computed" for c in claims))
    _, _, raw = api.request("GET", f"/runs/{done['id']}/artifacts/wall_bracket/report.json")
    check("report carries the same claim evidence", json.loads(raw)["claims"] == claims)

    status, body = api.json("POST", "/projects", {"folder": str(folder), "from_design": "wall_bracket"})
    check("creating over a non-empty folder is refused", status == 400, body.get("error", ""))
    status, body = api.json("POST", "/projects", {"folder": str(tmp / "x"), "from_design": "no_such_part"})
    check("an unknown design is refused", status == 400 and "no such design" in body["error"], body["error"])


def test_versions_and_rollback(api, tmp):
    folder = tmp / "two_parts"
    design = folder / "designs" / "good_two_parts.py"
    status, _ = api.json("POST", "/projects", {"folder": str(folder), "from_design": str(TWO_PARTS)})
    check("create from a design path: 201", status == 201, str(status))
    v1_source = design.read_text()
    _, run = api.json("POST", "/runs", {"project": str(folder), "wait": True})
    check("version 1 passes", run["verdict"]["pass"] and run["verdict"]["version"] == versions(api, folder)[0]["id"])

    status, body = api.json("POST", "/projects/versions", {"project": str(folder), "message": "Nothing"})
    check("saving with no change is refused", status == 409, body.get("error", ""))

    design.write_text(v1_source.replace('"size": (20.0,', '"size": (24.0,'))
    (folder / "notes.txt").write_text("bigger cubes for the shelf\n")
    status, body = api.json("POST", "/projects/versions", {"project": str(folder), "message": "Bigger cubes"})
    v2 = body.get("version", {})
    stamp_ok = datetime.fromisoformat(v2.get("timestamp", "")).tzinfo is not None if v2 else False
    check("saving a change makes version 2 with message and timestamp",
          status == 201 and v2["number"] == 2 and v2["message"] == "Bigger cubes" and stamp_ok, str(v2))

    design.write_text(v1_source.replace("size, size, size,", "size, size, 37.5,"))
    api.json("POST", "/projects/versions", {"project": str(folder), "message": "Hard-code the height"})
    _, run = api.json("POST", "/runs", {"project": str(folder), "wait": True})
    check("version 3 fails the gates", not run["verdict"]["pass"])

    timeline = versions(api, folder)
    check("timeline lists 3 versions newest first with messages",
          [v["number"] for v in timeline] == [3, 2, 1]
          and [v["message"] for v in timeline] == ["Hard-code the height", "Bigger cubes",
                                                   f"Created from {TWO_PARTS.stem}"], str(timeline))
    check("each version shows the verdict it earned, or none",
          [None if v["verdict"] is None else v["verdict"]["pass"] for v in timeline] == [False, None, True])

    design.write_text(design.read_text() + "# an unsaved edit\n")
    status, body = api.json("POST", "/projects/rollback", {"project": str(folder), "version": 1})
    check("rollback over unsaved edits is refused", status == 409 and "unsaved" in body["error"], body["error"])
    design.write_text(design.read_text().replace("# an unsaved edit\n", ""))

    _, queued = api.json("POST", "/runs", {"project": str(folder)})
    status, body = api.json("POST", "/projects/rollback", {"project": str(folder), "version": 1})
    check("rollback during a run of the project is refused", status == 409, body.get("error", ""))
    api.events(queued["id"])  # let it finish

    status, body = api.json("POST", "/projects/rollback", {"project": str(folder), "version": 1, "wait": True})
    check("rollback to version 1 re-runs the gates", status == 200 and body["run"]["status"] == "done"
          and body["run"]["verdict"]["pass"], str(status))
    check("rollback restores version 1's files exactly",
          design.read_text() == v1_source and not (folder / "notes.txt").exists())
    _, _, raw = api.request("GET", f"/runs/{body['run']['id']}/artifacts/good_two_parts/report.json")
    check("the re-run built version 1's parameters", json.loads(raw)["params"]["size"] == 20.0)
    timeline = versions(api, folder)
    check("rollback is a new version on top; nothing is lost",
          [v["number"] for v in timeline] == [4, 3, 2, 1]
          and timeline[0]["message"].startswith("Rolled back to version 1")
          and timeline[0]["current"] and timeline[0]["verdict"]["pass"], timeline[0]["message"])
    check("the response reports the new version's verdict", body["version"]["verdict"]["pass"] is True)

    status, body = api.json("POST", "/projects/rollback", {"project": str(folder), "version": "99"})
    check("an unknown version is refused", status == 400 and "no such version" in body["error"], body["error"])
    status, body = api.json("GET", f"/projects/versions?project={tmp / 'nowhere'}")
    check("versions of a non-project are refused", status == 400, body.get("error", ""))


def test_rollback_with_non_ascii_paths(api, tmp):
    """Git quotes non-ASCII paths by default; the version store must still see real file names."""
    folder = tmp / "unicode_paths"
    design = folder / "designs" / "good_two_parts.py"
    status, _ = api.json("POST", "/projects", {"folder": str(folder), "from_design": str(TWO_PARTS)})
    check("unicode: create 201", status == 201, str(status))
    (folder / "briefs").mkdir(exist_ok=True)
    (folder / "briefs" / "café.yaml").write_text("note: unicode name\n")
    status, _ = api.json("POST", "/projects/versions", {"project": str(folder), "message": "Brief"})
    check("unicode: save with a non-ASCII file", status == 201, str(status))
    design.write_text(design.read_text().replace('"size": (20.0,', '"size": (24.0,'))
    api.json("POST", "/projects/versions", {"project": str(folder), "message": "Bigger"})
    (folder / "naïve.txt").write_text("unsaved\n")
    status, body = api.json("POST", "/projects/rollback", {"project": str(folder), "version": "2"})
    check("unicode: unsaved non-ASCII file is named plainly", status == 409 and "naïve.txt" in body.get("error", ""), body.get("error", ""))
    (folder / "naïve.txt").unlink()
    status, body = api.json("POST", "/projects/rollback", {"project": str(folder), "version": "1", "wait": True})
    check("unicode: rollback past a non-ASCII file succeeds", status in (200, 201, 202), f"{status} {body.get('error', '')}")
    check("unicode: the non-ASCII file is gone in version 1", not (folder / "briefs" / "café.yaml").exists())
    status, body = api.json("POST", "/projects/rollback", {"project": str(folder), "version": "2", "wait": True})
    check("unicode: rollback restores the non-ASCII file", status in (200, 201, 202) and (folder / "briefs" / "café.yaml").is_file(), f"{status} {body.get('error', '')}")


def main():
    server = make_server(port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    api = Client(server.server_address[1])
    try:
        with tempfile.TemporaryDirectory(prefix="engine_projects_") as tmp:
            for test in (test_versions_and_rollback, test_create_from_wall_bracket, test_rollback_with_non_ascii_paths):
                print(f"--- {test.__name__}")
                test(api, Path(tmp))
    finally:
        server.shutdown()
        server.server_close()
    print(f"\n{sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
