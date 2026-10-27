import contextlib
import io
import re
import sys
import tomllib
import unittest
from pathlib import Path
from urllib.parse import unquote, urlsplit
from unittest.mock import patch

from discord_disentanglement.cli import build_parser, main


class PreparationCliTests(unittest.TestCase):
    def test_pipeline_scope_and_dependencies_exclude_legacy_experiments(self):
        root = Path(__file__).resolve().parents[1]
        for directory in ("approaches", "experiments", "evaluation", "training", "ui"):
            self.assertFalse((root / "discord_disentanglement" / directory).exists())
        self.assertFalse((root / "configs/filtering/games.v1.json").exists())
        project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        self.assertEqual(set(project["scripts"]), {"discord-data", "discord-filter", "discord-prepare"})
        locked = tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))
        names = {package["name"] for package in locked["package"]}
        self.assertTrue(names.isdisjoint({"scikit-learn", "streamlit", "matplotlib"}))

    def test_pipeline_overview_links_point_to_retained_files(self):
        root = Path(__file__).resolve().parents[1]
        for relative in ("README.md", "annotations/README.md", "docs/methodology/DISENTANGLEMENT_DATASET_PIPELINE.md", "docs/methodology/DISCORD_UNVEILED_FILTERING.md"):
            document = root / relative
            for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", document.read_text(encoding="utf-8")):
                parsed = urlsplit(target)
                if parsed.scheme or not parsed.path:
                    continue
                with self.subTest(document=relative, target=target):
                    self.assertTrue((document.parent / unquote(parsed.path)).resolve().exists())

    def test_only_data_preparation_commands_are_exposed(self):
        parser = build_parser()
        for command in ("run", "all", "gold-standard", "derive-human-components", "derive-annotation-components"):
            with self.subTest(command=command), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    parser.parse_args([command])
                self.assertEqual(result.exception.code, 2)
        self.assertFalse(any(name.startswith("discord_disentanglement.approaches") for name in sys.modules))

    def test_arguments_reach_the_existing_stage(self):
        with patch("discord_disentanglement.population.main") as handler:
            main(["population", "--memory-limit", "512MB"])
            handler.assert_called_once_with(["--memory-limit", "512MB"])
        with patch("discord_disentanglement.sampling.main") as handler:
            main(["draw", "--seed", "42"])
            handler.assert_called_once_with(["draw", "--seed", "42"])

    def test_stage_help_is_forwarded_without_execution(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), self.assertRaises(SystemExit) as result:
            main(["population", "--help"])
        self.assertEqual(result.exception.code, 0)
        self.assertIn("--memory-limit", output.getvalue())