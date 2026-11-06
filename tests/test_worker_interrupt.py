"""An interrupted CAD worker must terminate promptly and report interruption."""
import tempfile
import threading
import time
import unittest
from pathlib import Path

from harness.execute import run_worker


class WorkerInterruptTest(unittest.TestCase):
    def test_uncancelled_worker_returns_geometry(self):
        with tempfile.TemporaryDirectory() as folder:
            result = run_worker(Path(__file__).parent / 'fixtures/good_two_parts.py', folder,
                                timeout=60, cancel_event=threading.Event())
            self.assertTrue(result['ok'], result.get('traceback'))
            self.assertEqual(len(result['parts']), 2)

    def test_interrupt_stops_a_hanging_worker(self):
        stop = threading.Event()
        with tempfile.TemporaryDirectory() as folder:
            result = []
            worker = threading.Thread(target=lambda: result.append(run_worker(
                Path(__file__).parent / 'fixtures/hang.py', folder, timeout=60, cancel_event=stop)))
            worker.start()
            time.sleep(0.5)
            stop.set()
            worker.join(5)
            self.assertFalse(worker.is_alive())
            self.assertTrue(result[0]['interrupted'])
            self.assertFalse(result[0]['ok'])


if __name__ == '__main__':
    unittest.main()
