"""Tool discovery must not launch a binary from the other operating system."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import exercise


class NasmTests(unittest.TestCase):
    def test_local_binary_matches_host(self):
        with tempfile.TemporaryDirectory(prefix="nasm tools ") as directory:
            root = Path(directory)
            local = root / ".tools" / "nasm-3.02"
            local.mkdir(parents=True)
            for name in ("nasm", "nasm.exe"):
                (local / name).touch()
            for host, executable in (("win32", "nasm.exe"), ("darwin", "nasm")):
                with self.subTest(host=host), patch.object(exercise, "ROOT", root), \
                        patch.object(exercise.sys, "platform", host), \
                        patch.object(exercise.shutil, "which") as which:
                    self.assertEqual(exercise.nasm(), str(local / executable))
                    which.assert_not_called()

    def test_mac_ignores_windows_binary_and_uses_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            local = root / ".tools" / "nasm-3.02"
            local.mkdir(parents=True)
            (local / "nasm.exe").touch()
            with patch.object(exercise, "ROOT", root), \
                    patch.object(exercise.sys, "platform", "darwin"), \
                    patch.object(exercise.shutil, "which", return_value="/opt/homebrew/bin/nasm"):
                self.assertEqual(exercise.nasm(), "/opt/homebrew/bin/nasm")
            with patch.object(exercise, "ROOT", root), \
                    patch.object(exercise.sys, "platform", "darwin"), \
                    patch.object(exercise.shutil, "which", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "NASM missing"):
                    exercise.nasm()


if __name__ == "__main__":
    unittest.main()
