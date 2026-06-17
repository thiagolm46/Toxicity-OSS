from __future__ import annotations

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pathlib import Path

from pipeline_api import (
    ChannelScoringConfig,
    DiscordUnveiledPipeline,
    ExtractRemoteConfig,
    ProjectPaths,
    SelectionConfig,
)


def main() -> None:
    paths = ProjectPaths(
        metadata_path=Path("data/raw/server_metadata/servers_metadata.txt"),
        selected_servers_parquet=Path("data/processed/software_servers_software.parquet"),
        selected_servers_json=Path("data/processed/software_servers_software.json"),
        messages_parquet=Path("data/processed/software_messages_software.parquet"),
        channel_scores_parquet=Path("data/processed/software_channels_software.parquet"),
        channel_scores_json=Path("data/processed/software_channels_software.json"),
        database_path=Path("data/duckdb/discord_unveiled_software.duckdb"),
    )
    pipeline = DiscordUnveiledPipeline(paths)

    # Pass everything via code and keep reusable configs for each research profile.
    pipeline.select_servers(
        SelectionConfig(
            profile="software",
            min_positive_score=8,
            min_score_margin=2,
            max_negative_score=2,
        )
    )

    pipeline.extract_messages_remote(
        ExtractRemoteConfig(
            selected_servers_path=paths.selected_servers_parquet,
            output_parquet=paths.messages_parquet,
            exclude_bots=True,
        )
    )

    pipeline.score_channels(
        ChannelScoringConfig(
            messages_parquet=paths.messages_parquet,
            output_parquet=paths.channel_scores_parquet,
            output_json=paths.channel_scores_json,
            min_messages=50,
        )
    )

    pipeline.init_duckdb()


if __name__ == "__main__":
    main()
