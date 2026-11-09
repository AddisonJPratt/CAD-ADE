"""magic-cad MCP server pointed at a project folder (MAGIC_CAD_PROJECT), as the designer (#61) runs it.

The designer works in a proposal draft outside the repo, so run_check, measure_file and min_gap
must resolve paths against that draft and refuse anything outside it, the repo included.
"""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

from engine.versions import create_project_from_brief
from tests.test_designer import brief, good

ROOT = Path(__file__).resolve().parents[1]


def load_server(project):
    os.environ["MAGIC_CAD_PROJECT"] = str(project)
    try:
        spec = importlib.util.spec_from_file_location("magic_cad_server_project", ROOT / "mcp/magic_cad_server.py")
        server = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(server)
        return server
    finally:
        del os.environ["MAGIC_CAD_PROJECT"]


class McpProjectRootTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        card = Path(self.tmp.name) / 'block.yaml'
        card.write_text(brief())
        self.project = create_project_from_brief(Path(self.tmp.name) / 'project', card)
        (self.project / 'designs').mkdir()
        (self.project / 'designs/block.py').write_text(good())
        self.server = load_server(self.project)

    def test_design_tools_work_in_the_project_folder(self):
        designs = self.server.list_designs()
        self.assertEqual([(d['name'], d['brief_path']) for d in designs['designs']], [('block', 'briefs/block.yaml')])
        result = self.server.run_check('block', quick=True)
        result = getattr(result, 'structured_content', result)
        self.assertTrue(result['pass'], result)
        self.assertTrue(result['quick'])
        self.assertEqual(result['brief'], 'briefs/block.yaml')
        report = Path(result['report_path']).resolve()
        self.assertEqual(report.parent, (self.project / 'outputs/block-quick').resolve())   # never versioned

    def test_paths_outside_the_project_are_refused(self):
        outside = self.server.measure_file(str(ROOT / 'ui/tests/fixtures/models/wall_bracket/bracket.stl'))
        self.assertEqual(outside['error']['code'], 'path_outside_project')
        repo_design = self.server.run_check('wall_bracket')
        repo_design = getattr(repo_design, 'structured_content', repo_design)
        self.assertEqual(repo_design['error']['code'], 'design_not_found')


if __name__ == '__main__':
    unittest.main()
