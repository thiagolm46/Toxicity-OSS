from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

from discord_disentanglement.approaches import APPROACH_IDS
from discord_disentanglement.gold_standard import export_native_reply_gold_standard

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
        )
        print(result.conversations_path)
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
