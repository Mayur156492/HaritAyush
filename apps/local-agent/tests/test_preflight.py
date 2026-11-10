from __future__ import annotations

import io
import platform
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from haritayush_agent.preflight import _check_job_object, _check_kill_switch, _report


class PreflightTests(unittest.TestCase):
    def test_failure_always_prints_actionable_fix_hint(self):
        output = io.StringIO()
        with redirect_stdout(output):
            passed = _report("backend", lambda: (_ for _ in ()).throw(RuntimeError("offline")),
                             "Start the backend and set its URL.")
        self.assertFalse(passed)
        self.assertIn("FAIL - backend: offline", output.getvalue())
        self.assertIn("Fix: Start the backend and set its URL.", output.getvalue())

    def test_kill_switch_check_confirms_directory_is_writable_without_creating_kill_file(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "agent-state"
            message = _check_kill_switch(directory)
            self.assertIn(str(directory / "KILL"), message)
            self.assertTrue(directory.is_dir())
            self.assertEqual(list(directory.iterdir()), [])

    @unittest.skipUnless(platform.system() != "Windows", "non-Windows guard only")
    def test_job_object_check_fails_on_non_windows_instead_of_simulating(self):
        with self.assertRaisesRegex(RuntimeError, "only available on Windows"):
            _check_job_object()


if __name__ == "__main__":
    unittest.main()
