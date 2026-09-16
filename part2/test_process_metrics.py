"""Exercise native child accounting on every CI OS, including after child exit."""

import ctypes
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch

import process_metrics as metrics


class ProcessMetricsTests(unittest.TestCase):
    def run_python(self, code, **kwargs):
        return metrics.run_measured([sys.executable, "-c", code], **kwargs)

    def test_counts_faults_for_each_child_after_exit(self):
        _, _, small = self.run_python("pass")
        result, seconds, large = self.run_python(
            "import sys; data = bytearray(64 * 1024 * 1024); "
            "print(len(data)); print('diagnostic', file=sys.stderr)")
        _, _, next_small = self.run_python("pass")
        self.assertEqual(result.stdout, "67108864\n")
        self.assertEqual(result.stderr, "diagnostic\n")
        self.assertGreater(seconds, 0)
        # A freshly touched 64 MiB allocation must register well beyond startup
        # noise, even with macOS's 16 KiB pages. Later children must not inherit
        # this count.
        self.assertGreater(large["total"], small["total"] + 512)
        self.assertGreater(large["total"], next_small["total"] + 512)
        for faults in (small, large, next_small):
            self.assertIsInstance(faults["total"], int)
            self.assertGreater(faults["total"], 0)
            if sys.platform == "win32":
                self.assertIsNone(faults["minor"])
                self.assertIsNone(faults["major"])
            else:
                self.assertGreaterEqual(faults["minor"], 0)
                self.assertGreaterEqual(faults["major"], 0)
                self.assertEqual(faults["total"], faults["minor"] + faults["major"])

    def test_nonzero_exit_preserves_diagnostics(self):
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            self.run_python("import sys; print('out'); print('err', file=sys.stderr); sys.exit(7)")
        self.assertEqual(caught.exception.returncode, 7)
        self.assertEqual(caught.exception.stdout, "out\n")
        self.assertEqual(caught.exception.stderr, "err\n")

    def test_timeout_kills_and_reaps_child(self):
        children = []
        original_popen = subprocess.Popen

        def launch(*args, **kwargs):
            child = original_popen(*args, **kwargs)
            children.append(child)
            return child

        with patch.object(metrics.subprocess, "Popen", side_effect=launch):
            with self.assertRaises(subprocess.TimeoutExpired):
                self.run_python("import time; time.sleep(60)", timeout=0.1)
        self.assertEqual(len(children), 1)
        self.assertIsNotNone(children[0].returncode)
        self.assertNotEqual(children[0].returncode, 0)
        self.assertTrue(children[0].stdout.closed)
        self.assertTrue(children[0].stderr.closed)
        result, _, _ = self.run_python("print('ready')")
        self.assertEqual(result.stdout, "ready\n")

    def test_windows_counter_abi_and_full_width_handle(self):
        query = Mock()
        handle = 0x123456789 if ctypes.sizeof(ctypes.c_void_p) == 8 else 0x12345678

        def fill(actual_handle, pointer, size):
            self.assertEqual(actual_handle, handle)
            counters = ctypes.cast(pointer, ctypes.POINTER(metrics.ProcessMemoryCounters)).contents
            self.assertEqual(size, 8 + 8 * ctypes.sizeof(ctypes.c_size_t))
            self.assertEqual(counters.cb, size)
            counters.PageFaultCount = 12345
            return 1

        query.side_effect = fill
        with patch.object(ctypes, "WinDLL", create=True, return_value=Mock(GetProcessMemoryInfo=query)):
            reader = metrics.WindowsPageFaults()
        self.assertEqual(query.argtypes[0], ctypes.c_void_p)
        self.assertEqual(reader.read(Mock(_handle=handle)),
                         {"total": 12345, "minor": None, "major": None})

    def test_windows_api_failure_is_not_reported_as_zero(self):
        query = Mock(return_value=0)
        with patch.object(ctypes, "WinDLL", create=True, return_value=Mock(GetProcessMemoryInfo=query)), \
                patch.object(ctypes, "get_last_error", create=True, return_value=5), \
                patch.object(ctypes, "WinError", create=True, return_value=OSError("access denied")):
            reader = metrics.WindowsPageFaults()
            with self.assertRaisesRegex(OSError, "access denied"):
                reader.read(Mock(_handle=123))


if __name__ == "__main__":
    unittest.main()
