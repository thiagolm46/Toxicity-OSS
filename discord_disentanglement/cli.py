from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .pipeline import DisentanglementConfig, run_pipeline

app = typer.Typer(
    add_completion=False,
    help="Conversation disentanglement para exports JSON/CSV/Parquet de mensagens Discord.",
)
console = Console()


@app.callback()
def callback() -> None:
    """Pipeline de conversation disentanglement para Discord."""


@app.command("run")
def run(
    input_path: Path = typer.Option(
        ...,
        "--input",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Arquivo JSON, CSV ou Parquet com mensagens do Discord.",
    ),
    guild_name: str | None = typer.Option(
        None,
        "--guild-name",
        help="Nome do servidor/guild a processar, por exemplo Neo4j.",
    ),
    guild_id: str | None = typer.Option(
        None,
        "--guild-id",
        help="ID do servidor/guild a processar.",
    ),
    channel_name: str | None = typer.Option(
        None,
        "--channel-name",
        help="Nome do canal a processar. Se omitido, processa todos os canais do escopo.",
    ),
    channel_id: str | None = typer.Option(
        None,
        "--channel-id",
        help="ID do canal a processar.",
    ),
    out_dir: Path = typer.Option(
        Path("data/processed/neo4j_threads"),
        "--out",
        help="Diretorio de saida.",
    ),
    threshold: float = typer.Option(
        0.50,
        "--threshold",
        min=0.0,
        max=1.0,
        help="Threshold minimo para link inferido.",
    ),
    uncertain_threshold: float = typer.Option(
        0.60,
        "--uncertain-threshold",
        min=0.0,
        max=1.0,
        help="Abaixo deste score, links aceitos sao marcados como uncertain.",
    ),
    previous_message_window: int = typer.Option(
        50,
        "--previous-message-window",
        min=1,
        help="Quantidade de mensagens anteriores sempre consideradas.",
    ),
    time_window_hours: float = typer.Option(
        24.0,
        "--time-window-hours",
        min=0.1,
        help="Janela temporal para candidatos anteriores.",
    ),
    preserve_raw_content: bool = typer.Option(
        False,
        "--preserve-raw-content/--drop-raw-content",
        help="Salvar content_raw nos CSVs. Por padrao, o raw nao e exportado.",
    ),
    export_neo4j: bool = typer.Option(
        True,
        "--export-neo4j/--no-export-neo4j",
        help="Gerar CSVs e exports/neo4j_import.cypher para importar o grafo no Neo4j.",
    ),
) -> None:
    config = DisentanglementConfig(
        input_path=input_path,
        out_dir=out_dir,
        guild_name=guild_name,
        guild_id=guild_id,
        channel_name=channel_name or None,
        channel_id=channel_id,
        threshold=threshold,
        uncertain_threshold=uncertain_threshold,
        previous_message_window=previous_message_window,
        time_window_hours=time_window_hours,
        preserve_raw_content=preserve_raw_content,
        export_neo4j=export_neo4j,
    )
    outputs = run_pipeline(config)
    console.print("[green]Disentanglement concluido.[/green]")
    for label, path in outputs.items():
        if path.exists():
            console.print(f"[green]{label}:[/green] {path}")


def main() -> None:
    app()
