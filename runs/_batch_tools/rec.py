"""rec.py stem status dims sweep time 'note' ['summary' parts]  -> appends progress row, updates EVALS.md status (adds row if new)."""
import re, sys
stem, status, dims, sweep, secs, note = sys.argv[1:7]
summary = sys.argv[7] if len(sys.argv) > 7 else None
parts = sys.argv[8] if len(sys.argv) > 8 else None
p = open("batch_ten_progress.md").read()
n = len(re.findall(r"^\| \d+ \|", p, re.M)) + 1
row = f"| {n} | {stem} | {status} | {dims} | {sweep} | {secs} | {note} |\n"
head = "|---|---|---|---|---|---|---|\n"
i = p.index("\n## Library candidates")
p = p[:i].rstrip("\n") + "\n" + row + p[i:]
open("batch_ten_progress.md", "w").write(p)
e = open("evals/EVALS.md").read()
cell = f"`designs/{stem}.py`: {status} (batch ten, unreviewed)"
pat = re.compile(rf"^\| `briefs/{stem}\.yaml` \|(.*)\|(.*)\|(.*)\|$", re.M)
m = pat.search(e)
if m:
    e = pat.sub(lambda m: f"| `briefs/{stem}.yaml` |{m.group(1)}|{m.group(2)}| {cell} |", e)
else:
    lines = e.split("\n")
    idx = max(k for k, l in enumerate(lines) if l.startswith("| `briefs/"))
    lines.insert(idx + 1, f"| `briefs/{stem}.yaml` | {summary} | {parts} | {cell} |")
    e = "\n".join(lines)
open("evals/EVALS.md", "w").write(e)
