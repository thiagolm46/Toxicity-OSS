from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from discord_disentanglement.approaches import APPROACH_IDS
from discord_disentanglement.annotation_bundle import (
    build_annotation_bundle,
    materialize_annotation_tables,
    publish_annotation_dataset,
)
from discord_disentanglement.gold_standard import export_native_reply_gold_standard
from discord_disentanglement.human_annotations import materialize_human_reply_components

from .config import ExperimentConfig
from .runner import run_all, run_experiment


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Experimentos comparaveis de disentanglement no servidor Neo4j."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    gold_standard = subparsers.add_parser(
        "gold-standard",
        help="Exporta conversas ancoradas em direct_reply nativo do Discord.",
    )
    gold_standard.add_argument("--input", type=Path, required=True)
    gold_standard.add_argument("--output", type=Path, required=True)
    gold_standard.add_argument("--guild-id", default="787399249741479977")
    gold_standard.add_argument("--guild-name")
    gold_standard.add_argument("--channel-id")
    gold_standard.add_argument("--channel-name")
    gold_standard.add_argument(
        "--annotated-window-size",
        type=int,
        default=100,
        help="Mensagens contiguas por janela anotada no piloto (padrao: 100).",
    )
    gold_standard.add_argument(
        "--context-message-count",
        type=int,
        default=200,
        help="Mensagens anteriores exibidas como contexto no piloto (padrao: 200).",
    )
    human_components = subparsers.add_parser(
        "derive-human-components",
        help="Valida arestas humanas e deriva conversation_id por componentes conexos.",
    )
    human_components.add_argument("--annotation-windows", type=Path, required=True)
    human_components.add_argument("--output", type=Path, required=True)
    annotation_bundle = subparsers.add_parser(
        "build-annotation-bundle",
        help="Achata janelas em mensagens, arestas humanas e estados de fonte Parquet.",
    )
    annotation_bundle.add_argument("--annotation-windows", type=Path, required=True)
    annotation_bundle.add_argument("--output", type=Path, required=True)
    table_components = subparsers.add_parser(
        "derive-annotation-components",
        help="Valida tabelas humanas e deriva conversation_id por componentes conexos.",
    )
    table_components.add_argument("--messages", type=Path, required=True)
    table_components.add_argument("--sample-messages", type=Path, required=True)
    table_components.add_argument("--annotations", type=Path, required=True)
    table_components.add_argument("--source-statuses", type=Path, required=True)
    table_components.add_argument("--output", type=Path, required=True)
    table_components.add_argument("--include-ambiguous", action="store_true")
    publish_dataset = subparsers.add_parser(
        "publish-annotation-dataset",
        help="Publica somente as tabelas e regras necessarias para anotacao humana.",
    )
    publish_dataset.add_argument("--bundle-dir", type=Path, required=True)
    publish_dataset.add_argument("--native-reply-edges", type=Path, required=True)
    publish_dataset.add_argument("--codebook", type=Path, required=True)
    publish_dataset.add_argument("--output", type=Path, required=True)
    for command in ("run", "all"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--input", type=Path)
        subparser.add_argument("--output", type=Path)
        subparser.add_argument("--config", type=Path)
        subparser.add_argument(
            "--overwrite",
            action="store_true",
            help="Permite substituir somente os artefatos conhecidos da execucao.",
        )
        if command == "run":
            subparser.add_argument("--approach", choices=APPROACH_IDS, required=True)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == "gold-standard":
        result = export_native_reply_gold_standard(
            args.input,
            args.output,
            guild_id=args.guild_id,
            guild_name=args.guild_name,
            channel_id=args.channel_id,
            channel_name=args.channel_name,
            annotated_window_size=args.annotated_window_size,
            context_message_count=args.context_message_count,
        )
        print(result.annotation_windows_path)
        return 0
    if args.command == "derive-human-components":
        result = materialize_human_reply_components(
            args.annotation_windows,
            args.output,
        )
        print(result.human_components_path)
        return 0
    if args.command == "build-annotation-bundle":
        result = build_annotation_bundle(args.annotation_windows, args.output)
        print(result.messages_path)
        return 0
    if args.command == "derive-annotation-components":
        result = materialize_annotation_tables(
            args.messages,
            args.sample_messages,
            args.annotations,
            args.source_statuses,
            args.output,
            include_ambiguous=args.include_ambiguous,
        )
        print(result.components_path)
        return 0
    if args.command == "publish-annotation-dataset":
        result = publish_annotation_dataset(
            args.bundle_dir,
            args.native_reply_edges,
            args.codebook,
            args.output,
        )
        print(result.manifest_path)
        return 0
    if args.config:
        config = ExperimentConfig.from_json(
            args.config,
            input_path=args.input,
            output_dir=args.output,
        )
    else:
        if args.input is None or args.output is None:
            raise SystemExit("Informe --input e --output, ou use --config.")
        config = ExperimentConfig(input_path=args.input, output_dir=args.output)
    if args.overwrite and not config.overwrite:
        config = replace(config, overwrite=True)
    if args.command == "run":
        result = run_experiment(config, args.approach)
        print(result.run_dir)
    else:
        result = run_all(config)
        print(result.comparison_markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
