from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from discord_disentanglement.population import DEFAULT_OUTPUT, ROOT
from discord_filtering.storage import atomic_write_bytes, sha256_file


DEFAULT_REPORT = ROOT / "docs/methodology/POPULATION_CHARACTERIZATION.md"
INPUT_FILES = (
    "channels.csv", "servers.csv", "temporal_activity.csv",
    "reply_distances.csv", "concentration.csv", "summary.json",
)


def number(value: object, digits: int = 0) -> str:
    if value is None or pd.isna(value):
        return "NA"
    return f"{float(value):,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def percentage(numerator: float, denominator: float) -> str:
    return number(100 * numerator / denominator, 2) + "%" if denominator else "NA"


def markdown_table(headers: list[str], rows: list[list[object]]) -> str:
    def cell(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")

    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    lines.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def distribution(values: pd.Series) -> list[str]:
    clean = values.dropna().astype(float)
    if clean.empty:
        return ["NA"] * 8
    return [number(value, 2) for value in (
        clean.min(), clean.quantile(0.25), clean.median(), clean.mean(),
        clean.quantile(0.75), clean.quantile(0.9), clean.quantile(0.95), clean.max(),
    )]


def concentration_statistics(volumes: pd.Series) -> dict:
    ordered = np.sort(volumes.to_numpy(dtype=float))[::-1]
    if (ordered < 0).any():
        raise ValueError("message volumes must be nonnegative")
    total = float(ordered.sum())
    if not total:
        return {"total": 0, "units": len(ordered), "gini": None, "hhi": None, "effective_units": None, "thresholds": [], "top_shares": []}
    shares = ordered / total
    cumulative = np.cumsum(ordered)
    ascending = ordered[::-1]
    ranks = np.arange(1, len(ordered) + 1)
    gini = float(2 * np.dot(ranks, ascending) / (len(ordered) * total) - (len(ordered) + 1) / len(ordered))
    hhi = float(np.square(shares).sum())
    thresholds = []
    for threshold in (0.5, 0.8, 0.9, 0.95):
        count = int(np.searchsorted(cumulative, threshold * total, side="left") + 1)
        thresholds.append({"threshold": threshold, "units": count, "actual_share": float(cumulative[count - 1] / total)})
    return {
        "total": total, "units": len(ordered), "gini": gini,
        "hhi": hhi, "effective_units": 1 / hhi, "thresholds": thresholds,
        "top_shares": [{"units": min(count, len(ordered)), "share": float(shares[:count].sum())} for count in (1, 5, 10, 20, 50)],
    }


def generate_population_report(
    input_dir: str | Path,
    output_path: str | Path,
    *,
    overwrite: bool = False,
) -> Path:
    directory = Path(input_dir).resolve()
    output = Path(output_path).resolve()
    provenance_path = output.with_name(output.name + ".manifest.json")
    if not overwrite and (output.exists() or provenance_path.exists()):
        raise FileExistsError(f"report already exists: {output}; use --overwrite")
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("usability_definition_version") != "payload_v2":
        raise ValueError("expected payload_v2 artifacts; rerun discord_disentanglement.population in a new directory")
    expected = {Path(item["path"]).name: item["sha256"] for item in manifest["outputs"]}
    hashes = {}
    for filename in INPUT_FILES:
        hashes[filename] = sha256_file(directory / filename)
        if expected.get(filename) != hashes[filename]:
            raise ValueError(f"artifact hash mismatch: {filename}")
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    channels = pd.read_csv(directory / "channels.csv", dtype={"guild_id": "string", "channel_id": "string"})
    servers = pd.read_csv(directory / "servers.csv", dtype={"guild_id": "string"})
    temporal = pd.read_csv(directory / "temporal_activity.csv", dtype={"period_utc": "string"})
    replies = pd.read_csv(directory / "reply_distances.csv", dtype={"guild_id": "string", "channel_id": "string"})
    concentration = pd.read_csv(directory / "concentration.csv")
    total = summary["total_records"]
    usable = summary.get("usable_human_messages", 0)
    if summary.get("usable_records", 0) + summary.get("unusable_records", 0) != total:
        raise ValueError("payload counts disagree with total records")
    for frame in (channels, servers):
        if frame["total_records"].sum() != total or frame["usable_human_messages"].sum() != usable:
            raise ValueError("aggregate counts disagree with summary")
        if frame["unusable_records"].sum() != summary.get("unusable_records", 0):
            raise ValueError("unusable counts disagree with summary")
    for unit in ("month", "weekday", "hour"):
        activity = temporal.loc[temporal.temporal_unit == unit]
        if activity.total_records.sum() != total - summary.get("missing_or_invalid_timestamp", 0):
            raise ValueError(f"temporal counts disagree: {unit}")
        if activity.usable_human_messages.sum() != usable - summary.get("usable_messages_without_valid_timestamp", 0):
            raise ValueError(f"usable temporal counts disagree: {unit}")
    if replies.replies.sum() + summary.get("native_replies_without_orderable_source", 0) != summary.get("native_reply_records", 0):
        raise ValueError("reply counts disagree with summary")
    lines = [
        "# Caracterizacao da populacao de canais mantidos",
        "## 1. Escopo, fontes e reproducibilidade",
        "Este documento descreve o corpus apos a selecao de canais da Etapa 2, antes do sorteio das janelas da Etapa 3. As estatisticas sao descritivas do export observado, nao estimativas de todas as mensagens das comunidades nem resultados de classificacao semantica ou toxicidade.",
        f"Extracao das estatisticas: `{manifest['created_at_utc']}`. Todos os horarios e agrupamentos temporais usam UTC.",
        f"Entrada congelada: `{Path(manifest['inputs'][0]['path']).name}`.",
        "Os calculos deste documento sao executados por `discord_disentanglement/population_report.py`, sobre os CSVs e o resumo produzidos por `discord_disentanglement/population.py`. O gerador verifica os hashes dos artefatos e a reconciliacao dos totais antes de escrever. Nao precisa reler os milhoes de mensagens para gerar o texto.",
        "```powershell\npython -m discord_disentanglement.population_report\n```",
        "Para regenerar explicitamente ou usar outros artefatos:",
        f"```powershell\npython -m discord_disentanglement.population_report `\n  --input-dir {DEFAULT_OUTPUT.relative_to(ROOT).as_posix()} `\n  --output docs/methodology/POPULATION_CHARACTERIZATION.md `\n  --overwrite\n```",
        "O Markdown tem um manifesto adjacente com hashes dos artefatos utilizados, do gerador e do documento. A validacao de hashes cobre os relatorios; o Parquet original nao e relido por este gerador. Valores sao formatados com ponto para milhares e virgula para decimais; NA indica denominador nulo ou medida indisponivel. Arredondamento ocorre apenas na apresentacao.",
        "## 2. Populacao observada e quadro utilizavel",
    ]
    overview = [
        ["Servidores com registros", number(len(servers))],
        ["Canais com registros", number(len(channels))],
        ["Registros totais", number(total)],
        ["Registros explicitamente humanos", number(summary.get("human_records", 0))],
        ["Registros com texto ou midia (qualquer autor)", number(summary.get("usable_records", 0))],
        ["Mensagens humanas utilizaveis", number(usable)],
        ["Nao utilizaveis: sem texto nem midia registrada", number(summary.get("unusable_records", 0))],
        ["Mensagens humanas com conteudo e problemas estruturais", number(summary.get("human_messages_with_structural_issues", 0))],
        ["Autores humanos distintos no corpus", number(summary.get("distinct_human_authors", 0))],
        ["Autores humanos distintos no quadro utilizavel", number(summary.get("distinct_usable_human_authors", 0))],
        ["Primeiro timestamp observado (UTC)", summary.get("first_timestamp_utc", "NA")],
        ["Ultimo timestamp observado (UTC)", summary.get("last_timestamp_utc", "NA")],
        ["Dias com atividade observada no corpus", number(summary.get("active_days", 0))],
    ]
    lines += [markdown_table(["Medida", "Valor"], overview),
        "Neste projeto, nao utilizavel significa exclusivamente um registro sem texto nao vazio e sem anexo, embed ou sticker registrado. Texto composto apenas por espacos e considerado vazio. Havendo texto ou midia, o registro e utilizavel nesta caracterizacao, independentemente do tipo Discord. Uma mensagem humana utilizavel tem conteudo registrado e `is_bot = false`; status de bot ausente nao e presumido humano. Bots com conteudo nao sao classificados como nao utilizaveis, mas nao pertencem a populacao humana.",
        "IDs ausentes, timestamp invalido e chave duplicada sao problemas estruturais separados, nao motivos de nao utilizabilidade pela definicao adotada. Registros com conteudo e essas flags permanecem no volume utilizavel; calculos que exigem identificacao e ordem cronologica precisam exclui-los de sua base especifica. Todos os tipos de mensagem sao aceitos para volume quando ha conteudo. Utilizabilidade nao garante relevancia tematica ou elegibilidade final para anotacao. O quadro amostral definitivo ainda deve ser congelado apos revisar as restricoes tecnicas das janelas.",
        "Autores sao deduplicados globalmente por ID no resumo. A soma de autores distintos por canal/servidor nao e uma contagem global, pois a mesma pessoa pode aparecer em varios canais. Dias ativos globais tambem nao sao somas dos dias ativos dos canais.",
        f"Registros com texto ou midia representam {percentage(summary.get('usable_records', 0), total)} do total; {percentage(summary.get('unusable_records', 0), total)} nao possuem conteudo registrado. Mensagens humanas utilizaveis representam {percentage(usable, total)} do total. Dos autores humanos observados, {percentage(summary.get('distinct_usable_human_authors', 0), summary.get('distinct_human_authors', 0))} possuem ao menos uma mensagem utilizavel. A diferenca entre autores observados e autores do quadro decorre da disponibilidade de conteudo em suas mensagens, nao do tipo Discord.",
        "A definicao `payload_v2` substitui a regra inicial que tambem rejeitava tipos diferentes de 0/19 e problemas estruturais. Os artefatos anteriores permanecem em `data/processed/disentanglement/population`; as estatisticas abaixo foram recalculadas pela nova regra. Mensagens totalmente ausentes do export continuam sendo uma perda desconhecida, distinta de registros presentes sem conteudo.",
        "## 3. Distribuicao de volume e concentracao",
        "### 3.1. Distribuicao entre canais e servidores",
    ]
    distributions = []
    for scope, frame in (("Canal", channels), ("Servidor", servers)):
        for field, label in (("total_records", "Registros"), ("usable_human_messages", "Mensagens utilizaveis"), ("distinct_human_authors", "Autores humanos distintos")):
            distributions.append([scope, label, *distribution(frame[field])])
    lines.append(markdown_table(["Unidade", "Medida", "Min", "Q25", "Mediana", "Media", "Q75", "Q90", "Q95", "Max"], distributions))
    lines.append("Os quantis acima sao entre unidades: cada canal ou servidor tem peso um. Usam interpolacao linear (`pandas.Series.quantile`). Nao sao quantis entre mensagens.")
    lines.append("### 3.2. Concentracao acumulada")
    concentration_rows = []
    concentration_indices = []
    top_rows = []
    for scope, frame in (("channel", channels), ("server", servers)):
        for population, field in (("all_records", "total_records"), ("usable_human", "usable_human_messages")):
            stats = concentration_statistics(frame[field])
            exported = concentration.loc[(concentration.scope == scope) & (concentration.population == population)]
            if exported.messages.sum() != stats["total"]:
                raise ValueError("concentration counts disagree")
            for item in stats["thresholds"]:
                concentration_rows.append([scope, population, percentage(item["threshold"], 1), number(item["units"]), percentage(item["units"], stats["units"]), percentage(item["actual_share"], 1)])
            concentration_indices.append([scope, population, number(stats["gini"], 4), number(stats["hhi"], 4), number(stats["effective_units"], 2)])
            for item in stats["top_shares"]:
                top_rows.append([scope, population, number(item["units"]), percentage(item["share"], 1)])
    lines += [markdown_table(["Unidade", "Populacao", "Meta de volume", "Unidades necessarias", "% das unidades", "Volume efetivamente coberto"], concentration_rows),
        "As unidades sao ordenadas por volume decrescente. O limiar e o menor numero de unidades cuja soma atinge a meta; a participacao efetiva pode exceder a meta devido a indivisibilidade dos canais. `all_records` usa todos os registros; `usable_human` usa o quadro utilizavel.",
        markdown_table(["Unidade", "Populacao", "Gini", "HHI", "Numero efetivo de unidades"], concentration_indices),
        "Gini mede desigualdade de volume (0 indica volumes iguais). HHI e a soma dos quadrados das participacoes, na escala 0 a 1; seu inverso e o numero de unidades de igual volume com concentracao equivalente. Estes indices descrevem volume, nao qualidade ou importancia cientifica.",
        "$$G = \\frac{2\\sum_{i=1}^{k} i x_{(i)}}{k\\sum_{i=1}^{k}x_i}-\\frac{k+1}{k}, \\qquad HHI=\\sum_{i=1}^{k}s_i^2, \\qquad k_{efetivo}=\\frac{1}{HHI}$$",
        "Na formula de Gini, os volumes sao ordenados de forma crescente; $s_i=x_i/\\sum_jx_j$.",
        markdown_table(["Unidade", "Populacao", "Maiores unidades", "% das mensagens"], top_rows),
        "### 3.3. Faixas de tamanho dos canais",
    ]
    for label, frame in (("canais", channels), ("servidores", servers)):
        stats = concentration_statistics(frame.usable_human_messages)
        if stats["total"]:
            threshold = next(item for item in stats["thresholds"] if item["threshold"] == 0.8)
            lines.insert(-1, f"Na populacao utilizavel, {number(threshold['units'])} de {number(stats['units'])} {label} ({percentage(threshold['units'], stats['units'])}) atingem 80% do volume, cobrindo efetivamente {percentage(threshold['actual_share'], 1)}. A unidade de maior volume concentra {percentage(stats['top_shares'][0]['share'], 1)} das mensagens utilizaveis.")
    bins = [0, 500, 1000, 5000, 10000, 50000, 100000, float("inf")]
    labels = ["0 a 499", "500 a 999", "1.000 a 4.999", "5.000 a 9.999", "10.000 a 49.999", "50.000 a 99.999", "100.000 ou mais"]
    bands = pd.cut(channels.usable_human_messages, bins=bins, labels=labels, right=False)
    band_rows = []
    for label in labels:
        selected = channels.loc[bands == label]
        messages = selected.usable_human_messages.sum()
        band_rows.append([label, number(len(selected)), percentage(len(selected), len(channels)), number(messages), percentage(messages, usable)])
    lines += [markdown_table(["Mensagens utilizaveis por canal", "Canais", "% dos canais", "Mensagens", "% das mensagens"], band_rows),
        "As faixas usam mensagens utilizaveis, nao o volume bruto empregado na selecao de canais. O corpus atual exige pelo menos 500 registros brutos e cinco autores humanos distintos por canal. Um canal pode ter menos de 500 mensagens utilizaveis se parte de seus registros nao tiver conteudo.",
        "### 3.4. Todos os servidores, por volume utilizavel",
    ]
    ranked_servers = servers.sort_values(["usable_human_messages", "guild_id"], ascending=[False, True])
    lines.append(markdown_table(["Servidor", "guild_id", "Canais", "Registros", "Utilizaveis", "% do quadro", "Autores humanos", "Primeiro UTC", "Ultimo UTC"], [
        [row.guild_name, row.guild_id, number(row.channels), number(row.total_records), number(row.usable_human_messages), percentage(row.usable_human_messages, usable), number(row.distinct_human_authors), row.first_timestamp_utc, row.last_timestamp_utc]
        for row in ranked_servers.itertuples()
    ]))
    ranked_channels = channels.sort_values(["usable_human_messages", "guild_id", "channel_id"], ascending=[False, True, True]).copy()
    ranked_channels["cumulative_messages"] = ranked_channels.usable_human_messages.cumsum()
    lines.append("### 3.5. Os 20 canais de maior volume utilizavel")
    lines.append(markdown_table(["Servidor", "Canal", "channel_id", "Utilizaveis", "% do quadro", "% acumulado", "Autores humanos"], [
        [row.guild_name, row.channel_name, row.channel_id, number(row.usable_human_messages), percentage(row.usable_human_messages, usable), percentage(row.cumulative_messages, usable), number(row.distinct_human_authors)]
        for row in ranked_channels.head(20).itertuples()
    ]))
    lines += ["## 4. Autores e participacao",
        "`distinct_human_authors` conta IDs humanos distintos presentes no canal, sem exigir replies ou mencoes. `distinct_usable_human_authors` exige pelo menos uma mensagem com conteudo registrado. Ambas sao contagens de participantes; nao inferem conversas semanticas. A selecao usa a primeira contagem, juntamente com o volume bruto do canal.",
        markdown_table(["Medida por canal", "Min", "Q25", "Mediana", "Media", "Q75", "Q90", "Q95", "Max"], [
            [field, *distribution(channels[field])] for field in ("distinct_human_authors", "distinct_usable_human_authors")
        ]),
        "A regra vigente exclui o canal quando `total_messages < 500 OR distinct_human_authors < 5`, alem das exclusoes manuais. As duas contagens sao calculadas diretamente das mensagens originais. A selecao, a caracterizacao e a amostra foram versionadas novamente; resultados anteriores nao definem o quadro atual. Consulte `docs/methodology/CHANNEL_SELECTION_STAGE.md` para o protocolo.",
        "Nao ha contagens por autor nos artefatos agregados; portanto este documento nao estima distribuicao individual de produtividade, participacao do autor dominante ou concentracao entre autores.",
        "## 5. Cobertura e distribuicao temporal",
        "### 5.1. Cobertura por canal",
    ]
    first = pd.to_datetime(channels.first_timestamp_utc, utc=True, format="mixed")
    last = pd.to_datetime(channels.last_timestamp_utc, utc=True, format="mixed")
    spans = (last.dt.normalize() - first.dt.normalize()).dt.days + 1
    rates = channels.usable_human_messages / channels.usable_active_days.replace(0, np.nan)
    lines += [markdown_table(["Medida por canal", "Min", "Q25", "Mediana", "Media", "Q75", "Q90", "Q95", "Max"], [
        ["Amplitude em dias calendario (inclusive)", *distribution(spans)],
        ["Dias ativos (todos os registros)", *distribution(channels.active_days)],
        ["Dias ativos (quadro utilizavel)", *distribution(channels.usable_active_days)],
        ["Mensagens utilizaveis por dia ativo", *distribution(rates)],
    ]),
        "Amplitude e diferenca entre as datas UTC extremas mais um dia; nao garante coleta continua. Mensagens por dia ativo divide o volume utilizavel pelos dias com ao menos uma mensagem utilizavel no canal. Nao e media por dia calendario nem intensidade corrigida pela disponibilidade do export.",
        "### 5.2. Atividade por ano",
    ]
    months = temporal.loc[temporal.temporal_unit == "month"].copy()
    months["year"] = months.period_utc.str[:4]
    years = months.groupby("year")[["total_records", "usable_human_messages"]].sum()
    lines.append(markdown_table(["Ano UTC", "Registros", "% dos registros", "Utilizaveis", "% do quadro"], [
        [year, number(row.total_records), percentage(row.total_records, total), number(row.usable_human_messages), percentage(row.usable_human_messages, usable)] for year, row in years.iterrows()
    ]))
    lines.append("Anos e meses nas extremidades podem ser parciais. Contagens anuais nao sao taxas anualizadas; diferencas podem refletir cobertura do export, entrada/saida de canais ou mudancas reais de atividade.")
    lines.append("### 5.3. Dez meses de maior volume utilizavel")
    monthly = months.groupby("period_utc")[["total_records", "usable_human_messages"]].sum().reset_index()
    monthly = monthly.sort_values(["usable_human_messages", "period_utc"], ascending=[False, True])
    lines.append(markdown_table(["Mes UTC", "Registros", "Utilizaveis", "% do quadro"], [
        [row.period_utc, number(row.total_records), number(row.usable_human_messages), percentage(row.usable_human_messages, usable)] for row in monthly.head(10).itertuples()
    ]))
    for unit, title, index, names in (
        ("weekday", "5.4. Atividade por dia da semana", range(1, 8), ["Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado", "Domingo"]),
        ("hour", "5.5. Atividade por hora UTC", range(24), [f"{hour:02d}:00 a {hour:02d}:59" for hour in range(24)]),
    ):
        selected = temporal.loc[temporal.temporal_unit == unit].copy()
        selected["bucket"] = selected.period_utc.astype(int)
        buckets = selected.groupby("bucket")[["total_records", "usable_human_messages"]].sum().reindex(index, fill_value=0)
        lines.append(f"### {title}")
        lines.append(markdown_table(["Periodo UTC", "Registros", "Utilizaveis", "% do quadro"], [
            [label, number(row.total_records), number(row.usable_human_messages), percentage(row.usable_human_messages, usable)] for label, row in zip(names, buckets.itertuples())
        ]))
    lines += ["Dias da semana e horas agregam todos os periodos e canais. As participacoes nao sao corrigidas pelo numero de ocorrencias de cada dia no historico, nem pelo fuso local dos participantes. A rotina original exporta apenas buckets observados; dias da semana/horas ausentes sao preenchidos com zero nesta apresentacao, sem supor completude da coleta. Mensagens com timestamp ausente/invalido nao podem ser agrupadas temporalmente, mesmo se tiverem conteudo; as participacoes usam todo o volume como denominador.",
        "## 6. Native replies, antecedentes e distancias",
        "### 6.1. Frequencia e denominadores",
        markdown_table(["Medida", "Contagem", "Denominador", "Proporcao"], [
            ["Native replies", number(summary.get("native_reply_records", 0)), "Todos os registros", percentage(summary.get("native_reply_records", 0), total)],
            ["Native replies utilizaveis", number(summary.get("usable_native_replies", 0)), "Mensagens utilizaveis", percentage(summary.get("usable_native_replies", 0), usable)],
            ["Qualquer referencia nativa", number(summary.get("reference_records", 0)), "Todos os registros", percentage(summary.get("reference_records", 0), total)],
            ["Reply sem ID do antecedente", number(summary.get("replies_without_parent_id", 0)), "Todos os registros", percentage(summary.get("replies_without_parent_id", 0), total)],
        ]),
        "Native reply exige tipo Discord 19 e ID de referencia nao vazio. Referencias de outros tipos nao sao incluidas como replies. Ausencia de reply nativo nao significa ausencia de resposta semantica.",
        "### 6.2. Resolucao de antecedentes",
    ]
    status_rows = []
    for population, frame in (("Todas as origens ordenaveis", replies), ("Origens utilizaveis", replies.loc[replies.source_usable == True])):
        denominator = frame.replies.sum()
        for status, count in frame.groupby("status").replies.sum().items():
            status_rows.append([population, status, number(count), number(denominator), percentage(count, denominator)])
    lines += [markdown_table(["Populacao de replies", "Status", "Replies", "Denominador", "Proporcao"], status_rows),
        f"Replies com origem nao ordenavel, fora da tabela de distancias: {number(summary.get('native_replies_without_orderable_source', 0))}.",
        "`resolved`: antecedente identificado, unico, com timestamp valido e anterior no mesmo canal; `parent_not_found`: nao localizado na base ordenavel; `different_channel`: encontrado em outro canal; `not_preceding`: origem igual ao antecedente ou antecedente posterior na ordem. Nao encontrado nao demonstra exclusao: pode ser mensagem fora do export ou registro nao ordenavel.",
        "### 6.3. Alcance posicional agregado",
    ]
    distance_rows = []
    for population, frame in (("Todas as origens", replies), ("Origens utilizaveis", replies.loc[replies.source_usable == True])):
        resolved = frame.loc[frame.status == "resolved"]
        denominator = resolved.replies.sum()
        for threshold in (10, 100, 200):
            count = resolved[f"within_{threshold}_records"].sum()
            distance_rows.append([population, number(threshold), number(count), number(denominator), percentage(count, denominator)])
        pairs = resolved.usable_parent_pairs.sum()
        lines.append(f"{population}: {number(pairs)} pares com origem e antecedente utilizaveis entre {number(denominator)} replies resolvidos ({percentage(pairs, denominator)}).")
    lines += [markdown_table(["Populacao", "Distancia ate (registros)", "Replies cobertos", "Replies resolvidos", "Cobertura"], distance_rows),
        "Estas proporcoes globais sao calculadas pela soma das contagens dos canais dividida pela soma dos replies resolvidos, nao pela media das proporcoes. A distancia e posicao da origem menos posicao do antecedente; 1 indica adjacencia. A ordem inclui todos os registros unicos e identificaveis com timestamp valido, incluindo bots e tipos de sistema. Ha uma ordem alternativa somente de mensagens utilizaveis para pares utilizaveis.",
        "Cobertura ate 200 registros e um diagnostico de alcance dos native replies, nao garantia de contexto suficiente para arestas semanticas. A posicao da mensagem-alvo dentro da janela e a ordem usada na geracao de janelas tambem alteram o contexto disponivel.",
        "### 6.4. Quantis por canal de maior volume",
    ]
    quantile_rows = []
    available = replies.loc[(replies.status == "resolved") & (replies.source_usable == True)]
    lookup = {(row.guild_id, row.channel_id): row for row in available.itertuples()}
    for channel in ranked_channels.head(20).itertuples():
        row = lookup.get((channel.guild_id, channel.channel_id))
        if row is None:
            continue
        positions = json.loads(row.position_quantiles)
        seconds = json.loads(row.seconds_quantiles)
        quantile_rows.append([channel.guild_name, channel.channel_name, channel.channel_id, number(row.replies), number(positions[1], 2), number(positions[4], 2), number(seconds[1] / 60, 2), number(seconds[4] / 3600, 2)])
    lines += [markdown_table(["Servidor", "Canal", "channel_id", "Replies resolvidos utilizaveis", "Mediana posicional", "Q95 posicional", "Mediana temporal (min)", "Q95 temporal (h)"], quantile_rows),
        "Quantis sao calculados sobre replies de origem utilizavel resolvidos no respectivo canal. O antecedente pode nao ser utilizavel. Minutos e horas sao conversoes de segundos por divisao por 60 e 3.600. O CSV original preserva Q25, Q50, Q75, Q90, Q95 e Q99, inclusive na ordem alternativa utilizavel. Nao e possivel recuperar quantis globais exatos apenas desses quantis por canal; este documento nao os inventa nem calcula medias de quantis.",
        "## 7. Bots, campos ausentes e registros nao utilizaveis",
    ]
    quality_fields = (
        ("bot_records", "Bots registrados"), ("unknown_bot_status", "Status de bot ausente"),
        ("missing_message_id", "ID da mensagem ausente"), ("missing_author_id", "ID do autor ausente"),
        ("missing_scope", "Servidor/canal ausente"), ("missing_or_invalid_timestamp", "Timestamp ausente/invalido"),
        ("duplicate_id_records", "Registros com chave duplicada"), ("empty_text_records", "Texto vazio ou ausente"),
        ("human_messages_with_structural_issues", "Mensagens humanas com conteudo e problemas estruturais"),
        ("other_or_unknown_type_records", "Tipo diferente de 0/19 ou ausente (nao implica nao utilizabilidade)"),
        ("unusable_records", "Nao utilizaveis: sem texto nem midia registrada"),
    )
    lines += [markdown_table(["Flag", "Registros", "% de todos os registros"], [
        [label, number(summary.get(field, 0)), percentage(summary.get(field, 0), total)] for field, label in quality_fields
    ]),
        "As flags sao descritivas, podem se sobrepor e nao devem ser somadas. Somente a ausencia simultanea de texto e midia define nao utilizabilidade. Tipos diferentes de 0/19, bots e problemas estruturais nao sao incluidos nessa contagem pelo simples fato de apresentarem essas caracteristicas. Texto vazio sozinho nao torna uma mensagem inutilizavel quando ha anexo, embed ou sticker. Nao se presume que a disponibilidade de midia significa que seu conteudo foi baixado ou sera visivel ao anotador.",
        "Uma proporcao zero de bots descreve apenas a entrada analisada, que pode ter passado por exclusao previa de bots. Nao demonstra que os servidores nao possuem bots. Mensagens completamente ausentes do export nao podem ser contadas sem fonte externa; antecedentes nao localizados e campos ausentes sao indicadores diferentes dessa perda desconhecida.",
        "## 8. Implicacoes para a construcao de janelas",
        "A concentracao deve ser avaliada sobre `usable_human` ao planejar mensagens-alvo. A amostragem proporcional ao volume favorece canais grandes. Isso e coerente para estimar uma media entre mensagens, mas pode deixar poucos exemplos dos canais pequenos para comparacoes entre canais. Uma media entre canais e uma media entre mensagens sao estimandos distintos.",
        "Uma alternativa a avaliar e estabelecer cobertura minima por canal e distribuir o restante proporcionalmente ao volume. As probabilidades de inclusao e os pesos precisam ser registrados quando o desenho for definido. Esta caracterizacao nao determina tamanho amostral, nao estima efeito de desenho e nao sorteia janelas.",
        "Estratificar temporalmente dentro de cada canal evita selecionar apenas inicio/fim do historico ou meses de maior atividade. O volume global por ano nao deve substituir a avaliacao do periodo disponivel de cada canal. Periodos sem registros nao provam inatividade nem falha de coleta.",
        "O piloto deve confrontar alcance posicional dos native replies com antecedentes semanticos anotados, registrar casos fora do contexto e verificar mensagens de midia. Nao interpretar ausencia de reply nativo como rotulo negativo, nem quantidade de participantes como medida completa de sociabilidade.",
        "## 9. Inventario completo dos canais",
        "Uma linha por par `(guild_id, channel_id)`, ordenada pelo volume utilizavel. Autores H sao distintos humanos; autores U sao distintos com mensagens utilizaveis. Replies % divide native replies utilizaveis por mensagens utilizaveis do canal. Flags detalhadas e quantis adicionais permanecem nos CSVs.",
        markdown_table(["Servidor", "guild_id", "Canal", "channel_id", "Registros", "Utilizaveis", "% do quadro", "Autores H", "Autores U", "Replies %", "Dias ativos U", "Primeiro UTC", "Ultimo UTC"], [
            [row.guild_name, row.guild_id, row.channel_name, row.channel_id, number(row.total_records), number(row.usable_human_messages), percentage(row.usable_human_messages, usable), number(row.distinct_human_authors), number(row.distinct_usable_human_authors), percentage(row.usable_native_replies, row.usable_human_messages), number(row.usable_active_days), row.first_timestamp_utc, row.last_timestamp_utc]
            for row in ranked_channels.itertuples()
        ]),
        "## 10. Fontes auditaveis",
        "Os arquivos de entrada deste documento estao em `" + directory.relative_to(ROOT).as_posix() + "`." if directory.is_relative_to(ROOT) else f"Diretorio de artefatos: `{directory}`.",
        markdown_table(["Arquivo", "SHA-256"], [[filename, f"`{hashes[filename]}`"] for filename in INPUT_FILES]),
        "Os numeradores, denominadores, agrupamentos, faixas e formulas adicionais estao no gerador Python. A extracao original, suas definicoes e a proveniencia do Parquet estao no manifesto da populacao. Nao foram adicionados calculos manuais fora desses arquivos executaveis.",
    ]
    payload = ("\n\n".join(lines) + "\n").encode("utf-8")
    atomic_write_bytes(output, payload, overwrite=overwrite)
    provenance = {
        "manifest_schema_version": 1,
        "command": "generate-population-report",
        "generator_sha256": sha256_file(Path(__file__)),
        "population_manifest_sha256": sha256_file(directory / "manifest.json"),
        "inputs": [{"path": str(directory / filename), "sha256": hashes[filename]} for filename in INPUT_FILES],
        "output": {"path": str(output), "sha256": sha256_file(output)},
    }
    atomic_write_bytes(provenance_path, json.dumps(provenance, indent=2).encode() + b"\n", overwrite=overwrite)
    return output


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate an auditable detailed population report in Markdown.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--overwrite", action="store_true")
    arguments = parser.parse_args(argv)
    print(generate_population_report(arguments.input_dir, arguments.output, overwrite=arguments.overwrite))


if __name__ == "__main__":
    main()