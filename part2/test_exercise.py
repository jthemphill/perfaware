"""Ensure tasks only instrument builds whose phase timings are displayed."""

import json
import unittest
from unittest.mock import patch

import exercise


class ProfilingBuildTests(unittest.TestCase):
    def test_build_does_not_retain_profiling_on_next_default_build(self):
        with patch.object(exercise, "run") as run, \
                patch.object(exercise, "BUILD"):
            exercise.build(profiling=True)
            exercise.build()
        profiled, ordinary = [call.args for call in run.call_args_list]
        self.assertIn("--no-default-features", profiled)
        self.assertEqual(profiled[-2:], ("--features", "profiling"))
        self.assertIn("--no-default-features", ordinary)
        self.assertNotIn("--features", ordinary)

    def test_only_tasks_displaying_phase_stats_enable_profiling(self):
        tasks = json.loads((exercise.ROOT / ".vscode/tasks.json").read_text())["tasks"]
        profiled = {task["label"] for task in tasks if "--profiling" in task.get("args", [])}
        self.assertEqual(profiled, {"Haversine: Check correctness", "Haversine: Benchmark at scale"})

    def test_cli_passes_profiling_option_to_build(self):
        for options, enabled in (([], False), (["--profiling"], True)):
            with self.subTest(enabled=enabled), \
                    patch("sys.argv", ["exercise.py", "correctness", *options]), \
                    patch.object(exercise, "build") as build, \
                    patch.object(exercise, "correctness"):
                self.assertEqual(exercise.main(), 0)
                build.assert_called_once_with(profiling=enabled)


if __name__ == "__main__":
    unittest.main()
