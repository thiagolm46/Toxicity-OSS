from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from discord_filtering import (
    ProfileValidationError,
    classify_server,
    load_profile,
    profile_from_dict,
    score_channel,
)
from discord_filtering.storage import (
    OutputExistsError,
    build_manifest,
    sha256_file,
    write_records_with_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
SOFTWARE_PROFILE = ROOT / "configs" / "filtering" / "software.v1.json"
GAMES_PROFILE = ROOT / "configs" / "filtering" / "games.v1.json"


class ProfileValidationTests(unittest.TestCase):
    def test_both_domains_use_the_same_validated_model(self) -> None:
        software = load_profile(SOFTWARE_PROFILE)
        games = load_profile(GAMES_PROFILE)

        self.assertEqual(software.profile_id, "software")
        self.assertEqual(games.profile_id, "games")
        self.assertEqual(software.server.overlap_policy, "max_per_group")
        self.assertEqual(games.channel.overlap_policy, "max_per_group")

    def test_unknown_profile_keys_are_rejected(self) -> None:
        raw = json.loads(SOFTWARE_PROFILE.read_text(encoding="utf-8"))
        raw["unreviewed_option"] = True

        with self.assertRaises(ProfileValidationError):
            profile_from_dict(raw)


class ServerFilteringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profile = load_profile(SOFTWARE_PROFILE)

    def test_keywords_accept_list_string_and_na(self) -> None:
        base = {"id": "1", "name": "Open Source", "description": None}
        from_list = classify_server({**base, "keywords": ["programming"]}, self.profile)
        from_string = classify_server({**base, "keywords": "programming"}, self.profile)
        from_na = classify_server({**base, "keywords": math.nan}, self.profile)
        from_sentinels = classify_server(
            {**base, "keywords": ["NA", "n/a", "null", "programming"]},
            self.profile,
        )

        self.assertTrue(from_list.is_selected)
        self.assertTrue(from_string.is_selected)
        self.assertEqual(from_list.positive_score, from_string.positive_score)
        self.assertEqual(from_na.keywords, ())
        self.assertEqual(from_sentinels.keywords, ("programming",))

    def test_cpp_csharp_boundaries_and_field_provenance(self) -> None:
        result = classify_server(
            {
                "id": "42",
                "name": "Software Development",
                "description": "Community for C++ and C# developers",
                "about": "DevOps collaboration",
                "reasons_to_join": ["Learn Ｐｙｔｈｏｎ", "Contribute code"],
                "keywords": ["open source"],
            },
            self.profile,
        )
        labels = {item.label for item in result.positive_evidence}
        evidence_fields = {item.field for item in result.positive_evidence}

        self.assertTrue(result.is_selected)
        self.assertTrue({"c++", "c#"}.issubset(labels))
        self.assertTrue(
            {"name", "description", "about", "reasons_to_join", "keywords"}.issubset(
                evidence_fields
            )
        )
        self.assertEqual(result.to_record()["about"], "DevOps collaboration")
        self.assertEqual(
            json.loads(result.to_record()["reasons_to_join_json"]),
            ["Learn Python", "Contribute code"],
        )

        false_boundary = classify_server(
            {"id": "43", "name": "abc++ and c##", "keywords": None},
            self.profile,
        )
        false_labels = {item.label for item in false_boundary.positive_evidence}
        self.assertNotIn("c++", false_labels)
        self.assertNotIn("c#", false_labels)

    def test_overlap_policy_credits_only_max_once_per_group(self) -> None:
        result = classify_server(
            {"id": "7", "name": "Programming and coding", "keywords": []},
            self.profile,
        )
        group_evidence = [
            item for item in result.positive_evidence if item.group == "programming-core"
        ]

        self.assertEqual(result.positive_score, 4.0)
        self.assertEqual(sum(item.credited_weight for item in group_evidence), 4.0)
        self.assertEqual({item.label for item in group_evidence}, {"programming", "coding"})


class ChannelScoringTests(unittest.TestCase):
    def test_profiles_score_channels_with_one_pure_engine(self) -> None:
        software = load_profile(SOFTWARE_PROFILE)
        software_messages = [
            {
                "message_id": str(index),
                "author_id": str(index % 4),
                "is_bot": index == 0,
                "content": (
                    "pip install package config.py traceback TypeError github.com/org/repo "
                    "issue branch release open source"
                ),
            }
            for index in range(60)
        ]
        software_result = score_channel(
            {"guild_id": "1", "channel_id": "10", "channel_name": "general"},
            software,
            messages=software_messages,
        )

        self.assertEqual(software_result.channel_class, "A")
        self.assertEqual(software_result.n_messages, 59)
        self.assertEqual(software_result.n_bot_messages, 1)
        self.assertEqual(
            software_result.to_record()["software_channel_score"],
            software_result.channel_score,
        )
        self.assertLessEqual(
            max(len(signal.evidence) for signal in software_result.signal_scores),
            software.channel.max_evidence_examples,
        )

        games = load_profile(GAMES_PROFILE)
        game_messages = [
            {
                "message_id": str(index),
                "author_id": str(index % 3),
                "is_bot": False,
                "content": (
                    "Valorant gameplay match ranked MMR strategy loadout Steam looking for group "
                    "play tonight new season"
                ),
            }
            for index in range(30)
        ]
        game_result = score_channel(
            {"guild_id": "2", "channel_id": "20", "channel_name": "gameplay"},
            games,
            messages=game_messages,
        )

        self.assertEqual(game_result.channel_class, "A")
        self.assertEqual(game_result.to_record()["game_channel_score"], game_result.channel_score)


class ArtifactSafetyTests(unittest.TestCase):
    def test_atomic_output_has_hash_manifest_and_refuses_overwrite(self) -> None:
        profile = load_profile(SOFTWARE_PROFILE)
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = directory / "source.json"
            source.write_text("[]\n", encoding="utf-8")
            output = directory / "result.json"
            manifest = build_manifest(
                command="test",
                profile_path=SOFTWARE_PROFILE,
                profile_id=profile.profile_id,
                profile_version=profile.profile_version,
                domain=profile.domain,
                input_paths=[source],
                parameters={},
                counts={"rows": 1},
            )
            _, manifest_path = write_records_with_manifest(
                [{"guild_id": "1", "is_selected": True}],
                output,
                manifest,
            )
            saved_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(saved_manifest["output"]["sha256"], sha256_file(output))
            self.assertEqual(saved_manifest["source_data_policy"], "read_only_immutable")
            with self.assertRaises(OutputExistsError):
                write_records_with_manifest([], output, manifest)

    def test_atomic_parquet_output_is_fsynced_on_windows(self) -> None:
        profile = load_profile(SOFTWARE_PROFILE)
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            source = directory / "source.json"
            source.write_text("[]\n", encoding="utf-8")
            output = directory / "result.parquet"
            manifest = build_manifest(
                command="test-parquet",
                profile_path=SOFTWARE_PROFILE,
                profile_id=profile.profile_id,
                profile_version=profile.profile_version,
                domain=profile.domain,
                input_paths=[source],
                parameters={},
                counts={"rows": 1},
            )

            _, manifest_path = write_records_with_manifest(
                [{"guild_id": "1", "is_selected": True}],
                output,
                manifest,
            )

            self.assertTrue(output.exists())
            self.assertEqual(
                json.loads(manifest_path.read_text(encoding="utf-8"))["output"]["sha256"],
                sha256_file(output),
            )


if __name__ == "__main__":
    unittest.main()
