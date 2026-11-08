import tempfile
import unittest
from pathlib import Path

from engine.printers import select_printer
from engine.versions import create_project, list_versions, unsaved
from library.printer_profiles import PROFILE


class PrinterSettingsAreVersioned(unittest.TestCase):
    def test_choosing_a_material_saves_a_version_and_leaves_nothing_unsaved(self):
        """Writing printer.json must not leave the project dirty: that blocks rollback and proposals."""
        root = Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as folder:
            project = create_project(Path(folder) / 'p', root / 'fixtures' / 'good_two_parts.py')
            select_printer(str(project), PROFILE['id'], 'PETG')
            self.assertEqual(unsaved(project), [])
            self.assertIn('PETG', list_versions(project)[0]['message'])
            before = len(list_versions(project))
            select_printer(str(project), PROFILE['id'], 'PETG')  # same choice again: no empty version, no error
            self.assertEqual(len(list_versions(project)), before)
            self.assertEqual(unsaved(project), [])


if __name__ == '__main__':
    unittest.main()
