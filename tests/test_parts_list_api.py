#!/usr/bin/env python
"""The parts list through the engine API: derived from the assembly file, never edited by hand.

    .venv/bin/python tests/test_parts_list_api.py

GET /projects/parts-list?project=<folder>[&format=csv] evaluates the project's assembly.py as
it is now. A run also writes outputs/_assembly/parts_list.csv and .json as run artifacts.
"""
import csv
import io
import shutil
import sys
import tempfile
import threading
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from engine.api import make_server  # noqa: E402
from test_engine_api import Client, check, results  # noqa: E402  (same client and tally)

STACK = ROOT / "tests" / "fixtures" / "assembly_stack"
SAMPLES = 7   # the lid's three params at min/default/max; sweep coverage is tested elsewhere
BOARD = '''
    board = asm.component("board", "esp32-devkitc-v4", name="ESP32 board")
    asm.place(board, (board_offset, 0, 0))
'''


def holder_project(tmp):
    """The converted holder assembly as a project: its two designs plus assembly.py."""
    folder = tmp / "holder"
    (folder / "designs").mkdir(parents=True)
    for stem in ("holder_clip", "cable_clip"):
        shutil.copy2(ROOT / "designs" / f"{stem}.py", folder / "designs" / f"{stem}.py")
    shutil.copy2(ROOT / "assembly" / "holder_clip.py", folder / "assembly.py")
    return folder


def parts(api, folder, fmt=None):
    path = f"/projects/parts-list?project={quote(str(folder))}" + (f"&format={fmt}" if fmt else "")
    return api.request("GET", path) if fmt else api.json("GET", path)


def test_holder_parts_list(api, tmp):
    folder = holder_project(tmp)
    status, body = parts(api, folder)
    check("parts list of the holder assembly: 200", status == 200, str(body)[:200])
    got = [(r["category"], r["item"], r["quantity"], r["source"], r["instances"]) for r in body["rows"]]
    check("holder: one printed clip and two M3 x 12 mm screws", got == [
        ("Printed part", "Wall clip", 1, "designs/holder_clip.py", ["clip"]),
        ("Hardware", "M3 socket-head screw, 12 mm", 2, "library/standard_parts.json", ["screw_1", "screw_2"])],
        str(got))
    check("each row says what to print or buy",
          body["rows"][0]["specification"].startswith("FDM print; barrel_dia 38")
          and "ISO 4762" in body["rows"][1]["specification"], str([r["specification"] for r in body["rows"]]))
    check("the list names the assembly file it came from", body["assembly"] == "assembly.py"
          and len(body["source_sha256"] or "") == 64)

    status, ctype, data = parts(api, folder, "csv")
    table = list(csv.reader(io.StringIO(data.decode())))
    check("CSV export: header and one line per row", status == 200 and ctype.startswith("text/csv")
          and table[0] == ["Category", "Item", "Quantity", "Specification", "Source", "Instances"]
          and table[2][:3] == ["Hardware", "M3 socket-head screw, 12 mm", "2"]
          and table[2][5] == "screw_1 screw_2", str(table))
    return folder, body


def test_changing_the_assembly_changes_the_list(api, folder, before):
    source = (folder / "assembly.py").read_text()
    source = source.replace('"screw_length": (12.0,', '"screw_length": (16.0,')
    source = source.replace('PARAMS = {', 'PARAMS = {\n    "board_offset": (80.0, 60.0, 100.0),   # mm, board clear of the clip', 1)
    source = source.replace("def assemble(asm, screw_length):", "def assemble(asm, screw_length, board_offset):")
    (folder / "assembly.py").write_text(source + BOARD)
    status, body = parts(api, folder)
    items = [(r["category"], r["item"], r["quantity"]) for r in body["rows"]]
    check("edited assembly: longer screws and a purchased board, with no edit to any list", status == 200 and items == [
        ("Printed part", "Wall clip", 1), ("Hardware", "M3 socket-head screw, 16 mm", 2),
        ("Purchased component", "ESP32 board", 1)], str(items))
    board = body["rows"][-1] if body.get("rows") else {}
    check("purchased component carries its source link and dimension provenance",
          board.get("source", "").startswith("https://dl.espressif.com/")
          and "datasheet-verified" in board.get("specification", ""), str(board))
    check("the list's source hash follows the file", body.get("source_sha256") != before["source_sha256"])


def test_refusals(api, tmp):
    folder = holder_project(tmp / "refuse")
    (folder / "assembly.py").unlink()
    status, body = parts(api, folder)
    check("no assembly file: 400", status == 400 and "no assembly.py" in body["error"], body.get("error"))
    (folder / "assembly.py").write_text("PARAMS = {}\n\ndef assemble(asm):\n    asm.printed('x', 'missing')\n")
    status, body = parts(api, folder)
    check("an assembly that does not build: 400 with the reason", status == 400
          and "no design designs/missing.py" in body["error"], body.get("error"))


def test_run_writes_the_parts_list(api, tmp):
    folder = tmp / "stack"
    shutil.copytree(STACK, folder, ignore=shutil.ignore_patterns("__pycache__", "outputs"))
    status, queued = api.json("POST", "/runs", {"project": str(folder), "samples": SAMPLES})
    api.events(queued["id"])
    _, done = api.json("GET", f"/runs/{queued['id']}")
    artifacts = done["verdict"]["assembly"]["artifacts"]
    check("a run keeps the parts list as CSV and JSON artifacts",
          {"_assembly/parts_list.csv", "_assembly/parts_list.json"} <= set(artifacts), str(artifacts))
    status, ctype, data = api.request("GET", f"/runs/{queued['id']}/artifacts/_assembly/parts_list.csv")
    _, _, live = parts(api, folder, "csv")
    check("the run's CSV is the same list the API derives", status == 200 and ctype.startswith("text/csv")
          and data == live, data.decode()[:200])
    items = [r[1] for r in csv.reader(io.StringIO(data.decode()))][1:]
    check("stack: base, lid, insert and screw, in declaration order within each category",
          items == ["Base plate", "Lid", "M3 heat-set insert", "M3 socket-head screw, 6 mm"], str(items))


def main():
    server = make_server(port=0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    api = Client(server.server_address[1])
    try:
        with tempfile.TemporaryDirectory(prefix="parts_list_api_") as tmp:
            tmp = Path(tmp)
            print("--- test_holder_parts_list")
            folder, body = test_holder_parts_list(api, tmp)
            print("--- test_changing_the_assembly_changes_the_list")
            test_changing_the_assembly_changes_the_list(api, folder, body)
            print("--- test_refusals")
            test_refusals(api, tmp)
            print("--- test_run_writes_the_parts_list")
            test_run_writes_the_parts_list(api, tmp)
    finally:
        server.shutdown()
        server.server_close()
    print(f"\n{sum(results)}/{len(results)} passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
