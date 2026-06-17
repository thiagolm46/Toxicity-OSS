from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from main import classify_server, score_channels_from_messages


class ServerSelectionTests(unittest.TestCase):
    def test_max_negative_score_excludes_noisy_candidate(self) -> None:
        record = {
            "id": "1",
            "name": "Open source programming github framework crypto giveaway",
            "description": "software development community",
            "keywords": [],
        }

        result = classify_server(
            record,
            min_positive_score=8,
            min_score_margin=2,
            max_negative_score=2,
            blocked_negative_labels=set(),
        )

        self.assertGreaterEqual(result["positive_score"], 8)
        self.assertGreater(result["negative_score"], 2)
        self.assertFalse(result["is_selected"])


class ChannelScoringTests(unittest.TestCase):
    def test_generic_technical_channel_is_class_a_and_social_channel_is_class_c(self) -> None:
        rows: list[dict[str, object]] = []
        for index in range(60):
            rows.append(
                {
                    "guild_id": "1",
                    "guild_name": "OSS Project",
                    "message_id": str(index),
                    "channel_id": "10",
                    "channel_name": "general",
                    "author_id": str(index % 4),
                    "is_bot": False,
                    "timestamp": "2026-01-01T00:00:00Z",
                    "content": "pip install package traceback TypeError github.com/org/repo issue branch",
                }
            )
        for index in range(60):
            rows.append(
                {
                    "guild_id": "1",
                    "guild_name": "OSS Project",
                    "message_id": str(100 + index),
                    "channel_id": "11",
                    "channel_name": "memes",
                    "author_id": str(index % 4),
                    "is_bot": False,
                    "timestamp": "2026-01-01T00:00:00Z",
                    "content": "lol weekend random meme",
                }
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            messages_path = Path(temp_dir) / "messages.parquet"
            pd.DataFrame(rows).to_parquet(messages_path, index=False)

            scored = score_channels_from_messages(messages_path, min_messages=1)

        classes = dict(zip(scored["channel_name"], scored["channel_class"], strict=True))
        self.assertEqual(classes["general"], "A")
        self.assertEqual(classes["memes"], "C")


if __name__ == "__main__":
    unittest.main()