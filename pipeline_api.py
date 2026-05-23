from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import main as pipeline_cli


@dataclass(slots=True)
class ProjectPaths:
    metadata_path: Path = Path("data/raw/server_metadata/servers_metadata.txt")
    dataset_path: Path = Path("data/raw/dataset.zst")
    selected_servers_parquet: Path = Path("data/processed/software_servers.parquet")
    selected_servers_json: Path = Path("data/processed/software_servers.json")
    messages_parquet: Path = Path("data/processed/software_messages.parquet")
    channel_scores_parquet: Path = Path("data/processed/software_channels.parquet")
    channel_scores_json: Path = Path("data/processed/software_channels.json")
    database_path: Path = Path("data/duckdb/discord_unveiled.duckdb")


@dataclass(slots=True)
class SelectionConfig:
    profile: str = "software"
    min_positive_score: int | None = None
    min_score_margin: int | None = None
    positive_regex: list[str] = field(default_factory=list)
    negative_regex: list[str] = field(default_factory=list)
    positive_regex_weight: int = 2
    negative_regex_weight: int = 2
    output_parquet: Path | None = None
    output_json: Path | None = None


@dataclass(slots=True)
class ExtractLocalConfig:
    dataset_path: Path | None = None
    selected_servers_path: Path | None = None
    output_parquet: Path | None = None
    exclude_bots: bool = False
    batch_size: int = 50_000
    include_channel_regex: list[str] = field(default_factory=list)
    exclude_channel_regex: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ExtractRemoteConfig:
    selected_servers_path: Path | None = None
    output_parquet: Path | None = None
    remote_path: str = pipeline_cli.DATASET_REMOTE_PATH
    exclude_bots: bool = False
    batch_size: int = 50_000
    download_chunk_mb: int = 8
    include_channel_regex: list[str] = field(default_factory=list)
    exclude_channel_regex: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ChannelScoringConfig:
    messages_parquet: Path | None = None
    output_parquet: Path | None = None
    output_json: Path | None = None
    min_messages: int = 50


@dataclass(slots=True)
class DuckDBConfig:
    messages_parquet: Path | None = None
    servers_parquet: Path | None = None
    channels_parquet: Path | None = None
    database_path: Path | None = None


class DiscordUnveiledPipeline:
    def __init__(self, paths: ProjectPaths | None = None) -> None:
        self.paths = paths or ProjectPaths()

    def list_profiles(self) -> None:
        pipeline_cli.list_profiles()

    def download_metadata(self, output_path: Path | None = None) -> Path:
        resolved_output = output_path or self.paths.metadata_path
        pipeline_cli.download_metadata(output_path=resolved_output)
        return resolved_output

    def download_dataset(self, output_path: Path | None = None) -> Path:
        resolved_output = output_path or self.paths.dataset_path
        pipeline_cli.download_dataset(output_path=resolved_output)
        return resolved_output

    def select_servers(self, config: SelectionConfig | None = None) -> tuple[Path, Path]:
        cfg = config or SelectionConfig()
        output_parquet = cfg.output_parquet or self.paths.selected_servers_parquet
        output_json = cfg.output_json or self.paths.selected_servers_json

        pipeline_cli.select_servers(
            metadata_path=self.paths.metadata_path,
            output_parquet=output_parquet,
            output_json=output_json,
            profile=cfg.profile,
            min_positive_score=cfg.min_positive_score,
            min_score_margin=cfg.min_score_margin,
            positive_regex=cfg.positive_regex or None,
            negative_regex=cfg.negative_regex or None,
            positive_regex_weight=cfg.positive_regex_weight,
            negative_regex_weight=cfg.negative_regex_weight,
        )
        return output_parquet, output_json

    def extract_messages_local(self, config: ExtractLocalConfig | None = None) -> Path:
        cfg = config or ExtractLocalConfig()
        dataset_path = cfg.dataset_path or self.paths.dataset_path
        selected_servers_path = cfg.selected_servers_path or self.paths.selected_servers_parquet
        output_parquet = cfg.output_parquet or self.paths.messages_parquet

        pipeline_cli.extract_messages(
            dataset_path=dataset_path,
            selected_servers_path=selected_servers_path,
            output_parquet=output_parquet,
            exclude_bots=cfg.exclude_bots,
            batch_size=cfg.batch_size,
            include_channel_regex=cfg.include_channel_regex or None,
            exclude_channel_regex=cfg.exclude_channel_regex or None,
        )
        return output_parquet

    def extract_messages_remote(self, config: ExtractRemoteConfig | None = None) -> Path:
        cfg = config or ExtractRemoteConfig()
        selected_servers_path = cfg.selected_servers_path or self.paths.selected_servers_parquet
        output_parquet = cfg.output_parquet or self.paths.messages_parquet

        pipeline_cli.extract_messages_remote(
            selected_servers_path=selected_servers_path,
            output_parquet=output_parquet,
            remote_path=cfg.remote_path,
            exclude_bots=cfg.exclude_bots,
            batch_size=cfg.batch_size,
            download_chunk_mb=cfg.download_chunk_mb,
            include_channel_regex=cfg.include_channel_regex or None,
            exclude_channel_regex=cfg.exclude_channel_regex or None,
        )
        return output_parquet

    def score_channels(self, config: ChannelScoringConfig | None = None) -> tuple[Path, Path]:
        cfg = config or ChannelScoringConfig()
        messages_parquet = cfg.messages_parquet or self.paths.messages_parquet
        output_parquet = cfg.output_parquet or self.paths.channel_scores_parquet
        output_json = cfg.output_json or self.paths.channel_scores_json

        pipeline_cli.score_channels(
            messages_parquet=messages_parquet,
            output_parquet=output_parquet,
            output_json=output_json,
            min_messages=cfg.min_messages,
        )
        return output_parquet, output_json

    def init_duckdb(self, config: DuckDBConfig | None = None) -> Path:
        cfg = config or DuckDBConfig()
        messages_parquet = cfg.messages_parquet or self.paths.messages_parquet
        servers_parquet = cfg.servers_parquet or self.paths.selected_servers_parquet
        channels_parquet = cfg.channels_parquet or self.paths.channel_scores_parquet
        database_path = cfg.database_path or self.paths.database_path

        pipeline_cli.init_duckdb(
            messages_parquet=messages_parquet,
            servers_parquet=servers_parquet,
            channels_parquet=channels_parquet,
            database_path=database_path,
        )
        return database_path
