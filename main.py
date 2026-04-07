from __future__ import annotations

import json
import re
import tarfile
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

POSITIVE_PATTERNS: list[tuple[re.Pattern[str], int, str]] = [
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

NEGATIVE_PATTERNS: list[tuple[re.Pattern[str], int, str]] = [
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


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def dump_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def render_path(path: Path) -> str:
    return str(path.resolve())


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
    patterns: list[tuple[re.Pattern[str], int, str]],
) -> tuple[int, list[str]]:
    score = 0
    matches: list[str] = []
    for pattern, weight, label in patterns:
        if pattern.search(text):
            score += weight
            matches.append(label)
    return score, matches


def classify_server(record: dict[str, Any], min_positive_score: int) -> dict[str, Any]:
    text = build_search_text(record)
    positive_score, positive_terms = score_text(text, POSITIVE_PATTERNS)
    negative_score, negative_terms = score_text(text, NEGATIVE_PATTERNS)
    is_selected = positive_score >= min_positive_score and positive_score > negative_score
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
        "matched_positive_terms": dump_json(positive_terms),
        "matched_negative_terms": dump_json(negative_terms),
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
    table.add_column("matched_positive_terms")

    for row in preview.itertuples(index=False):
        table.add_row(
            str(row.guild_id),
            str(row.name or ""),
            str(row.positive_score),
            str(row.negative_score),
            str(row.matched_positive_terms),
        )

    console.print(table)


def stream_hf_file(remote_path: str, output_path: Path, chunk_size: int = 8 * 1024 * 1024) -> None:
    ensure_parent(output_path)
    url = f"https://huggingface.co/datasets/{REPO_ID}/resolve/main/{remote_path}?download=true"
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
        "guild_name": guild_info.get("name"),
        "message_id": message.get("id"),
        "channel_id": message.get("channel_id"),
        "channel_name": message.get("channel_name"),
        "author_id": author.get("id"),
        "author_username": author.get("username"),
        "author_discriminator": author.get("discriminator"),
        "timestamp": message.get("timestamp"),
        "edited_timestamp": message.get("edited_timestamp"),
        "message_type": message.get("type"),
        "content": content,
        "content_length": len(content),
        "is_bot": bool(message.get("is_bot") or author.get("bot", False)),
        "pinned": bool(message.get("pinned")),
        "mention_everyone": bool(message.get("mention_everyone")),
        "tts": bool(message.get("tts")),
        "flags": message.get("flags"),
        "attachment_count": len(attachments),
        "embed_count": len(embeds),
        "mention_count": len(mentions),
        "mention_role_count": len(mention_roles),
        "sticker_count": len(sticker_items),
        "referenced_message_id": reference.get("message_id"),
        "referenced_guild_id": reference.get("guild_id"),
        "attachments_json": dump_json(attachments),
        "embeds_json": dump_json(embeds),
        "mentions_json": dump_json(mentions),
        "mention_roles_json": dump_json(mention_roles),
        "sticker_items_json": dump_json(sticker_items),
        "positive_score": guild_info.get("positive_score"),
        "matched_positive_terms": guild_info.get("matched_positive_terms"),
    }


def write_batch(
    rows: list[dict[str, Any]],
    writer: pq.ParquetWriter | None,
    output_path: Path,
) -> pq.ParquetWriter:
    table = pa.Table.from_pylist(rows)
    if writer is None:
        ensure_parent(output_path)
        writer = pq.ParquetWriter(output_path, table.schema, compression="zstd")
    writer.write_table(table)
    rows.clear()
    return writer


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
    min_positive_score: int = typer.Option(
        4,
        min=1,
        help="Pontuação mínima positiva para um servidor ser selecionado.",
    ),
) -> None:
    metadata = load_metadata(metadata_path)
    classified = [classify_server(record, min_positive_score) for record in metadata]
    frame = pd.DataFrame(classified)
    selected = frame[frame["is_selected"]].copy()
    selected.sort_values(
        by=["positive_score", "approximate_member_count"],
        ascending=[False, False],
        inplace=True,
    )

    ensure_parent(output_parquet)
    selected.to_parquet(output_parquet, index=False)
    ensure_parent(output_json)
    with output_json.open("w", encoding="utf-8") as file_handle:
        json.dump(selected.to_dict(orient="records"), file_handle, ensure_ascii=False, indent=2)

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
) -> None:
    selected_servers = pd.read_parquet(selected_servers_path)
    selected_servers["guild_id"] = selected_servers["guild_id"].astype(str)
    guild_lookup = {
        row["guild_id"]: row
        for row in selected_servers[
            ["guild_id", "name", "positive_score", "matched_positive_terms"]
        ].to_dict(orient="records")
    }
    selected_ids = set(guild_lookup)

    rows: list[dict[str, Any]] = []
    writer: pq.ParquetWriter | None = None
    matched_servers = 0
    matched_messages = 0

    ensure_parent(output_parquet)
    if output_parquet.exists():
        output_parquet.unlink()

    with dataset_path.open("rb") as compressed_stream:
        zstd_stream = zstd.ZstdDecompressor().stream_reader(compressed_stream)
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
                    progress.update(task_id, advance=1, description=f"Lendo {guild_id}")
                    for raw_line in file_handle:
                        if not raw_line.strip():
                            continue
                        message = json.loads(raw_line)
                        row = transform_message(message, guild_id, guild_lookup)
                        if exclude_bots and row["is_bot"]:
                            continue
                        rows.append(row)
                        matched_messages += 1
                        if len(rows) >= batch_size:
                            writer = write_batch(rows, writer, output_parquet)

    if rows:
        writer = write_batch(rows, writer, output_parquet)
    if writer is not None:
        writer.close()
    else:
        console.print("[red]Nenhuma mensagem foi encontrada para os servidores selecionados.[/red]")
        raise typer.Exit(
            code=1,
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
