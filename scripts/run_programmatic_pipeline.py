from __future__ import annotations

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from pathlib import Path

from pipeline_api import (
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
        database_path=Path("data/duckdb/discord_unveiled_software.duckdb"),
    )
    pipeline = DiscordUnveiledPipeline(paths)

    # Pass everything via code and keep reusable configs for each research profile.
    pipeline.select_servers(
        SelectionConfig(
            profile="software",
            min_positive_score=6,
            min_score_margin=2,
        )
    )

    pipeline.extract_messages_remote(
        ExtractRemoteConfig(
            selected_servers_path=paths.selected_servers_parquet,
            output_parquet=paths.messages_parquet,
            exclude_bots=True,
            include_channel_regex=[r"dev|help|code|backend|frontend"],
            exclude_channel_regex=[r"off-topic|meme|music"],
        )
    )

    pipeline.init_duckdb()


if __name__ == "__main__":
    main()
