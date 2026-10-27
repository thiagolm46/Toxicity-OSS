import json
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from discord_filtering.channel_selection import (
    channel_decisions,
    freeze_historical_selection,
    verify_historical_selection,
)
from discord_filtering.storage import sha256_file
from discord_filtering.interaction_audit import audit_interacting_authors, compare_candidates, main as interaction_audit_main, write_audit_report


class ChannelDecisionTests(unittest.TestCase):
    def test_new_audit_does_not_overwrite_a_shared_report_by_default(self):
        with patch("sys.argv", ["interaction_audit", "--output", "new-audit"]), \
             patch("discord_filtering.interaction_audit.audit_interacting_authors", return_value={}) as audit, \
             patch("discord_filtering.interaction_audit.write_audit_report") as report, \
             contextlib.redirect_stdout(io.StringIO()):
            interaction_audit_main()
            audit.assert_called_once()
            report.assert_not_called()

    def test_interaction_hypotheses_distinguish_senders_and_resolved_replies(self):
        base = {"guild_id": "g", "channel_id": "c", "is_bot": False,
                "timestamp": "2026-01-01T00:00:00Z", "referenced_message_id": None,
                "mention_count": 0}
        rows = [
            {**base, "message_id": "1", "author_id": "a"},
            {**base, "message_id": "2", "author_id": "b", "referenced_message_id": "1"},
            {**base, "message_id": "3", "author_id": "c", "mention_count": 1},
            {**base, "message_id": "4", "author_id": "d", "referenced_message_id": "absent"},
            {**base, "message_id": "5", "author_id": "a", "referenced_message_id": "1"},
            {**base, "message_id": "6", "author_id": "bot", "is_bot": True, "mention_count": 1},
        ]
        statistics = pd.DataFrame([{"guild_id": "g", "guild_name": "Guild", "channel_id": "c",
                                    "channel_name": "general", "total_messages": 6, "interacting_authors": 4}])
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "messages.parquet"
            pd.DataFrame(rows).to_parquet(source, index=False)
            comparison, candidates = compare_candidates(source, statistics, set(), database=Path(temporary) / "audit.duckdb")
            self.assertEqual(comparison.human_authors.item(), 4)
            self.assertEqual(comparison.reply_senders.item(), 3)
            self.assertEqual(comparison.mention_senders.item(), 1)
            self.assertEqual(comparison.reply_or_mention_senders.item(), 4)
            self.assertEqual(comparison.resolved_reply_senders.item(), 2)
            self.assertEqual(comparison.resolved_reply_or_mention_senders.item(), 3)
            self.assertEqual(comparison.other_author_reply_or_mention_senders.item(), 2)
            exact = candidates.loc[candidates.different_channels == 0, "candidate"].tolist()
            self.assertEqual(exact, ["human_authors", "reply_or_mention_senders"])

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
            for identifier, name, volume, authors in (("1", "tiny", 2, 2), ("2", "NA", 5, 5), ("3", "manual", 2, 2))
        ]).to_parquet(self.statistics, index=False)
        self.exclusions.write_text("manual\n", encoding="utf-8")
        messages = pd.DataFrame([{"guild_id": "g", "channel_id": identifier} for identifier in ["1", "1", *(["2"] * 5), "3", "3"]])
        messages["message_id"] = [str(index) for index in range(len(messages))]
        messages["author_id"] = messages.message_id
        messages["timestamp"] = "2026-01-01T00:00:00Z"
        messages["is_bot"] = False
        messages["referenced_message_id"] = None
        messages["mention_count"] = 1
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

    def test_interaction_audit_records_ambiguity_and_report_provenance(self):
        self._freeze()
        audit_dir = self.root / "interaction-audit"
        summary = audit_interacting_authors(self.source, self.output, audit_dir)
        self.assertIn("resolved_reply_or_mention_senders", summary["exactly_matching_candidates"])
        self.assertIn("human_authors", summary["exactly_matching_candidates"])
        self.assertEqual(summary["historical_definition_status"], "unrecovered")
        report = self.root / "audit.md"
        write_audit_report(audit_dir, report)
        self.assertIn("3 de 3 canais coincidentes", report.read_text(encoding="utf-8"))
        self.assertIn("nao prova", report.read_text(encoding="utf-8"))
        self.assertIn("| Candidata | Canais iguais", report.read_text(encoding="utf-8"))
        self.assertNotIn("|\n\n|", report.read_text(encoding="utf-8"))
        with self.assertRaises(FileExistsError):
            write_audit_report(audit_dir, report)
        with self.assertRaises(FileExistsError):
            audit_interacting_authors(self.source, self.output, audit_dir)
        (audit_dir / "summary.json").write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            write_audit_report(audit_dir, self.root / "tampered.md")

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