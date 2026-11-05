"""A saved project's CAD library travels with, and is restored with, its design."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from engine.versions import create_project, restore_version, save_version


class ProjectLibraryTest(unittest.TestCase):
    def test_library_is_local_and_rollback_restores_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = create_project(Path(tmp) / "project", "wall_bracket")
            library = project / "library" / "standard_parts.json"
            original = library.read_text()
            self.assertEqual(original, (ROOT / "library" / "standard_parts.json").read_text())
            # Ask a fresh worker process which library the copied design imports.
            script = ("import sys; from harness.worker import load_design; "
                      "load_design(sys.argv[1]); import library; print(library.__file__)")
            imported = subprocess.check_output([sys.executable, "-c", script,
                                                str(project / "designs" / "wall_bracket.py")],
                                               cwd=ROOT, text=True).strip()
            self.assertEqual(Path(imported).resolve(), (project / "library" / "__init__.py").resolve())
            library.write_text(original + "\n")
            save_version(project, "Changed library")
            restore_version(project, 1)
            self.assertEqual(library.read_text(), original)


if __name__ == "__main__":
    unittest.main()
