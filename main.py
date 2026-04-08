from __future__ import annotations

import io
import json
import re
import tarfile
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Any

import duckdb
import httpx
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import typer
import zstandard as zstd
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TransferSpeedColumn,
)
from rich.table import Table

console = Console()
app = typer.Typer(
    add_completion=False,
    help=(
        "Ferramentas para filtrar servidores de software no dataset "
        "Discord-Unveiled e exportar as mensagens para Parquet/DuckDB."
    ),
)

REPO_ID = "SaisExperiments/Discord-Unveiled-Compressed"
METADATA_REMOTE_PATH = "server_metadata/servers_metadata.txt"
DATASET_REMOTE_PATH = "dataset.zst"

PatternRule = tuple[re.Pattern[str], int, str]

SOFTWARE_POSITIVE_PATTERNS: list[PatternRule] = [
    (re.compile(r"\bsoftware engineering\b", re.IGNORECASE), 5, "software engineering"),
    (re.compile(r"\bsoftware development\b", re.IGNORECASE), 5, "software development"),
    (re.compile(r"\bopen[ -]?source\b", re.IGNORECASE), 5, "open source"),
    (re.compile(r"\bprogramming\b", re.IGNORECASE), 4, "programming"),
    (re.compile(r"\bcoding\b", re.IGNORECASE), 4, "coding"),
    (re.compile(r"\bdeveloper(?:s)?\b", re.IGNORECASE), 4, "developer"),
    (re.compile(r"\bdev(?:elopment)?\b", re.IGNORECASE), 2, "dev"),
    (re.compile(r"\bdevops\b", re.IGNORECASE), 4, "devops"),
    (re.compile(r"\bcomputer science\b", re.IGNORECASE), 4, "computer science"),
    (re.compile(r"\bfull[ -]?stack\b", re.IGNORECASE), 3, "full stack"),
    (re.compile(r"\bfront[ -]?end\b", re.IGNORECASE), 3, "frontend"),
    (re.compile(r"\bback[ -]?end\b", re.IGNORECASE), 3, "backend"),
    (re.compile(r"\bweb(?:site)? development\b", re.IGNORECASE), 3, "web development"),
    (re.compile(r"\bapi(?:s)?\b", re.IGNORECASE), 2, "api"),
    (re.compile(r"\bframework(?:s)?\b", re.IGNORECASE), 2, "framework"),
    (re.compile(r"\b(?:library|libraries)\b", re.IGNORECASE), 2, "library"),
    (re.compile(r"\bgithub\b", re.IGNORECASE), 2, "github"),
    (re.compile(r"\bgitlab\b", re.IGNORECASE), 2, "gitlab"),
    (re.compile(r"\bpython\b", re.IGNORECASE), 2, "python"),
    (re.compile(r"\bjavascript\b", re.IGNORECASE), 2, "javascript"),
    (re.compile(r"\btypescript\b", re.IGNORECASE), 2, "typescript"),
    (re.compile(r"\bjava\b", re.IGNORECASE), 2, "java"),
    (re.compile(r"\bc\+\+\b", re.IGNORECASE), 2, "c++"),
    (re.compile(r"\bc#\b", re.IGNORECASE), 2, "c#"),
    (re.compile(r"\brust\b", re.IGNORECASE), 2, "rust"),
    (re.compile(r"\bgolang|\bgo language\b", re.IGNORECASE), 2, "go"),
    (re.compile(r"\bdocker\b", re.IGNORECASE), 2, "docker"),
    (re.compile(r"\bkubernetes|\bk8s\b", re.IGNORECASE), 2, "kubernetes"),
    (re.compile(r"\blinux\b", re.IGNORECASE), 2, "linux"),
    (re.compile(r"\bengineering\b", re.IGNORECASE), 1, "engineering"),
    (re.compile(r"\bcli\b", re.IGNORECASE), 1, "cli"),
]

SOFTWARE_NEGATIVE_PATTERNS: list[PatternRule] = [
    (re.compile(r"\bnsfw\b|\b18\+\b", re.IGNORECASE), 6, "nsfw"),
    (re.compile(r"\bcrypto\b|\bnft\b|\bforex\b|\btrading\b", re.IGNORECASE), 4, "finance/crypto"),
    (re.compile(r"\bdating\b|\bmatchmaking\b", re.IGNORECASE), 4, "dating"),
    (re.compile(r"\bgiveaway\b|\bdrops?\b", re.IGNORECASE), 3, "giveaway"),
    (re.compile(r"\broleplay\b|\brp\b", re.IGNORECASE), 3, "roleplay"),
    (re.compile(r"\bminecraft\b|\bvalorant\b|\broblox\b|\bfortnite\b", re.IGNORECASE), 3, "game title"),
    (re.compile(r"\banime\b|\bmanga\b", re.IGNORECASE), 2, "anime"),
    (re.compile(r"\bmusic\b|\bartist\b|\bconcert\b", re.IGNORECASE), 2, "music"),
    (re.compile(r"\bmeme(?:s)?\b", re.IGNORECASE), 1, "meme"),
]

GAMING_POSITIVE_PATTERNS: list[PatternRule] = [
    (re.compile(r"\bgaming\b|\bgames?\b", re.IGNORECASE), 5, "gaming"),
    (re.compile(r"\besports?\b|\be-?sports\b", re.IGNORECASE), 4, "esports"),
    (
        re.compile(
            r"\bminecraft\b|\bvalorant\b|\broblox\b|\bfortnite\b|\bgenshin\b|\bleague of legends\b|\blol\b|\bcs2\b|\bcsgo\b",
            re.IGNORECASE,
        ),
        4,
        "game title",
    ),
    (re.compile(r"\bsteam\b|\bepic games?\b", re.IGNORECASE), 3, "platform"),
    (re.compile(r"\bclan\b|\bguild\b|\bsquad\b", re.IGNORECASE), 3, "community"),
    (re.compile(r"\bmod(?:ding)?\b|\baddon\b|\bplugin\b", re.IGNORECASE), 3, "modding"),
    (re.compile(r"\bstream(?:er|ing)?\b|\btwitch\b", re.IGNORECASE), 2, "streaming"),
    (re.compile(r"\broleplay\b|\brp\b", re.IGNORECASE), 2, "roleplay"),
]

GAMING_NEGATIVE_PATTERNS: list[PatternRule] = [
    (re.compile(r"\bnsfw\b|\b18\+\b", re.IGNORECASE), 6, "nsfw"),
    (re.compile(r"\bcrypto\b|\bnft\b|\bforex\b|\btrading\b", re.IGNORECASE), 4, "finance/crypto"),
    (re.compile(r"\bdating\b|\bmatchmaking\b", re.IGNORECASE), 4, "dating"),
    (re.compile(r"\bgiveaway\b|\bdrops?\b", re.IGNORECASE), 2, "giveaway"),
]

# Kept for backward compatibility in internal calls and snippets.
POSITIVE_PATTERNS = SOFTWARE_POSITIVE_PATTERNS
NEGATIVE_PATTERNS = SOFTWARE_NEGATIVE_PATTERNS

FILTER_PROFILES: dict[str, dict[str, Any]] = {
    "software": {
        "positive_patterns": SOFTWARE_POSITIVE_PATTERNS,
        "negative_patterns": SOFTWARE_NEGATIVE_PATTERNS,
        "default_min_positive_score": 6,
        "default_min_score_margin": 2,
        "blocked_negative_terms": {"nsfw", "finance/crypto", "game title"},
    },
    "gaming": {
        "positive_patterns": GAMING_POSITIVE_PATTERNS,
        "negative_patterns": GAMING_NEGATIVE_PATTERNS,
        "default_min_positive_score": 5,
        "default_min_score_margin": 1,
        "blocked_negative_terms": {"nsfw", "finance/crypto", "dating"},
    },
}

MESSAGE_SCHEMA = pa.schema(
    [
        pa.field("guild_id", pa.string()),
        pa.field("guild_name", pa.string()),
        pa.field("message_id", pa.string()),
        pa.field("channel_id", pa.string()),
        pa.field("channel_name", pa.string()),
        pa.field("author_id", pa.string()),
        pa.field("author_username", pa.string()),
        pa.field("author_discriminator", pa.string()),
        pa.field("timestamp", pa.string()),
        pa.field("edited_timestamp", pa.string()),
        pa.field("message_type", pa.int64()),
        pa.field("content", pa.string()),
        pa.field("content_length", pa.int64()),
        pa.field("is_bot", pa.bool_()),
        pa.field("pinned", pa.bool_()),
        pa.field("mention_everyone", pa.bool_()),
        pa.field("tts", pa.bool_()),
        pa.field("flags", pa.int64()),
        pa.field("attachment_count", pa.int64()),
        pa.field("embed_count", pa.int64()),
        pa.field("mention_count", pa.int64()),
        pa.field("mention_role_count", pa.int64()),
        pa.field("sticker_count", pa.int64()),
        pa.field("referenced_message_id", pa.string()),
        pa.field("referenced_guild_id", pa.string()),
        pa.field("attachments_json", pa.string()),
        pa.field("embeds_json", pa.string()),
        pa.field("mentions_json", pa.string()),
        pa.field("mention_roles_json", pa.string()),
        pa.field("sticker_items_json", pa.string()),
        pa.field("positive_score", pa.int64()),
        pa.field("matched_positive_terms", pa.string()),
    ]
)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def render_path(path: Path) -> str:
    return str(path.resolve())


def build_hf_url(remote_path: str) -> str:
    return f"https://huggingface.co/datasets/{REPO_ID}/resolve/main/{remote_path}?download=true"


def normalize_profile_name(profile_name: str) -> str:
    normalized = profile_name.strip().lower()
    if normalized in FILTER_PROFILES:
        return normalized
    available_profiles = ", ".join(sorted(FILTER_PROFILES))
    raise typer.BadParameter(
        f"Perfil invalido: '{profile_name}'. Perfis disponiveis: {available_profiles}."
    )


def as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def as_int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build_search_text(record: dict[str, Any]) -> str:
    parts: list[str] = [
        str(record.get("name") or ""),
        str(record.get("description") or ""),
        str(record.get("vanity_url_code") or ""),
        str(record.get("preferred_locale") or ""),
    ]
    keywords = record.get("keywords") or []
    if isinstance(keywords, list):
        parts.extend(str(item) for item in keywords)
    return " ".join(part for part in parts if part).lower()


def score_text(
    text: str,
    patterns: list[PatternRule],
) -> tuple[int, list[str]]:
    score = 0
    matches: list[str] = []
    for pattern, weight, label in patterns:
        if pattern.search(text):
            score += weight
            matches.append(label)
    return score, matches


def build_custom_rules(
    regex_patterns: list[str],
    weight: int,
    label_prefix: str,
    option_name: str,
) -> list[PatternRule]:
    rules: list[PatternRule] = []
    for raw_pattern in regex_patterns:
        pattern_text = raw_pattern.strip()
        if not pattern_text:
            continue
        try:
            compiled = re.compile(pattern_text, re.IGNORECASE)
        except re.error as error:
            raise typer.BadParameter(
                f"Regex invalido em {option_name}: '{pattern_text}' ({error})"
            ) from error
        rules.append((compiled, weight, f"{label_prefix}:{pattern_text}"))
    return rules


def compile_channel_filters(
    include_channel_regex: list[str],
    exclude_channel_regex: list[str],
) -> tuple[list[re.Pattern[str]], list[re.Pattern[str]]]:
    include_patterns: list[re.Pattern[str]] = []
    exclude_patterns: list[re.Pattern[str]] = []

    for raw_pattern in include_channel_regex:
        pattern_text = raw_pattern.strip()
        if not pattern_text:
            continue
        try:
            include_patterns.append(re.compile(pattern_text, re.IGNORECASE))
        except re.error as error:
            raise typer.BadParameter(
                f"Regex invalido em --include-channel-regex: '{pattern_text}' ({error})"
            ) from error

    for raw_pattern in exclude_channel_regex:
        pattern_text = raw_pattern.strip()
        if not pattern_text:
            continue
        try:
            exclude_patterns.append(re.compile(pattern_text, re.IGNORECASE))
        except re.error as error:
            raise typer.BadParameter(
                f"Regex invalido em --exclude-channel-regex: '{pattern_text}' ({error})"
            ) from error

    return include_patterns, exclude_patterns


def is_channel_allowed(
    channel_name: str,
    include_patterns: list[re.Pattern[str]],
    exclude_patterns: list[re.Pattern[str]],
) -> bool:
    if include_patterns and not any(pattern.search(channel_name) for pattern in include_patterns):
        return False
    if exclude_patterns and any(pattern.search(channel_name) for pattern in exclude_patterns):
        return False
    return True


def classify_server(
    record: dict[str, Any],
    min_positive_score: int,
    positive_patterns: list[PatternRule] | None = None,
    negative_patterns: list[PatternRule] | None = None,
    min_score_margin: int = 1,
    blocked_negative_labels: set[str] | None = None,
) -> dict[str, Any]:
    text = build_search_text(record)
    effective_positive_patterns = positive_patterns or POSITIVE_PATTERNS
    effective_negative_patterns = negative_patterns or NEGATIVE_PATTERNS
    effective_blocked_negative_labels = blocked_negative_labels or set()

    positive_score, positive_terms = score_text(text, effective_positive_patterns)
    negative_score, negative_terms = score_text(text, effective_negative_patterns)
    score_margin = positive_score - negative_score
    blocked_terms = sorted(set(negative_terms).intersection(effective_blocked_negative_labels))
    is_selected = (
        positive_score >= min_positive_score
        and score_margin >= min_score_margin
        and not blocked_terms
    )
    keywords = record.get("keywords") or []

    return {
        "guild_id": str(record.get("id") or ""),
        "slug": record.get("slug"),
        "name": record.get("name"),
        "description": record.get("description"),
        "preferred_locale": record.get("preferred_locale"),
        "primary_category_id": (
            str(record.get("primary_category_id"))
            if record.get("primary_category_id") is not None
            else None
        ),
        "approximate_member_count": record.get("approximate_member_count"),
        "approximate_presence_count": record.get("approximate_presence_count"),
        "vanity_url_code": record.get("vanity_url_code"),
        "keywords_json": dump_json(keywords),
        "positive_score": positive_score,
        "negative_score": negative_score,
        "score_margin": score_margin,
        "matched_positive_terms": dump_json(positive_terms),
        "matched_negative_terms": dump_json(negative_terms),
        "blocked_negative_terms": dump_json(blocked_terms),
        "is_selected": is_selected,
    }


def load_metadata(metadata_path: Path) -> list[dict[str, Any]]:
    with metadata_path.open("r", encoding="utf-8") as file_handle:
        return json.load(file_handle)


def show_server_preview(frame: pd.DataFrame, limit: int = 15) -> None:
    preview = frame.head(limit)
    table = Table(title="Servidores selecionados")
    table.add_column("guild_id")
    table.add_column("name")
    table.add_column("positive_score", justify="right")
    table.add_column("negative_score", justify="right")
    table.add_column("score_margin", justify="right")
    table.add_column("matched_positive_terms")

    for row in preview.itertuples(index=False):
        table.add_row(
            str(row.guild_id),
            str(row.name or ""),
            str(row.positive_score),
            str(row.negative_score),
            str(row.score_margin),
            str(row.matched_positive_terms),
        )

    console.print(table)


def stream_hf_file(remote_path: str, output_path: Path, chunk_size: int = 8 * 1024 * 1024) -> None:
    ensure_parent(output_path)
    url = build_hf_url(remote_path)
    total_bytes: int | None = None
    timeout = httpx.Timeout(connect=60.0, read=60.0, write=60.0, pool=60.0)

    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            if content_length:
                total_bytes = int(content_length)

            with output_path.open("wb") as target:
                progress = Progress(
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    DownloadColumn(binary_units=True),
                    TransferSpeedColumn(),
                    TimeElapsedColumn(),
                    console=console,
                )
                with progress:
                    task_id = progress.add_task(f"Baixando {remote_path}", total=total_bytes)
                    for chunk in response.iter_bytes(chunk_size=chunk_size):
                        if not chunk:
                            continue
                        target.write(chunk)
                        progress.update(task_id, advance=len(chunk))


class IteratorReader(io.RawIOBase):
    def __init__(
        self,
        iterator: Iterable[bytes],
        on_chunk: Callable[[int], None] | None = None,
    ) -> None:
        self._iterator: Iterator[bytes] = iter(iterator)
        self._buffer = bytearray()
        self._on_chunk = on_chunk

    def readable(self) -> bool:
        return True

    def readinto(self, target: bytearray) -> int:
        if self.closed:
            return 0
        target_view = memoryview(target)
        requested_size = len(target_view)

        while len(self._buffer) < requested_size:
            try:
                chunk = next(self._iterator)
            except StopIteration:
                break
            if not chunk:
                continue
            if self._on_chunk is not None:
                self._on_chunk(len(chunk))
            self._buffer.extend(chunk)

        output_size = min(requested_size, len(self._buffer))
        if output_size == 0:
            return 0

        target_view[:output_size] = self._buffer[:output_size]
        del self._buffer[:output_size]
        return output_size


def extract_member_guild_id(member_name: str) -> str | None:
    match = re.search(r"(\d+)\.json$", member_name)
    if match is None:
        return None
    return match.group(1)


def transform_message(
    message: dict[str, Any],
    guild_id: str,
    guild_lookup: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    author = message.get("author") or {}
    attachments = message.get("attachments") or []
    embeds = message.get("embeds") or []
    mentions = message.get("mentions") or []
    mention_roles = message.get("mention_roles") or []
    sticker_items = message.get("sticker_items") or []
    reference = message.get("message_reference") or {}
    guild_info = guild_lookup[guild_id]
    content = message.get("content") or ""

    return {
        "guild_id": guild_id,
        "guild_name": as_optional_str(guild_info.get("name")),
        "message_id": as_optional_str(message.get("id")),
        "channel_id": as_optional_str(message.get("channel_id")),
        "channel_name": as_optional_str(message.get("channel_name")),
        "author_id": as_optional_str(author.get("id")),
        "author_username": as_optional_str(author.get("username")),
        "author_discriminator": as_optional_str(author.get("discriminator")),
        "timestamp": as_optional_str(message.get("timestamp")),
        "edited_timestamp": as_optional_str(message.get("edited_timestamp")),
        "message_type": as_int_or_none(message.get("type")),
        "content": content,
        "content_length": len(content),
        "is_bot": bool(message.get("is_bot") or author.get("bot", False)),
        "pinned": bool(message.get("pinned")),
        "mention_everyone": bool(message.get("mention_everyone")),
        "tts": bool(message.get("tts")),
        "flags": as_int_or_none(message.get("flags")),
        "attachment_count": len(attachments),
        "embed_count": len(embeds),
        "mention_count": len(mentions),
        "mention_role_count": len(mention_roles),
        "sticker_count": len(sticker_items),
        "referenced_message_id": as_optional_str(reference.get("message_id")),
        "referenced_guild_id": as_optional_str(reference.get("guild_id")),
        "attachments_json": dump_json(attachments),
        "embeds_json": dump_json(embeds),
        "mentions_json": dump_json(mentions),
        "mention_roles_json": dump_json(mention_roles),
        "sticker_items_json": dump_json(sticker_items),
        "positive_score": as_int_or_none(guild_info.get("positive_score")),
        "matched_positive_terms": as_optional_str(guild_info.get("matched_positive_terms")),
    }


def write_batch(
    rows: list[dict[str, Any]],
    writer: pq.ParquetWriter | None,
    output_path: Path,
) -> pq.ParquetWriter:
    table = pa.Table.from_pylist(rows, schema=MESSAGE_SCHEMA)
    if writer is None:
        ensure_parent(output_path)
        writer = pq.ParquetWriter(output_path, MESSAGE_SCHEMA, compression="zstd")
    writer.write_table(table)
    rows.clear()
    return writer


def prepare_output_parquet(output_parquet: Path) -> None:
    ensure_parent(output_parquet)
    if output_parquet.exists():
        output_parquet.unlink()


def load_selected_servers(selected_servers_path: Path) -> tuple[dict[str, dict[str, Any]], set[str]]:
    selected_servers = pd.read_parquet(selected_servers_path)
    if selected_servers.empty:
        raise typer.BadParameter("O arquivo de servidores selecionados esta vazio.")

    selected_servers["guild_id"] = selected_servers["guild_id"].astype(str)
    guild_lookup = {
        row["guild_id"]: row
        for row in selected_servers[
            ["guild_id", "name", "positive_score", "matched_positive_terms"]
        ].to_dict(orient="records")
    }
    selected_ids = set(guild_lookup)
    return guild_lookup, selected_ids


def process_archive_members(
    archive: tarfile.TarFile,
    selected_ids: set[str],
    guild_lookup: dict[str, dict[str, Any]],
    output_parquet: Path,
    exclude_bots: bool,
    batch_size: int,
    include_channel_patterns: list[re.Pattern[str]],
    exclude_channel_patterns: list[re.Pattern[str]],
    progress: Progress,
    server_task_id: TaskID,
) -> tuple[int, int, int, int]:
    rows: list[dict[str, Any]] = []
    writer: pq.ParquetWriter | None = None
    matched_servers = 0
    matched_messages = 0
    skipped_by_channel = 0
    invalid_json_lines = 0

    try:
        for member in archive:
            if not member.isfile():
                continue
            guild_id = extract_member_guild_id(member.name)
            if guild_id is None or guild_id not in selected_ids:
                continue
            file_handle = archive.extractfile(member)
            if file_handle is None:
                continue

            matched_servers += 1
            progress.update(server_task_id, advance=1, description=f"Lendo {guild_id}")
            for line_number, raw_line in enumerate(file_handle, start=1):
                if not raw_line.strip():
                    continue
                try:
                    message = json.loads(raw_line)
                except json.JSONDecodeError as error:
                    invalid_json_lines += 1
                    if invalid_json_lines <= 3:
                        raw_preview = (
                            raw_line[:180]
                            .decode("utf-8", errors="replace")
                            .replace("\n", "\\n")
                            .replace("\r", "\\r")
                        )
                        console.print(
                            "[yellow]Aviso:[/yellow] mensagem JSON invalida ignorada "
                            f"(guild_id={guild_id}, linha={line_number}): {error}."
                        )
                        console.print(f"[yellow]Preview:[/yellow] {raw_preview}")
                    continue
                channel_name = str(message.get("channel_name") or "")
                if not is_channel_allowed(
                    channel_name,
                    include_channel_patterns,
                    exclude_channel_patterns,
                ):
                    skipped_by_channel += 1
                    continue

                row = transform_message(message, guild_id, guild_lookup)
                if exclude_bots and row["is_bot"]:
                    continue
                rows.append(row)
                matched_messages += 1
                if len(rows) >= batch_size:
                    writer = write_batch(rows, writer, output_parquet)

        if rows:
            writer = write_batch(rows, writer, output_parquet)

        if writer is None:
            console.print("[red]Nenhuma mensagem foi encontrada para os servidores selecionados.[/red]")
            raise typer.Exit(code=1)

        return matched_servers, matched_messages, skipped_by_channel, invalid_json_lines
    finally:
        if writer is not None:
            writer.close()


@app.command("list-profiles")
def list_profiles() -> None:
    table = Table(title="Perfis de filtragem")
    table.add_column("profile")
    table.add_column("default_min_positive_score", justify="right")
    table.add_column("default_min_score_margin", justify="right")
    table.add_column("blocked_negative_terms")

    for profile_name in sorted(FILTER_PROFILES):
        profile_config = FILTER_PROFILES[profile_name]
        blocked_terms = ", ".join(sorted(profile_config["blocked_negative_terms"]))
        table.add_row(
            profile_name,
            str(profile_config["default_min_positive_score"]),
            str(profile_config["default_min_score_margin"]),
            blocked_terms,
        )

    console.print(table)


@app.command("download-metadata")
def download_metadata(
    output_path: Path = typer.Option(
        Path("data/raw/server_metadata/servers_metadata.txt"),
        help="Caminho local para salvar o server_metadata.",
    ),
) -> None:
    stream_hf_file(METADATA_REMOTE_PATH, output_path)
    console.print(f"[green]Metadados salvos em:[/green] {render_path(output_path)}")


@app.command("download-dataset")
def download_dataset(
    output_path: Path = typer.Option(
        Path("data/raw/dataset.zst"),
        help="Caminho local para salvar o dataset.zst completo.",
    ),
) -> None:
    console.print(
        "[yellow]Aviso:[/yellow] o arquivo principal tem cerca de 118 GB e pode levar bastante tempo para baixar."
    )
    stream_hf_file(DATASET_REMOTE_PATH, output_path)
    console.print(f"[green]Dataset salvo em:[/green] {render_path(output_path)}")


@app.command("select-servers")
def select_servers(
    metadata_path: Path = typer.Option(
        Path("data/raw/server_metadata/servers_metadata.txt"),
        exists=True,
        dir_okay=False,
        readable=True,
        help="Arquivo JSON com os metadados dos servidores.",
    ),
    output_parquet: Path = typer.Option(
        Path("data/processed/software_servers.parquet"),
        help="Parquet com os servidores classificados.",
    ),
    output_json: Path = typer.Option(
        Path("data/processed/software_servers.json"),
        help="JSON com os servidores selecionados para revisão manual.",
    ),
    profile: str = typer.Option(
        "software",
        help="Perfil de seleção (software ou gaming).",
    ),
    min_positive_score: int | None = typer.Option(
        None,
        min=1,
        help="Sobrescreve a pontuação mínima positiva do perfil.",
    ),
    min_score_margin: int | None = typer.Option(
        None,
        min=0,
        help="Diferença mínima entre positive_score e negative_score.",
    ),
    positive_regex: list[str] | None = typer.Option(
        None,
        "--positive-regex",
        help="Regex positivo extra (repetivel).",
    ),
    negative_regex: list[str] | None = typer.Option(
        None,
        "--negative-regex",
        help="Regex negativo extra (repetivel).",
    ),
    positive_regex_weight: int = typer.Option(
        2,
        min=1,
        help="Peso aplicado aos regex positivos extras.",
    ),
    negative_regex_weight: int = typer.Option(
        2,
        min=1,
        help="Peso aplicado aos regex negativos extras.",
    ),
) -> None:
    profile_name = normalize_profile_name(profile)
    profile_config = FILTER_PROFILES[profile_name]
    effective_min_positive_score = (
        min_positive_score
        if min_positive_score is not None
        else int(profile_config["default_min_positive_score"])
    )
    effective_min_score_margin = (
        min_score_margin
        if min_score_margin is not None
        else int(profile_config["default_min_score_margin"])
    )

    positive_patterns = list(profile_config["positive_patterns"])
    negative_patterns = list(profile_config["negative_patterns"])
    positive_patterns.extend(
        build_custom_rules(
            positive_regex or [],
            weight=positive_regex_weight,
            label_prefix="custom+",
            option_name="--positive-regex",
        )
    )
    negative_patterns.extend(
        build_custom_rules(
            negative_regex or [],
            weight=negative_regex_weight,
            label_prefix="custom-",
            option_name="--negative-regex",
        )
    )
    blocked_negative_terms = set(profile_config["blocked_negative_terms"])

    metadata = load_metadata(metadata_path)
    classified = [
        classify_server(
            record,
            min_positive_score=effective_min_positive_score,
            positive_patterns=positive_patterns,
            negative_patterns=negative_patterns,
            min_score_margin=effective_min_score_margin,
            blocked_negative_labels=blocked_negative_terms,
        )
        for record in metadata
    ]
    frame = pd.DataFrame(classified)
    selected = frame[frame["is_selected"]].copy()
    selected.sort_values(
        by=["score_margin", "positive_score", "approximate_member_count"],
        ascending=[False, False, False],
        inplace=True,
    )

    ensure_parent(output_parquet)
    selected.to_parquet(output_parquet, index=False)
    ensure_parent(output_json)
    with output_json.open("w", encoding="utf-8") as file_handle:
        json.dump(selected.to_dict(orient="records"), file_handle, ensure_ascii=False, indent=2)

    console.print(f"[green]Perfil:[/green] {profile_name}")
    console.print(
        "[green]Regra de seleção:[/green] "
        f"min_positive_score={effective_min_positive_score}, "
        f"min_score_margin={effective_min_score_margin}"
    )
    console.print(
        f"[green]Servidores selecionados:[/green] {len(selected):,} de {len(frame):,} registros avaliados."
    )
    console.print(f"[green]Parquet:[/green] {render_path(output_parquet)}")
    console.print(f"[green]JSON:[/green] {render_path(output_json)}")
    if not selected.empty:
        show_server_preview(selected)


@app.command("extract-messages")
def extract_messages(
    dataset_path: Path = typer.Option(
        Path("data/raw/dataset.zst"),
        exists=True,
        dir_okay=False,
        readable=True,
        help="Arquivo dataset.zst já baixado localmente.",
    ),
    selected_servers_path: Path = typer.Option(
        Path("data/processed/software_servers.parquet"),
        exists=True,
        dir_okay=False,
        readable=True,
        help="Parquet gerado pelo comando select-servers.",
    ),
    output_parquet: Path = typer.Option(
        Path("data/processed/software_messages.parquet"),
        help="Parquet de saída com as mensagens filtradas.",
    ),
    exclude_bots: bool = typer.Option(
        False,
        help="Quando ativado, remove mensagens enviadas por bots.",
    ),
    batch_size: int = typer.Option(
        50_000,
        min=1_000,
        help="Quantidade de linhas acumuladas antes de gravar um lote no Parquet.",
    ),
    include_channel_regex: list[str] | None = typer.Option(
        None,
        "--include-channel-regex",
        help="Regex de canais para incluir (repetivel).",
    ),
    exclude_channel_regex: list[str] | None = typer.Option(
        None,
        "--exclude-channel-regex",
        help="Regex de canais para excluir (repetivel).",
    ),
) -> None:
    guild_lookup, selected_ids = load_selected_servers(selected_servers_path)
    include_patterns, exclude_patterns = compile_channel_filters(
        include_channel_regex or [],
        exclude_channel_regex or [],
    )
    prepare_output_parquet(output_parquet)

    with dataset_path.open("rb") as compressed_stream:
        with zstd.ZstdDecompressor().stream_reader(compressed_stream) as zstd_stream:
            with tarfile.open(fileobj=zstd_stream, mode="r|") as archive:
                progress = Progress(
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(),
                    TaskProgressColumn(),
                    TimeElapsedColumn(),
                    console=console,
                )
                with progress:
                    task_id = progress.add_task("Processando servidores", total=len(selected_ids))
                    (
                        matched_servers,
                        matched_messages,
                        skipped_by_channel,
                        invalid_json_lines,
                    ) = process_archive_members(
                        archive=archive,
                        selected_ids=selected_ids,
                        guild_lookup=guild_lookup,
                        output_parquet=output_parquet,
                        exclude_bots=exclude_bots,
                        batch_size=batch_size,
                        include_channel_patterns=include_patterns,
                        exclude_channel_patterns=exclude_patterns,
                        progress=progress,
                        server_task_id=task_id,
                    )

    if include_patterns or exclude_patterns:
        console.print(f"[green]Mensagens removidas por filtro de canais:[/green] {skipped_by_channel:,}")
    if invalid_json_lines > 0:
        console.print(
            "[yellow]Mensagens ignoradas por JSON invalido:[/yellow] "
            f"{invalid_json_lines:,}"
        )

    console.print(f"[green]Servidores processados:[/green] {matched_servers:,}")
    console.print(f"[green]Mensagens gravadas:[/green] {matched_messages:,}")
    console.print(f"[green]Parquet:[/green] {render_path(output_parquet)}")


@app.command("extract-messages-remote")
def extract_messages_remote(
    selected_servers_path: Path = typer.Option(
        Path("data/processed/software_servers.parquet"),
        exists=True,
        dir_okay=False,
        readable=True,
        help="Parquet gerado pelo comando select-servers.",
    ),
    output_parquet: Path = typer.Option(
        Path("data/processed/software_messages.parquet"),
        help="Parquet de saída com as mensagens filtradas.",
    ),
    remote_path: str = typer.Option(
        DATASET_REMOTE_PATH,
        help="Caminho remoto no dataset do Hugging Face.",
    ),
    exclude_bots: bool = typer.Option(
        False,
        help="Quando ativado, remove mensagens enviadas por bots.",
    ),
    batch_size: int = typer.Option(
        50_000,
        min=1_000,
        help="Quantidade de linhas acumuladas antes de gravar um lote no Parquet.",
    ),
    download_chunk_mb: int = typer.Option(
        8,
        min=1,
        max=64,
        help="Tamanho (MB) dos chunks lidos durante o streaming remoto.",
    ),
    include_channel_regex: list[str] | None = typer.Option(
        None,
        "--include-channel-regex",
        help="Regex de canais para incluir (repetivel).",
    ),
    exclude_channel_regex: list[str] | None = typer.Option(
        None,
        "--exclude-channel-regex",
        help="Regex de canais para excluir (repetivel).",
    ),
) -> None:
    guild_lookup, selected_ids = load_selected_servers(selected_servers_path)
    include_patterns, exclude_patterns = compile_channel_filters(
        include_channel_regex or [],
        exclude_channel_regex or [],
    )
    prepare_output_parquet(output_parquet)

    url = build_hf_url(remote_path)
    chunk_size = download_chunk_mb * 1024 * 1024
    timeout = httpx.Timeout(connect=60.0, read=60.0, write=60.0, pool=60.0)

    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            total_bytes: int | None = None
            content_length = response.headers.get("content-length")
            if content_length:
                total_bytes = int(content_length)

            progress = Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                DownloadColumn(binary_units=True),
                TransferSpeedColumn(),
                TimeElapsedColumn(),
                console=console,
            )
            with progress:
                download_task_id = progress.add_task(
                    "Baixando e descompactando dataset remoto",
                    total=total_bytes,
                )
                server_task_id = progress.add_task("Processando servidores", total=len(selected_ids))

                stream_reader = IteratorReader(
                    response.iter_bytes(chunk_size=chunk_size),
                    on_chunk=lambda size: progress.update(download_task_id, advance=size),
                )
                with zstd.ZstdDecompressor().stream_reader(stream_reader) as zstd_stream:
                    with tarfile.open(fileobj=zstd_stream, mode="r|") as archive:
                        (
                            matched_servers,
                            matched_messages,
                            skipped_by_channel,
                            invalid_json_lines,
                        ) = process_archive_members(
                            archive=archive,
                            selected_ids=selected_ids,
                            guild_lookup=guild_lookup,
                            output_parquet=output_parquet,
                            exclude_bots=exclude_bots,
                            batch_size=batch_size,
                            include_channel_patterns=include_patterns,
                            exclude_channel_patterns=exclude_patterns,
                            progress=progress,
                            server_task_id=server_task_id,
                        )

    console.print(
        "[green]Processamento remoto concluido sem salvar o dataset.zst inteiro localmente.[/green]"
    )
    if include_patterns or exclude_patterns:
        console.print(f"[green]Mensagens removidas por filtro de canais:[/green] {skipped_by_channel:,}")
    if invalid_json_lines > 0:
        console.print(
            "[yellow]Mensagens ignoradas por JSON invalido:[/yellow] "
            f"{invalid_json_lines:,}"
        )

    console.print(f"[green]Servidores processados:[/green] {matched_servers:,}")
    console.print(f"[green]Mensagens gravadas:[/green] {matched_messages:,}")
    console.print(f"[green]Parquet:[/green] {render_path(output_parquet)}")


@app.command("init-duckdb")
def init_duckdb(
    messages_parquet: Path = typer.Option(
        Path("data/processed/software_messages.parquet"),
        exists=True,
        dir_okay=False,
        readable=True,
        help="Parquet com as mensagens filtradas.",
    ),
    servers_parquet: Path = typer.Option(
        Path("data/processed/software_servers.parquet"),
        exists=True,
        dir_okay=False,
        readable=True,
        help="Parquet com os servidores selecionados.",
    ),
    database_path: Path = typer.Option(
        Path("data/duckdb/discord_unveiled.duckdb"),
        help="Arquivo DuckDB a ser criado.",
    ),
) -> None:
    ensure_parent(database_path)
    if database_path.exists():
        database_path.unlink()

    conn = duckdb.connect(str(database_path))
    messages_path = str(messages_parquet.resolve()).replace("\\", "/")
    servers_path = str(servers_parquet.resolve()).replace("\\", "/")
    conn.execute(
        f"CREATE OR REPLACE VIEW software_servers AS SELECT * FROM read_parquet('{servers_path}')"
    )
    conn.execute(
        f"CREATE OR REPLACE VIEW software_messages AS SELECT * FROM read_parquet('{messages_path}')"
    )
    conn.execute(
        """
        CREATE OR REPLACE VIEW server_message_stats AS
        SELECT
            guild_id,
            guild_name,
            COUNT(*) AS message_count,
            COUNT(DISTINCT author_id) AS unique_authors,
            MIN(timestamp) AS first_message_at,
            MAX(timestamp) AS last_message_at
        FROM software_messages
        GROUP BY 1, 2
        ORDER BY message_count DESC
        """
    )
    conn.close()

    console.print(f"[green]DuckDB criado em:[/green] {render_path(database_path)}")
    console.print("[green]Views disponíveis:[/green] software_servers, software_messages, server_message_stats")


def run() -> None:
    app()


if __name__ == "__main__":
    run()
