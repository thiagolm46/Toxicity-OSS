from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

import duckdb
import pandas as pd

from discord_filtering.channel_selection import channel_decisions, verify_historical_selection
from discord_filtering.storage import atomic_write_bytes, sha256_file


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BUNDLE = ROOT / "annotations/channel_selection_2026-10-07"
DEFAULT_SOURCE = ROOT / "data/processed/filtering/software/affinity_v2/messages_2026-09-21.parquet"
DEFAULT_OUTPUT = ROOT / "data/processed/filtering/software/interaction_audit_v1"
DEFAULT_REPORT = ROOT / "docs/methodology/INTERACTING_AUTHORS_AUDIT.md"
CANDIDATES = {
    "human_authors": "distinct nonempty author_id with is_bot=false",
    "reply_senders": "distinct human source authors with nonempty referenced_message_id, whether resolved or not and regardless of message type",
    "mention_senders": "distinct human source authors with mention_count>0, including self/bot mentions if present",
    "reply_or_mention_senders": "distinct human source authors with referenced_message_id or mention_count>0; no semantic reply inference",
    "resolved_reply_senders": "distinct human source authors referencing a unique preceding human message in the same guild/channel; self replies allowed",
    "resolved_reply_or_mention_senders": "resolved_reply_senders union mention_senders; counts source authors, not recipients",
    "other_author_reply_or_mention_senders": "human authors replying to a unique preceding human message by another author in the same guild/channel, or with mention_count>0",
}


def write_audit_report(output: str | Path, report: str | Path, *, overwrite: bool = False) -> Path:
    output, report = Path(output).resolve(), Path(report).resolve()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    for item in manifest["outputs"]:
        if sha256_file(output / item["name"]) != item["sha256"]:
            raise ValueError(f"audit output hash mismatch: {item['name']}")
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    rows = summary["candidate_results"]
    lines = [
        "# Auditoria de interacting_authors",
        "## Explicacao concisa",
        "A hipotese principal e: quantidade de autores humanos distintos que, no canal, enviaram pelo menos uma referencia de resposta a uma mensagem humana anterior presente no mesmo canal/export, ou uma mensagem com `mention_count > 0`. Cada autor e contado uma unica vez. Conta emissores, nao destinatarios apenas por receberem resposta ou mencao. Nao mede conversas semanticas.",
    ]
    principal = next(row for row in rows if row["candidate"] == "resolved_reply_or_mention_senders")
    lines += [
        f"Resultado observado dessa hipotese: **{principal['matching_channels']} de {principal['total_channels']} canais coincidentes**, {principal['different_channels']} divergencias e {principal['changed_final_decisions']} decisoes finais alteradas. A comparacao cobre todos os canais da fonte historica, incluindo os excluidos.",
        "## O que foi recuperado",
        f"Foram comparadas {len(rows)} definicoes explicitas. Candidatas com igualdade em todos os canais: {', '.join('`' + name + '`' for name in summary['exactly_matching_candidates']) or 'nenhuma'}.",
        "Igualdade no corpus congelado e evidencia de compatibilidade empirica, nao prova de que a rotina original foi recuperada, nem de que outras implementacoes seriam impossiveis. A implementacao antiga continua ausente. As afirmacoes sobre o calculo estao limitadas as definicoes aqui executadas e ao snapshot identificado pelos hashes.",
        "## Comparacao das definicoes",
    ]
    table = [
        "| Candidata | Canais iguais | Canais diferentes | Maior diferenca absoluta | Diferentes com menos de 500 mensagens | Decisoes finais alteradas |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        table.append(f"| `{row['candidate']}` | {row['matching_channels']} | {row['different_channels']} | {row['max_absolute_difference']} | {row['different_channels_below_500']} | {row['changed_final_decisions']} |")
    lines.append("\n".join(table))
    lines.append("## Predicados executados")
    for name, definition in summary["candidate_definitions"].items():
        lines.append(f"- `{name}`: {definition}.")
    lines += [
        "A variante principal aceita autorrespostas. A condicao de mencao usa somente `mention_count > 0`, sem exigir que o destinatario seja outro humano e sem procurar um antecedente semantico. Replies sao identificados pelo campo de referencia, nao obrigatoriamente pelo tipo Discord 19. A variante resolvida exige pai humano unico, com timestamp valido e anterior na ordem UTC/ID, no mesmo servidor e canal. Essas escolhas sao explicitas na reconstrucao; casos nao presentes no export nao permitem distinguir todas as alternativas historicas.",
        "## Papel no filtro e impacto",
        "A regra final exclui por baixa atividade apenas quando `total_messages < 500 AND interacting_authors < 5`; a lista manual e aplicada por uniao. Assim, a metrica serve de contrapeso ao volume em canais pequenos, nao como validacao de relevancia para Engenharia de Software ou qualidade conversacional.",
        f"A decisao historica manteve {summary['historical_counts']['retained_channels']} canais; {summary['historical_counts']['retained_channels_below_500_messages']} tinham menos de 500 mensagens brutas. Substituir a metrica por autores humanos distintos mudaria {next(row['changed_final_decisions'] for row in rows if row['candidate'] == 'human_authors')} decisoes nesta auditoria. As comparacoes sao contrafactuais: nenhum corpus, quadro ou amostra foi alterado.",
        "O filtro exploratorio 552 mensagens/3 autores unicos e a regra final 500 AND 5 tem papeis e medidas diferentes. A reconstrucao da metrica nao recupera a justificativa contemporanea da mudanca de limiares nem razoes humanas de exclusao que nao foram registradas.",
        "## Reproducao e rastreabilidade",
        "```powershell\npython -m discord_filtering.interaction_audit --output <novo_diretorio>\n```",
        "O comando verifica o pacote historico e o hash da fonte, recusa saida existente e exporta `channel_comparison.csv`, `candidates.csv`, `summary.json` e `manifest.json`. O primeiro CSV preserva os valores por canal, as diferencas para cada candidata e o efeito sobre a decisao. Todos os calculos estao no arquivo Python, sem consultas ad hoc fora dele.",
        "Para gerar novamente somente este documento a partir da auditoria existente:",
        "```powershell\npython -m discord_filtering.interaction_audit --report-only --overwrite-report\n```",
        "Use `--output` para indicar o diretorio auditado e `--report` para outro Markdown. A geracao verifica os hashes dos artefatos antes de ler o resumo. O manifesto adjacente ao documento registra a auditoria, o gerador e o Markdown.",
        f"Fonte: `{manifest['inputs'][0]['path']}`; SHA-256: `{manifest['inputs'][0]['sha256']}`.",
        f"Pacote historico: SHA-256 do manifesto `{manifest['inputs'][1]['sha256']}`.",
    ]
    sidecar = report.with_name(report.name + ".manifest.json")
    if not overwrite and (report.exists() or sidecar.exists()):
        raise FileExistsError(f"report already exists: {report}")
    atomic_write_bytes(report, ("\n\n".join(lines) + "\n").encode("utf-8"), overwrite=overwrite)
    provenance = {
        "command": "interaction-audit-report",
        "audit_manifest_sha256": sha256_file(output / "manifest.json"),
        "generator_sha256": sha256_file(Path(__file__)),
        "output_sha256": sha256_file(report),
    }
    atomic_write_bytes(sidecar, (json.dumps(provenance, indent=2) + "\n").encode(), overwrite=overwrite)
    return report


def compare_candidates(
    source: str | Path,
    statistics: pd.DataFrame,
    excluded_names: set[str],
    *,
    database: str | Path = ":memory:",
    memory_limit: str = "2GB",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    historical = channel_decisions(statistics, excluded_names)
    with duckdb.connect(str(database)) as connection:
        connection.execute("SET memory_limit = ?", [memory_limit])
        connection.execute("SET threads = 2")
        connection.execute("SET preserve_insertion_order = false")
        connection.execute("SET TimeZone = 'UTC'")
        if str(database) != ":memory:":
            connection.execute("SET temp_directory = ?", [str(Path(database).parent / "spill")])
        connection.from_parquet(str(source)).create_view("source")
        required = {"guild_id", "channel_id", "message_id", "author_id", "is_bot", "timestamp", "referenced_message_id", "mention_count"}
        columns = {row[0] for row in connection.execute("DESCRIBE source").fetchall()}
        if missing := required - columns:
            raise ValueError(f"missing source columns: {', '.join(sorted(missing))}")
        connection.execute("""
            CREATE TABLE messages AS
            SELECT cast(guild_id AS VARCHAR) AS guild_id,
                   cast(channel_id AS VARCHAR) AS channel_id,
                   nullif(trim(cast(message_id AS VARCHAR)), '') AS message_id,
                   nullif(trim(cast(author_id AS VARCHAR)), '') AS author_id,
                   is_bot = false AS human,
                   try_cast(timestamp AS TIMESTAMPTZ) AS sent_at,
                   nullif(trim(cast(referenced_message_id AS VARCHAR)), '') AS parent_id,
                   coalesce(mention_count, 0) > 0 AS mentions
            FROM source
        """)
        connection.execute("""
            CREATE TABLE parents AS
            SELECT guild_id, channel_id, message_id,
                   min(sent_at) AS sent_at, min(author_id) AS author_id
            FROM messages
            WHERE human AND message_id IS NOT NULL AND author_id IS NOT NULL AND sent_at IS NOT NULL
            GROUP BY guild_id, channel_id, message_id HAVING count(*) = 1
        """)
        computed = connection.execute("""
            SELECT child.guild_id, child.channel_id, count(*) AS observed_messages,
                   count(DISTINCT child.author_id) FILTER (WHERE child.human) AS human_authors,
                   count(DISTINCT child.author_id) FILTER (WHERE child.human AND child.parent_id IS NOT NULL) AS reply_senders,
                   count(DISTINCT child.author_id) FILTER (WHERE child.human AND child.mentions) AS mention_senders,
                   count(DISTINCT child.author_id) FILTER (
                       WHERE child.human AND (child.parent_id IS NOT NULL OR child.mentions)
                   ) AS reply_or_mention_senders,
                   count(DISTINCT child.author_id) FILTER (
                       WHERE child.human AND parent.message_id IS NOT NULL
                         AND (parent.sent_at < child.sent_at OR (parent.sent_at = child.sent_at AND parent.message_id < child.message_id))
                   ) AS resolved_reply_senders,
                   count(DISTINCT child.author_id) FILTER (
                       WHERE child.human AND (child.mentions OR (parent.message_id IS NOT NULL
                         AND (parent.sent_at < child.sent_at OR (parent.sent_at = child.sent_at AND parent.message_id < child.message_id))))
                   ) AS resolved_reply_or_mention_senders,
                   count(DISTINCT child.author_id) FILTER (
                       WHERE child.human AND (child.mentions OR (parent.message_id IS NOT NULL
                         AND parent.author_id <> child.author_id
                         AND (parent.sent_at < child.sent_at OR (parent.sent_at = child.sent_at AND parent.message_id < child.message_id))))
                   ) AS other_author_reply_or_mention_senders
            FROM messages child LEFT JOIN parents parent
                ON child.guild_id = parent.guild_id AND child.channel_id = parent.channel_id
                AND child.parent_id = parent.message_id
            GROUP BY child.guild_id, child.channel_id
        """).fetchdf()
    for frame in (computed, historical):
        for field in ("guild_id", "channel_id"):
            frame[field] = frame[field].astype("string")
    comparison = historical.merge(computed, on=["guild_id", "channel_id"], how="outer", validate="one_to_one", indicator=True)
    if not comparison["_merge"].eq("both").all() or not comparison.total_messages.eq(comparison.observed_messages).all():
        raise ValueError("source channel membership or volume differs from historical statistics")
    comparison = comparison.drop(columns="_merge")
    rows = []
    for candidate in CANDIDATES:
        delta = comparison[candidate] - comparison.interacting_authors
        replay = channel_decisions(comparison.assign(interacting_authors=comparison[candidate]), excluded_names)
        comparison[candidate + "_delta"] = delta
        comparison[candidate + "_decision_changed"] = replay.retained.to_numpy() != historical.retained.to_numpy()
        rows.append({
            "candidate": candidate,
            "matching_channels": int(delta.eq(0).sum()),
            "different_channels": int(delta.ne(0).sum()),
            "max_absolute_difference": int(delta.abs().max()) if len(delta) else 0,
            "changed_final_decisions": int(comparison[candidate + "_decision_changed"].sum()),
            "different_channels_below_500": int((delta.ne(0) & comparison.total_messages.lt(500)).sum()),
            "total_channels": len(comparison),
        })
    return comparison, pd.DataFrame(rows)


def audit_interacting_authors(
    source: str | Path = DEFAULT_SOURCE,
    bundle: str | Path = DEFAULT_BUNDLE,
    output: str | Path = DEFAULT_OUTPUT,
    *,
    memory_limit: str = "2GB",
) -> dict:
    source, bundle, output = (Path(path).resolve() for path in (source, bundle, output))
    if output.exists():
        raise FileExistsError(f"audit output already exists: {output}")
    historical_audit = verify_historical_selection(bundle)
    corpus_manifest = json.loads((bundle / "corpus.manifest.json").read_text(encoding="utf-8"))
    source_reference = next(item for item in corpus_manifest["inputs"] if Path(item["path"]).name == source.name)
    source_hash = sha256_file(source)
    if source_hash != source_reference["sha256"]:
        raise ValueError("source hash differs from frozen historical manifest")
    names = {line.strip() for line in (bundle / "exclusions.txt").read_text(encoding="utf-8").splitlines() if line.strip()}
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".interaction-audit-", dir=output.parent) as temporary:
        staging = Path(temporary)
        work = staging / "work"
        work.mkdir()
        comparison, candidates = compare_candidates(source, pd.read_parquet(bundle / "statistics.parquet"), names, database=work / "audit.duckdb", memory_limit=memory_limit)
        exact = candidates.loc[candidates.different_channels.eq(0), "candidate"].tolist()
        summary = {
            "historical_definition_status": "unrecovered",
            "exactly_matching_candidates": exact,
            "interpretation": "empirical compatibility on this frozen corpus, not proof of the original implementation or uniqueness of the historical definition",
            "historical_counts": historical_audit["counts"],
            "candidate_definitions": CANDIDATES,
            "candidate_results": candidates.to_dict(orient="records"),
            "scope": "all historical source channels, including excluded channels; no corpus filtering, resampling or semantic classification",
            "ordering": "UTC timestamp then lexical message_id; only resolved variants require unique identified human parents with valid timestamps",
        }
        atomic_write_bytes(staging / "channel_comparison.csv", comparison.to_csv(index=False, lineterminator="\n").encode("utf-8"))
        atomic_write_bytes(staging / "candidates.csv", candidates.to_csv(index=False, lineterminator="\n").encode("utf-8"))
        atomic_write_bytes(staging / "summary.json", (json.dumps(summary, indent=2) + "\n").encode())
        manifest = {
            "command": "audit-interacting-authors",
            "implementation_sha256": sha256_file(Path(__file__)),
            "inputs": [{"path": str(source), "sha256": source_hash}, {"path": str(bundle / "manifest.json"), "sha256": sha256_file(bundle / "manifest.json")}],
            "parameters": {"memory_limit": memory_limit, "threads": 2},
            "outputs": [{"name": name, "sha256": sha256_file(staging / name)} for name in ("channel_comparison.csv", "candidates.csv", "summary.json")],
        }
        atomic_write_bytes(staging / "manifest.json", (json.dumps(manifest, indent=2) + "\n").encode())
        shutil.rmtree(work)
        staging.rename(output)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare explicit author-count hypotheses with frozen historical channel statistics.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--bundle", type=Path, default=DEFAULT_BUNDLE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--memory-limit", default="2GB")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--overwrite-report", action="store_true")
    arguments = parser.parse_args()
    if not arguments.report_only:
        print(json.dumps(audit_interacting_authors(arguments.source, arguments.bundle, arguments.output, memory_limit=arguments.memory_limit), indent=2))
    if arguments.report is not None or arguments.report_only:
        print(write_audit_report(arguments.output, arguments.report or DEFAULT_REPORT, overwrite=arguments.overwrite_report))


if __name__ == "__main__":
    main()