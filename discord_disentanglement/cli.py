from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

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
    config_path: Path | None = typer.Option(
        None,
        "--config",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Arquivo YAML de configuracao. A v2 inclui configs/disentanglement_default.yaml.",
    ),
    use_embeddings: bool = typer.Option(
        True,
        "--use-embeddings/--no-embeddings",
        help="Tentar usar sentence-transformers; se indisponivel, cair para TF-IDF.",
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
    generate_report: bool = typer.Option(
        True,
        "--generate-report/--no-generate-report",
        help="Gerar HTML estatico de inspecao.",
    ),
) -> None:
    settings = _load_config(config_path) if config_path else {}
    if config_path:
        console.print(f"[cyan]Configuracao informada:[/cyan] {config_path}")
    embedding_settings = settings.get("embeddings", {})
    candidate_settings = settings.get("candidate_generation", {})
    link_settings = settings.get("link_scoring", {})
    evaluation_settings = settings.get("evaluation", {})
    interface_settings = settings.get("interface", {})
    neo4j_settings = settings.get("neo4j_export", {})

    configured_threshold = (
        threshold
        if threshold != 0.50
        else float(link_settings.get("threshold", threshold))
    )
    uncertain_margin = link_settings.get("uncertain_margin")
    configured_uncertain_threshold = (
        uncertain_threshold
        if uncertain_threshold != 0.60
        else (
        min(1.0, configured_threshold + float(uncertain_margin))
        if uncertain_margin is not None
        else uncertain_threshold
        )
    )
    configured_previous_window = int(
        previous_message_window
        if previous_message_window != 50
        else candidate_settings.get("max_previous_messages", previous_message_window)
    )
    configured_time_window_hours = (
        time_window_hours
        if time_window_hours != 24.0
        else (
        float(candidate_settings.get("max_time_delta_minutes")) / 60.0
        if candidate_settings.get("max_time_delta_minutes") is not None
        else time_window_hours
        )
    )
    configured_export_neo4j = export_neo4j and bool(neo4j_settings.get("enabled", True))
    configured_generate_report = generate_report and bool(interface_settings.get("generate_overview", True))
    configured_use_embeddings = bool(embedding_settings.get("enabled", use_embeddings)) and use_embeddings

    config = DisentanglementConfig(
        input_path=input_path,
        out_dir=out_dir,
        guild_name=guild_name,
        guild_id=guild_id,
        channel_name=channel_name or None,
        channel_id=channel_id,
        threshold=configured_threshold,
        uncertain_threshold=configured_uncertain_threshold,
        previous_message_window=configured_previous_window,
        time_window_hours=configured_time_window_hours,
        max_candidates_per_message=int(
            candidate_settings.get(
                "max_candidates_per_message",
                DisentanglementConfig.max_candidates_per_message,
            )
        ),
        preserve_raw_content=preserve_raw_content,
        export_neo4j=configured_export_neo4j,
        use_embeddings=configured_use_embeddings,
        embedding_model_name=str(
            embedding_settings.get(
                "model_name",
                DisentanglementConfig.embedding_model_name,
            )
        ),
        embedding_batch_size=int(
            embedding_settings.get(
                "batch_size",
                DisentanglementConfig.embedding_batch_size,
            )
        ),
        embedding_min_batch_size=int(
            embedding_settings.get(
                "min_batch_size",
                DisentanglementConfig.embedding_min_batch_size,
            )
        ),
        embedding_max_seq_length=(
            int(embedding_settings["max_seq_length"])
            if embedding_settings.get("max_seq_length") is not None
            else None
        ),
        embedding_device=str(
            embedding_settings.get(
                "device",
                DisentanglementConfig.embedding_device,
            )
        ),
        embedding_precision=str(
            embedding_settings.get(
                "precision",
                DisentanglementConfig.embedding_precision,
            )
        ),
        generate_report=configured_generate_report,
        evaluation_thresholds=tuple(
            float(value)
            for value in evaluation_settings.get(
                "thresholds",
                DisentanglementConfig.evaluation_thresholds,
            )
        ),
    )
    outputs = run_pipeline(config)
    console.print("[green]Disentanglement concluido.[/green]")
    for label, path in outputs.items():
        if path.exists():
            console.print(f"[green]{label}:[/green] {path}")


@app.command("validate")
def validate(input_path: Path = typer.Option(..., "--input", exists=True, dir_okay=False)) -> None:
    """Valida se um arquivo de entrada existe e pode ser lido pelo pipeline."""
    from .io import load_discord_export

    rows = load_discord_export(input_path)
    console.print(f"[green]Arquivo valido.[/green] Linhas normalizadas: {len(rows)}")


@app.command("embed")
def embed(
    input_path: Path = typer.Option(..., "--input", exists=True, dir_okay=False),
    out_dir: Path = typer.Option(Path("data/processed/neo4j_threads"), "--out"),
    no_embeddings: bool = typer.Option(False, "--no-embeddings"),
) -> None:
    """Gera artefatos de embeddings ou metadados de fallback TF-IDF."""
    from .embeddings import build_message_embeddings
    from .io import load_discord_export
    from .pipeline import normalize_messages

    rows = load_discord_export(input_path)
    messages = normalize_messages(rows, None, None, None, None, preserve_raw_content=False)
    result = build_message_embeddings(messages, out_dir, enabled=not no_embeddings)
    console.print(f"[green]Embeddings finalizados.[/green] provider={result.provider} fallback={result.used_fallback}")


@app.command("evaluate")
def evaluate(out_dir: Path = typer.Option(Path("data/processed/neo4j_threads"), "--out")) -> None:
    """Mostra os caminhos das metricas geradas pelo comando run."""
    metrics = out_dir / "reports" / "metrics" / "disentanglement_metrics.json"
    if not metrics.exists():
        raise typer.BadParameter(f"Metricas nao encontradas: {metrics}. Execute run primeiro.")
    console.print(metrics.read_text(encoding="utf-8"))


@app.command("export-neo4j")
def export_neo4j(out_dir: Path = typer.Option(Path("data/processed/neo4j_threads"), "--out")) -> None:
    """Lista os artefatos Neo4j gerados pelo comando run."""
    exports_dir = out_dir / "exports"
    if not exports_dir.exists():
        raise typer.BadParameter(f"Diretorio de exports nao encontrado: {exports_dir}. Execute run primeiro.")
    for path in sorted(exports_dir.glob("neo4j*")):
        console.print(path)


def main() -> None:
    app()


def _load_config(path: Path) -> dict[str, Any]:
    try:
        import yaml

        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
        return loaded if isinstance(loaded, dict) else {}
    except ModuleNotFoundError:
        return _parse_simple_yaml(path.read_text(encoding="utf-8"))


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        if ":" not in stripped:
            continue
        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        while indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if not value:
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
        else:
            parent[key] = _parse_scalar(value)
    return root


def _parse_scalar(value: str) -> Any:
    lowered = value.casefold()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    if value.startswith("[") and value.endswith("]"):
        try:
            return ast.literal_eval(value)
        except (SyntaxError, ValueError):
            inner = value[1:-1].strip()
            return [item.strip() for item in inner.split(",") if item.strip()]
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value.strip("\"'")
