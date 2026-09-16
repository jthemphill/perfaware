"""Regression checks for the comparison harness's failure detection."""

import os
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
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
                        patch.object(compare, "find_compiler", return_value=compiler), \
                        patch.object(compare, "invoke", return_value=result):
                    commands = compare.build_casey()["commands"]
                    builds = [call for call in compare.invoke.call_args_list if call.kwargs.get("cwd") == build]
                    self.assertEqual(len(builds), 2)
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
        with patch.object(compare, "run_measured", return_value=(result, 0.1, {})), self.assertRaises(RuntimeError):
            compare.measure("casey", Path("input.json"), 1, 0)

    def test_measure_attaches_faults_to_correct_program(self):
        for name, output in (("rust", "Mean Haversine distance: 0 km"),
                             ("casey", "Haversine sum: 0")):
            result = subprocess.CompletedProcess([], 0, "Pair count: 1\n" + output + "\n", "")
            faults = {"total": 12, "minor": 10, "major": 2}
            with self.subTest(name=name), patch.object(compare, "run_measured", return_value=(result, 0.25, faults)):
                measured = compare.measure(name, Path("input.json"), 1, 0)
                program = compare.ex.binary("average") if name == "rust" else compare.BUILD / ("average" + compare.ex.SUFFIX)
                compare.run_measured.assert_called_once_with([program, Path("input.json")], cwd=compare.ex.ROOT)
            self.assertEqual(measured, {"seconds": 0.25, "mean_km": 0, "page_faults": faults})

    def test_benchmark_reports_faults_and_excludes_warmup(self):
        for split in (True, False):
            def round_result(total):
                return ({name: {"seconds": 0.25, "mean_km": 0,
                                "page_faults": {"total": total * multiplier,
                                                "minor": total * multiplier if split else None,
                                                "major": 0 if split else None}}
                         for name, multiplier in (("rust", 1), ("casey", 2))}, 0)

            with self.subTest(split=split), tempfile.TemporaryDirectory() as directory:
                build = Path(directory)
                path = build / "input.json"
                path.write_text('{}', encoding="utf-8")
                args = SimpleNamespace(dataset="rust", method="cluster", seed=42,
                                       pairs=1, regenerate=False, repeats=2)
                output = io.StringIO()
                with patch.object(compare, "BUILD", build), \
                        patch.object(compare, "dataset", return_value=(path, 0)), \
                        patch.object(compare, "compare", side_effect=[round_result(999), round_result(10), round_result(11)]), \
                        patch.object(compare, "invoke", return_value=subprocess.CompletedProcess([], 0, "rustc version", "")), \
                        redirect_stdout(output):
                    compare.benchmark(args, {})
                report = json.loads(next((build / "benchmarks").glob("*.json")).read_text())
                self.assertEqual(report["median_page_faults"]["rust"]["total"], 10.5)
                self.assertEqual(report["median_page_faults"]["casey"]["total"], 21)
                self.assertEqual(report["median_page_faults"]["rust"]["minor"], 10.5 if split else None)
                self.assertEqual(report["rounds"][1]["order"], ["casey", "rust"])
                self.assertEqual(report["rounds"][0]["results"]["rust"]["page_faults"]["total"], 10)
                self.assertEqual(report["page_fault_backend"], compare.page_fault_backend())
                self.assertIn("10.5 page faults", output.getvalue())
                self.assertNotIn("999 page faults", output.getvalue())


if __name__ == "__main__":
    unittest.main()
