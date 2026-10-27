import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from discord_filtering.channel_selection import (
    channel_decisions,
    freeze_historical_selection,
    verify_historical_selection,
)
from discord_filtering.storage import sha256_file


class ChannelDecisionTests(unittest.TestCase):
    def test_strict_boundaries_conjunction_and_exact_manual_names(self):
        rows = [
            ("1", "tiny", 499, 4),
            ("2", "boundary_messages", 500, 4),
            ("3", "boundary_authors", 499, 5),
            ("4", "manual", 1000, 9),
            ("5", "manual", 10, 1),
            ("6", "Manual", 1000, 9),
        ]
        statistics = pd.DataFrame([
            {"guild_id": "g", "guild_name": "Guild", "channel_id": identifier,
             "channel_name": name, "total_messages": volume, "interacting_authors": authors}
            for identifier, name, volume, authors in rows
        ])
        decisions = channel_decisions(statistics, {"manual"})
        self.assertEqual(decisions.retained.tolist(), [False, True, True, False, False, True])
        self.assertEqual(decisions.decision_reason.tolist(), ["low_activity", "retained", "retained", "manual_name", "manual_and_low_activity", "retained"])
        self.assertNotIn("retained", statistics.columns)

    def test_invalid_metrics_or_ambiguous_channel_ids_fail_closed(self):
        base = {"guild_id": "g", "guild_name": "Guild", "channel_id": "1", "channel_name": "general", "total_messages": 500, "interacting_authors": 5}
        for invalid in (None, float("nan"), float("inf"), -1, 1.5, True):
            with self.subTest(invalid=invalid):
                with self.assertRaises((ValueError, TypeError)):
                    channel_decisions(pd.DataFrame([{**base, "interacting_authors": invalid}]), set())
        with self.assertRaisesRegex(ValueError, "globally unique"):
            channel_decisions(pd.DataFrame([base, {**base, "guild_id": "other"}]), set())


class HistoricalBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.statistics = self.root / "statistics.parquet"
        self.exclusions = self.root / "exclusions.txt"
        self.source = self.root / "source.parquet"
        self.retained = self.root / "retained.parquet"
        self.output = self.root / "bundle"
        pd.DataFrame([
            {"guild_id": "g", "guild_name": "Guild", "channel_id": identifier,
             "channel_name": name, "total_messages": volume, "interacting_authors": authors}
            for identifier, name, volume, authors in (("1", "tiny", 2, 1), ("2", "NA", 5, 5), ("3", "manual", 2, 2))
        ]).to_parquet(self.statistics, index=False)
        self.exclusions.write_text("manual\n", encoding="utf-8")
        messages = pd.DataFrame([{"guild_id": "g", "channel_id": identifier} for identifier in ["1", "1", *(["2"] * 5), "3", "3"]])
        messages.to_parquet(self.source, index=False)
        messages.loc[messages.channel_id == "2"].to_parquet(self.retained, index=False)
        self.corpus_manifest = {
            "inputs": [{"path": str(path), "sha256": sha256_file(path)} for path in (self.source, self.statistics, self.exclusions)],
            "output": {"path": str(self.retained), "sha256": sha256_file(self.retained)},
            "counts": {"source_messages": 9, "removed_messages": 4, "remaining_messages": 5},
            "parameters": {"minimum_messages": 500, "minimum_interacting_authors": 5,
                           "excluded_channel_id_count": 2,
                           "low_activity_condition": "total_messages < minimum_messages AND interacting_authors < minimum_interacting_authors"},
        }
        self.statistics_manifest = {
            "inputs": [{"path": str(self.source), "sha256": sha256_file(self.source)}],
            "output": {"path": str(self.statistics), "sha256": sha256_file(self.statistics)},
            "counts": {"source_rows": 9, "total_channels": 3},
        }
        self._write_manifests()

    def _write_manifests(self):
        self.retained.with_name(self.retained.name + ".manifest.json").write_text(json.dumps(self.corpus_manifest), encoding="utf-8")
        self.statistics.with_name(self.statistics.name + ".manifest.json").write_text(json.dumps(self.statistics_manifest), encoding="utf-8")

    def _freeze(self):
        return freeze_historical_selection(self.statistics, self.exclusions, self.source, self.retained, self.output)

    def test_bundle_replays_without_original_sources_and_rejects_tampering(self):
        audit = self._freeze()
        self.assertEqual(audit["counts"]["retained_channels"], 1)
        self.assertEqual(audit["counts"]["overlap"], 1)
        self.assertEqual(audit["historical_metric_definition"], "unrecovered")
        self.assertEqual(verify_historical_selection(self.output), audit)
        with self.assertRaises(FileExistsError):
            self._freeze()
        for path in (self.statistics, self.exclusions, self.source, self.retained):
            path.unlink()
        self.assertEqual(verify_historical_selection(self.output), audit)
        (self.output / "exclusions.txt").write_text("changed\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            verify_historical_selection(self.output)

    def test_wrong_retained_membership_fails_even_with_matching_hash_and_total(self):
        pd.DataFrame([{"guild_id": "g", "channel_id": "wrong"}] * 5).to_parquet(self.retained, index=False)
        self.corpus_manifest["output"]["sha256"] = sha256_file(self.retained)
        self._write_manifests()
        with self.assertRaisesRegex(ValueError, "retained corpus"):
            self._freeze()
        self.assertFalse(self.output.exists())

    def test_changed_statistics_hash_and_wrong_rule_are_rejected(self):
        self.corpus_manifest["parameters"]["low_activity_condition"] = "OR"
        self._write_manifests()
        with self.assertRaisesRegex(ValueError, "conjunction"):
            self._freeze()
        self.corpus_manifest["parameters"]["low_activity_condition"] = "total_messages < minimum_messages AND interacting_authors < minimum_interacting_authors"
        self._write_manifests()
        pd.DataFrame({"changed": [1]}).to_parquet(self.statistics, index=False)
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            self._freeze()