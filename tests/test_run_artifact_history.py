"""Run-specific artifact URLs keep their original contents across later runs."""
import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

# The API's queue and HTTP behavior can be tested without loading the CAD runtime.
pipeline = types.ModuleType("harness.pipeline")
pipeline.run = lambda *args, **kwargs: None
with patch.dict(sys.modules, {"harness.pipeline": pipeline}):
    api = importlib.import_module("engine.api")


class ArtifactHistoryTest(unittest.TestCase):
    def test_external_symlink_is_not_snapshotted(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder) / "project"
            (project / "designs").mkdir(parents=True)
            (project / "designs" / "part.py").touch()
            outside = Path(folder) / "secret.json"
            outside.write_text("secret")
            engine = api.Engine()

            def run_project(path, *args):
                output = path / "outputs"
                output.mkdir()
                (output / "verdict.json").write_text("{}")
                (output / "leak.json").symlink_to(outside)
                return 0, {"pass": True, "designs": [{"artifacts": ["leak.json"]}]}

            with patch.object(api, "run_project", side_effect=run_project):
                run = engine.submit(project)
                api.Handler.finished(run, True)
            self.assertEqual(run.status, "error")
            self.assertIsNone(run.artifact_project)
            engine.artifacts.cleanup()

    def test_earlier_run_keeps_its_artifact(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Path(folder)
            (project / "designs").mkdir()
            (project / "designs" / "part.py").touch()
            engine = api.Engine()
            server = api.make_server(port=0, engine=engine)
            import threading
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            counter = iter((b"first", b"second"))

            def run_project(path, *args):
                output = path / "outputs"
                output.mkdir(exist_ok=True)
                (output / "report.json").write_bytes(next(counter))
                (output / "verdict.json").write_text("{}")
                (output / "old.json").write_text("stale")
                return 0, {"pass": True, "designs": [{"artifacts": ["report.json"]}]}

            try:
                with patch.object(api, "run_project", side_effect=run_project):
                    first = engine.submit(project)
                    api.Handler.finished(first, True)
                    second = engine.submit(project)
                    api.Handler.finished(second, True)
                base = f"http://127.0.0.1:{server.server_address[1]}/runs"
                with urlopen(f"{base}/{first.id}/artifacts/report.json") as response:
                    self.assertEqual(response.read(), b"first")
                with urlopen(f"{base}/{second.id}/artifacts/report.json") as response:
                    self.assertEqual(response.read(), b"second")
                from urllib.error import HTTPError
                with self.assertRaises(HTTPError) as missing:
                    urlopen(f"{base}/{second.id}/artifacts/old.json")
                self.assertEqual(missing.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
                engine.artifacts.cleanup()


if __name__ == "__main__":
    unittest.main()
