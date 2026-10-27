import json
import os
import tempfile
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from discord_filtering.channel_selection import channel_decisions
from discord_filtering.storage import atomic_write_bytes, sha256_file


DATA_DIR = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "processed"
    / "filtering"
    / "software"
    / "affinity_v2"
)
STATISTICS_PATH = DATA_DIR / "channel_statistics_2026-09-21.parquet"
EXCLUSION_PATH = DATA_DIR / "canais_a_excluir.txt"
MESSAGES_PATH = DATA_DIR / "messages_2026-09-21.parquet"
OUTPUT_PATH = DATA_DIR / "messages_2026-10-07_excluded_channels_min500_interacting5.parquet"
OUTPUT_MANIFEST_PATH = OUTPUT_PATH.with_name(f"{OUTPUT_PATH.name}.manifest.json")
BATCH_SIZE = 100_000
MIN_MESSAGES = 500
MIN_INTERACTING_AUTHORS = 5


def filter_messages(excluded_channel_ids: set[str]) -> tuple[int, int]:
    if OUTPUT_PATH.exists() or OUTPUT_MANIFEST_PATH.exists():
        raise FileExistsError(
            f"output already exists: {OUTPUT_PATH}; move it before running again"
        )

    source = pq.ParquetFile(MESSAGES_PATH)
    if "channel_id" not in source.schema_arrow.names:
        raise ValueError(f"{MESSAGES_PATH} does not contain a channel_id column")

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{OUTPUT_PATH.name}.", suffix=".tmp", dir=OUTPUT_PATH.parent
    )
    os.close(descriptor)
    temporary_path = Path(temporary_name)
    removed_rows = 0
    try:
        channel_ids = pa.array(sorted(excluded_channel_ids), type=pa.string())
        with pq.ParquetWriter(
            temporary_path, source.schema_arrow, compression="zstd"
        ) as writer:
            for batch in source.iter_batches(batch_size=BATCH_SIZE):
                belongs_to_excluded_channel = pc.is_in(
                    batch.column("channel_id"), value_set=channel_ids
                )
                kept_batch = pc.filter(batch, pc.invert(belongs_to_excluded_channel))
                removed_rows += batch.num_rows - kept_batch.num_rows
                if kept_batch.num_rows:
                    writer.write_batch(kept_batch)

        try:
            os.link(temporary_path, OUTPUT_PATH)
        except FileExistsError as error:
            raise FileExistsError(f"output already exists: {OUTPUT_PATH}") from error

        output_rows = source.metadata.num_rows - removed_rows
        manifest = {
            "manifest_schema_version": 1,
            "command": "remove-excluded-channels",
            "inputs": [
                {
                    "path": str(MESSAGES_PATH.resolve()),
                    "sha256": sha256_file(MESSAGES_PATH),
                    "immutable_source": True,
                },
                {
                    "path": str(STATISTICS_PATH.resolve()),
                    "sha256": sha256_file(STATISTICS_PATH),
                    "immutable_source": True,
                },
                {
                    "path": str(EXCLUSION_PATH.resolve()),
                    "sha256": sha256_file(EXCLUSION_PATH),
                    "immutable_source": True,
                },
            ],
            "parameters": {
                "excluded_channel_id_count": len(excluded_channel_ids),
                "batch_size": BATCH_SIZE,
                "minimum_messages": MIN_MESSAGES,
                "minimum_interacting_authors": MIN_INTERACTING_AUTHORS,
                "low_activity_condition": "total_messages < minimum_messages AND interacting_authors < minimum_interacting_authors",
            },
            "counts": {
                "source_messages": source.metadata.num_rows,
                "removed_messages": removed_rows,
                "remaining_messages": output_rows,
            },
            "source_data_policy": "read_only_immutable",
            "reproducibility_scope": "decision replay from frozen statistics; historical interacting_authors predicate unrecovered",
            "output": {
                "path": str(OUTPUT_PATH.resolve()),
                "format": "parquet",
                "row_count": output_rows,
                "sha256": sha256_file(OUTPUT_PATH),
            },
        }
        atomic_write_bytes(
            OUTPUT_MANIFEST_PATH,
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8") + b"\n",
        )
        return removed_rows, output_rows
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> None:
    excluded_names = {
        line.strip()
        for line in EXCLUSION_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    statistics = channel_decisions(
        pd.read_parquet(STATISTICS_PATH),
        excluded_names,
        minimum_messages=MIN_MESSAGES,
        minimum_interacting_authors=MIN_INTERACTING_AUTHORS,
    )
    manual_exclusion_mask = statistics["manual_excluded"]
    low_activity_mask = statistics["low_activity_excluded"]
    excluded_mask = manual_exclusion_mask | low_activity_mask
    excluded = statistics.loc[excluded_mask]
    remaining = statistics.loc[~excluded_mask]
    unmatched_names = sorted(excluded_names - set(statistics["channel_name"]))
    excluded_channel_ids = set(excluded["channel_id"].astype(str))
    overlap_count = int((manual_exclusion_mask & low_activity_mask).sum())

    print("Execucao historica: interacting_authors usa valores congelados; a reconstrucao compativel e verificada separadamente por interaction_audit.")
    print(f"Canais antes: {len(statistics)}")
    print(f"Removidos pela lista: {int(manual_exclusion_mask.sum())}")
    print(f"Removidos pelos limites de atividade: {int(low_activity_mask.sum())}")
    print(f"Presentes nos dois critérios: {overlap_count}")
    print(f"Total de canais removidos: {len(excluded)}")
    print(f"Canais restantes: {len(remaining)}")
    print("\nCanais removidos:")
    print(
        excluded[
            [
                "guild_name",
                "channel_name",
                "channel_id",
                "total_messages",
                "interacting_authors",
            ]
        ].to_string(index=False)
    )
    print("\nNomes da lista sem correspondência:")
    print("\n".join(unmatched_names) if unmatched_names else "Nenhum")
    print("\nEstatísticas dos canais restantes:")
    print(remaining.describe().to_string())

    removed_messages, remaining_messages = filter_messages(excluded_channel_ids)
    print(f"\nMensagens na origem: {pq.ParquetFile(MESSAGES_PATH).metadata.num_rows}")
    print(f"Mensagens removidas: {removed_messages}")
    print(f"Mensagens restantes: {remaining_messages}")
    print(f"Parquet filtrado: {OUTPUT_PATH}")
    print(f"Manifesto: {OUTPUT_MANIFEST_PATH}")


if __name__ == "__main__":
    main()