"""Compiler selection from the configured build environment."""

import os
import unittest
from unittest.mock import patch

import cpp_toolchain as toolchain


class CompilerDiscoveryTests(unittest.TestCase):
    def test_windows_without_compiler_requests_developer_environment(self):
        with patch.dict(os.environ, {"CXX": ""}), \
                patch.object(toolchain.sys, "platform", "win32"), \
                patch.object(toolchain.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Developer environment"):
                toolchain.find_compiler()

    def test_explicit_compiler_is_not_replaced(self):
        with patch.dict(os.environ, {"CXX": "custom compiler/clang++.exe"}), \
                patch.object(toolchain.shutil, "which") as search:
            self.assertEqual(toolchain.find_compiler(), "custom compiler/clang++.exe")
            search.assert_not_called()

    def test_path_compiler_is_used_on_windows_and_macos(self):
        for host, compiler in (("win32", "native tools/cl.exe"),
                               ("darwin", "/usr/bin/clang++")):
            with self.subTest(host=host), patch.dict(os.environ, {"CXX": ""}), \
                    patch.object(toolchain.sys, "platform", host), \
                    patch.object(toolchain.shutil, "which", return_value=compiler):
                self.assertEqual(toolchain.find_compiler(), compiler)


if __name__ == "__main__":
    unittest.main()
