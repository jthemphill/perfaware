"""Regression checks for the comparison harness's failure detection."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import compare_casey as compare


class ComparisonTests(unittest.TestCase):
    def test_build_selects_native_compiler_and_output_flags(self):
        cases = (("win32", ".exe", "cl", "/O2"),
                 ("darwin", "", "clang++", "-O3"))
        for host, suffix, compiler, optimization in cases:
            with self.subTest(host=host), tempfile.TemporaryDirectory(prefix="casey build ") as directory:
                build = Path(directory)
                source = build / "source"
                source.mkdir()
                (source / "listing_0067_simple_haversine_main.cpp").touch()
                result = subprocess.CompletedProcess([], 0, "version", "")
                with patch.dict(os.environ, {"CXX": ""}), \
                        patch.object(compare.sys, "platform", host), \
                        patch.object(compare.ex, "SUFFIX", suffix), \
                        patch.object(compare, "BUILD", build), \
                        patch.object(compare, "SOURCE", source), \
                        patch.object(compare.shutil, "which", side_effect=lambda name: name), \
                        patch.object(compare, "invoke", return_value=result):
                    commands = compare.build_casey()["commands"]
                for name, command in zip(("average", "generate"), commands):
                    self.assertEqual(command[0], compiler)
                    self.assertIn(optimization, command)
                    output = str(build / (name + suffix))
                    self.assertIn(f"/Fe:{output}" if host == "win32" else output, command)

    def test_rounding_difference_is_allowed(self):
        mean = compare.parse_result("casey", "Pair count: 65\nHaversine sum: 5000.0000000001\n", 65, 5000)
        self.assertAlmostEqual(mean, 5000)

    def test_missing_wrong_count_and_wrong_mean_fail(self):
        for output in ("", "Pair count: 64\nHaversine sum: 5000\n",
                       "Pair count: 65\nHaversine sum: 5010\n"):
            with self.subTest(output=output), self.assertRaises(RuntimeError):
                compare.parse_result("casey", output, 65, 5000)

    def test_nonfinite_results_fail_for_both_programs(self):
        for value in ("nan", "inf", "-inf"):
            for name, text in (("rust", f"Mean Haversine distance: {value} km"),
                               ("casey", f"Haversine sum: {value}")):
                with self.subTest(name=name, value=value), self.assertRaises(RuntimeError):
                    compare.parse_result(name, "Pair count: 1\n" + text, 1, 0)

    def test_programs_are_compared_directly(self):
        # Both could be within tolerance of zero yet disagree with each other.
        with patch.object(compare, "measure", side_effect=[
                {"mean_km": -0.9e-8}, {"mean_km": 0.9e-8}]), self.assertRaises(RuntimeError):
            compare.compare(Path("input.json"), 1, 0)

    def test_upstream_error_with_success_exit_fails(self):
        result = subprocess.CompletedProcess([], 0, "Pair count: 1\nHaversine sum: 0\n",
                                             "ERROR: malformed input\n")
        with patch.object(compare, "invoke", return_value=result), self.assertRaises(RuntimeError):
            compare.measure("casey", Path("input.json"), 1, 0)


if __name__ == "__main__":
    unittest.main()
