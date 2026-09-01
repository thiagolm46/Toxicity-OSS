"""Streamlit interface for inspecting completed disentanglement experiments."""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from discord_disentanglement.ui.data import (
    ExperimentRepository,
    LoadedRun,
    discover_experiments,
)
from discord_disentanglement.evaluation.clustering import projected_conversation_metrics
from discord_disentanglement.evaluation.ranking import (
    candidate_generation_metrics,
    ranking_metrics,
)


def launch() -> None:
    """Launch this module through Streamlit from the project console script."""
    from streamlit.web import cli as streamlit_cli

    sys.argv = [
        "streamlit",
        "run",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        str(Path(__file__).resolve()),
        *sys.argv[1:],
    ]
    raise SystemExit(streamlit_cli.main())


def main() -> None:
    st.set_page_config(page_title="Discord Disentanglement Lab", layout="wide")
    st.title("Discord Disentanglement Lab")
    st.caption(
        "Inspeção científica de artefatos concluídos. Direct reply é referência silver "
        "parcial; ausência de reply significa relação desconhecida."
    )
    default_root = Path("data/processed/disentanglement_experiments").resolve()
    root_text = st.sidebar.text_input("Diretório dos experimentos", str(default_root))
    experiments = discover_experiments(Path(root_text))
    if not experiments:
        st.warning("Nenhum experimento com comparison.csv foi encontrado nesse diretório.")
        return
    selected_dir = Path(
        st.sidebar.selectbox(
            "Experimento",
            options=[str(path) for path in experiments],
            format_func=lambda value: Path(value).name,
        )
    )
    repository = ExperimentRepository(selected_dir)
    page = st.sidebar.radio(
        "Página",
        ("Conversation Explorer", "Overview", "Error Explorer", "Method Comparison"),
    )
    if page == "Method Comparison":
        _comparison(repository)
        return

    first_approach = repository.approach_ids[0]
    messages = repository.load_messages(first_approach)
    channel_labels = _channel_label_map(messages)

    if page == "Conversation Explorer":
        runs = [repository.load_run(item) for item in repository.approach_ids]
        silver_channels = sorted(
            runs[0].silver_projection["channel_key"].dropna().astype(str).unique()
        )
        if not silver_channels:
            st.info("O experimento não contém componentes Silver avaliáveis.")
            return
        selected_channel = st.sidebar.selectbox(
            "Canal",
            silver_channels,
            format_func=lambda value: channel_labels.get(value, value),
        )
        st.sidebar.caption("Referência disponível: direct replies do split de teste.")
        _conversation_explorer(runs, messages, selected_channel)
        return

    selected_approach = st.sidebar.selectbox("Abordagem", repository.approach_ids)
    selected_run = repository.load_run(selected_approach)
    if page == "Overview":
        overview_channels = [
            "all",
            *sorted(
                selected_run.gold_outcomes["channel_key"].dropna().astype(str).unique()
            ),
        ]
        overview_channel = st.sidebar.selectbox(
            "Canal",
            overview_channels,
            format_func=lambda value: (
                "Todos os canais" if value == "all" else channel_labels.get(value, value)
            ),
        )
        st.sidebar.selectbox("Split", ("test",), disabled=True)
        _overview(repository, selected_run, overview_channel)
        return

    channel_options = sorted(
        selected_run.gold_outcomes["channel_key"].dropna().astype(str).unique()
    )
    selected_channel = st.sidebar.selectbox(
        "Canal",
        channel_options,
        format_func=lambda value: channel_labels.get(value, value),
    )
    st.sidebar.selectbox("Split", ("test",), disabled=True)
    _errors(repository, selected_run, messages, selected_channel)


def _channel_label_map(messages: pd.DataFrame) -> dict[str, str]:
    """Map internal channel keys to readable, collision-safe labels."""
    catalog = messages[["channel_key", "channel_name"]].drop_duplicates(
        "channel_key", keep="first"
    ).copy()
    catalog["channel_key"] = catalog["channel_key"].astype(str)
    catalog["display_name"] = catalog["channel_name"].fillna("").astype(str).str.strip()
    catalog.loc[catalog["display_name"].eq(""), "display_name"] = "Canal sem nome"
    duplicate_names = catalog["display_name"].value_counts()
    return {
        row.channel_key: (
            row.display_name
            if duplicate_names[row.display_name] == 1
            else f"{row.display_name} ({row.channel_key})"
        )
        for row in catalog.itertuples(index=False)
    }


def _overview(
    repository: ExperimentRepository, run: LoadedRun, channel_key: str
) -> None:
    metrics = run.metrics
    if channel_key == "all":
        candidate = metrics["candidate_generation"]
        overall = metrics["ranking"]["overall"]
        reconstruction = metrics["conversation_reconstruction"]
    else:
        outcomes = run.gold_outcomes[run.gold_outcomes["channel_key"] == channel_key]
        ks = tuple(point["k"] for point in metrics["candidate_generation"]["candidate_recall_by_k"])
        candidate = candidate_generation_metrics(outcomes, ks=ks)
        overall = ranking_metrics(outcomes)["overall"]
        reconstruction = projected_conversation_metrics(
            run.silver_projection[run.silver_projection["channel_key"] == channel_key]
        )
    labels = (
        ("Candidate Recall", candidate["candidate_recall"]),
        ("Recall@1 overall", overall["recall_at_1"]),
        ("Recall@3 overall", overall["recall_at_3"]),
        ("Recall@5 overall", overall["recall_at_5"]),
        ("MRR overall", overall["mrr"]),
        ("ARI", reconstruction["ari"]),
        ("B-Cubed F1", reconstruction["bcubed_f1"]),
        ("VI", reconstruction["variation_of_information"]),
        ("Fragmentation", reconstruction["fragmentation_rate"]),
        ("Merge", reconstruction["merge_rate"]),
    )
    columns = st.columns(5)
    for index, (label, value) in enumerate(labels):
        columns[index % 5].metric(label, _format_metric(value))

    left, right = st.columns(2)
    curve = pd.DataFrame(candidate["candidate_recall_by_k"])
    with left:
        st.subheader("Candidate Recall por K")
        figure, axis = plt.subplots()
        axis.plot(curve["k"], curve["candidate_recall"], marker="o")
        axis.set(xlabel="K candidatos", ylabel="Candidate Recall", ylim=(0, 1))
        axis.grid(alpha=0.25)
        st.pyplot(figure)
        plt.close(figure)
    with right:
        st.subheader("MRR overall por abordagem")
        comparison = repository.comparison
        mrr_error = _comparison_errors(repository, "mrr_overall", "mrr_overall")
        figure, axis = plt.subplots()
        axis.bar(
            comparison["approach_id"],
            comparison["mrr_overall"],
            yerr=mrr_error,
            capsize=4,
        )
        axis.set(ylabel="MRR overall", ylim=(0, 1))
        axis.tick_params(axis="x", rotation=30)
        st.pyplot(figure)
        plt.close(figure)

    st.subheader("Recall@1 global por distância do parent")
    difficulty = pd.DataFrame(metrics["stratified"]["parent_distance"])
    figure, axis = plt.subplots(figsize=(8, 3.5))
    axis.bar(difficulty["stratum"], difficulty["recall_at_1_overall"])
    axis.set(xlabel="Distância em mensagens", ylabel="Recall@1 overall", ylim=(0, 1))
    st.pyplot(figure)
    plt.close(figure)

    st.subheader("Auditoria e proveniência")
    audit = run.manifest.get("leakage_audit", {})
    st.json(
        {
            "leakage_audit": audit.get("status", "UNKNOWN"),
            "implementation_type": run.manifest["approach"]["implementation_type"],
            "dataset_hash": run.manifest["input"].get("dataset_file_sha256"),
            "candidate_fingerprint": run.manifest["common_candidate_protocol"][
                "candidate_fingerprint"
            ],
            "reference": "partial_silver_explicit_discord_replies",
        }
    )


def _conversation_explorer(
    runs: list[LoadedRun],
    messages: pd.DataFrame,
    channel_key: str,
) -> None:
    st.header("Reconstrução de uma conversa Silver")
    st.info(
        "Escolha uma conversa formada por direct replies. Ela será o objetivo inicial "
        "de reconstrução para todas as abordagens. A ausência de direct_reply continua "
        "sendo relação desconhecida, não evidência negativa."
    )
    reference_run = runs[0]
    catalog = _silver_thread_catalog(reference_run, messages, channel_key)
    if catalog.empty:
        st.warning("Este canal não possui uma conversa Silver avaliável no teste.")
        return

    labels = catalog.set_index("silver_thread_id")["display_label"].to_dict()
    selected_silver_thread = st.selectbox(
        "Conversa Silver — objetivo de reconstrução",
        catalog["silver_thread_id"].tolist(),
        format_func=lambda value: labels.get(value, value),
    )
    silver = _silver_conversations(
        reference_run, messages, messages, selected_silver_thread
    )

    st.subheader("1. Referência Silver")
    st.caption(
        "Estas mensagens são conectadas por respostas explícitas do Discord. "
        "Elas formam o padrão positivo que cada abordagem deve tentar preservar."
    )
    _render_conversations(silver, "Objetivo Silver", selected_silver_thread)

    st.subheader("2. Proximidade das abordagens")
    summaries = [
        _silver_alignment_summary(run, selected_silver_thread) for run in runs
    ]
    _render_silver_alignment(summaries)
    _render_direct_reply_matrix(runs, messages, selected_silver_thread)

    st.subheader("3. Threads reconstruídas e mensagens sugeridas")
    st.caption(
        "🟩 pertence à referência Silver · 🟨 foi acrescentada pela abordagem · "
        "✅ preservou o pai explícito · ⚠ escolheu outro pai."
    )
    for index, (run, summary) in enumerate(zip(runs, summaries, strict=True)):
        _render_approach_reconstruction(
            run,
            messages,
            selected_silver_thread,
            summary,
            silver,
            expanded=index == 0,
        )


def _errors(
    repository: ExperimentRepository,
    run: LoadedRun,
    messages: pd.DataFrame,
    channel_key: str,
) -> None:
    st.header("Error Explorer")
    outcomes = run.gold_outcomes[run.gold_outcomes["channel_key"] == channel_key].copy()
    best = run.ranked_candidates[run.ranked_candidates["rank_position"] == 1][
        ["source_message_id", "score"]
    ].rename(columns={"score": "top_score"})
    outcomes = outcomes.merge(best, on="source_message_id", how="left", validate="one_to_one")
    projected = run.silver_projection[
        ["message_id", "silver_thread_id", "predicted_thread_id"]
    ].rename(columns={"message_id": "source_message_id"})
    outcomes = outcomes.merge(projected, on="source_message_id", how="left")
    outcomes["error_type"] = "correct"
    outcomes.loc[~outcomes["candidate_available"], "error_type"] = "parent_absent"
    outcomes.loc[
        outcomes["candidate_available"] & outcomes["rank_position"].gt(1), "error_type"
    ] = "ranked_incorrectly"
    fragmentation_ids = set(
        run.silver_projection.groupby("silver_thread_id")["predicted_thread_id"]
        .nunique()
        .loc[lambda values: values > 1]
        .index.astype(str)
    )
    merge_ids = set(
        run.silver_projection.groupby("predicted_thread_id")["silver_thread_id"]
        .nunique()
        .loc[lambda values: values > 1]
        .index.astype(str)
    )
    error_type = st.selectbox(
        "Caso",
        (
            "all",
            "parent_absent",
            "ranked_incorrectly",
            "high_confidence_wrong",
            "long_distance",
            "fragmentation",
            "merge",
            "correct",
        ),
    )
    if error_type == "long_distance":
        outcomes = outcomes[outcomes["message_distance"] > 20]
    elif error_type == "high_confidence_wrong":
        threshold = float(outcomes["top_score"].quantile(0.90)) if len(outcomes) else 1.0
        outcomes = outcomes[
            outcomes["candidate_available"]
            & outcomes["rank_position"].gt(1)
            & outcomes["top_score"].ge(threshold)
        ]
    elif error_type == "fragmentation":
        outcomes = outcomes[outcomes["silver_thread_id"].astype(str).isin(fragmentation_ids)]
    elif error_type == "merge":
        outcomes = outcomes[outcomes["predicted_thread_id"].astype(str).isin(merge_ids)]
    elif error_type != "all":
        outcomes = outcomes[outcomes["error_type"] == error_type]
    max_distance = int(max(1, outcomes["message_distance"].max())) if len(outcomes) else 1
    distance_range = st.slider("Parent distance", 1, max_distance, (1, max_distance))
    outcomes = outcomes[outcomes["message_distance"].between(*distance_range)]
    max_gap = int(max(1, outcomes["time_gap_seconds"].max())) if len(outcomes) else 1
    time_range = st.slider("Time gap (seconds)", 0, max_gap, (0, max_gap))
    outcomes = outcomes[outcomes["time_gap_seconds"].between(*time_range)]
    st.dataframe(outcomes, width="stretch", hide_index=True)
    if outcomes.empty:
        return
    source_id = st.selectbox("Inspecionar caso", outcomes["source_message_id"].astype(str))
    st.dataframe(
        repository.link_inspector(run, messages, source_id, top_k=10),
        width="stretch",
        hide_index=True,
    )


def _comparison(repository: ExperimentRepository) -> None:
    st.header("Method Comparison")
    columns = [
        "approach_id",
        "implementation_type",
        "candidate_recall",
        "recall_at_1_overall",
        "recall_at_5_overall",
        "mrr_overall",
        "mrr_conditional",
        "ari",
        "bcubed_f1",
        "variation_of_information",
        "fragmentation_rate",
        "merge_rate",
    ]
    comparison = repository.comparison[columns]
    st.dataframe(comparison, width="stretch", hide_index=True)
    mrr_error = _comparison_errors(repository, "mrr_overall", "mrr_overall")
    bcubed_error = _comparison_errors(repository, "bcubed_f1", "bcubed_f1")
    figure, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].bar(
        comparison["approach_id"], comparison["mrr_overall"], yerr=mrr_error, capsize=4
    )
    axes[0].set(title="Parent ranking", ylabel="MRR overall", ylim=(0, 1))
    axes[1].bar(
        comparison["approach_id"],
        comparison["bcubed_f1"],
        yerr=bcubed_error,
        capsize=4,
    )
    axes[1].set(title="Conversation reconstruction", ylabel="B-Cubed F1", ylim=(0, 1))
    for axis in axes:
        axis.tick_params(axis="x", rotation=35)
    figure.tight_layout()
    st.pyplot(figure)
    plt.close(figure)


def _silver_thread_catalog(
    run: LoadedRun,
    messages: pd.DataFrame,
    channel_key: str,
) -> pd.DataFrame:
    projection = run.silver_projection.loc[
        run.silver_projection["channel_key"].astype(str).eq(str(channel_key)),
        ["message_id", "silver_thread_id"],
    ].drop_duplicates("message_id").copy()
    if projection.empty:
        return pd.DataFrame()
    projection["message_id"] = projection["message_id"].astype(str)
    context = messages[
        ["message_id", "timestamp", "author_anon", "content_normalized"]
    ].drop_duplicates("message_id").copy()
    context["message_id"] = context["message_id"].astype(str)
    joined = projection.merge(context, on="message_id", how="inner").sort_values(
        ["timestamp", "message_id"], kind="stable"
    )
    rows: list[dict[str, Any]] = []
    for silver_thread_id, component in joined.groupby("silver_thread_id", sort=False):
        first = component.iloc[0]
        preview = " ".join(str(first["content_normalized"]).split())
        if len(preview) > 90:
            preview = f"{preview[:87]}..."
        rows.append(
            {
                "silver_thread_id": str(silver_thread_id),
                "message_count": int(len(component)),
                "participant_count": int(component["author_anon"].nunique()),
                "start_timestamp": first["timestamp"],
                "display_label": (
                    f"{len(component)} mensagens · "
                    f"{component['author_anon'].nunique()} participantes · "
                    f"{first['timestamp']:%Y-%m-%d %H:%M} · {preview} · "
                    f"[{str(silver_thread_id).removeprefix('SILVER_')}]"
                ),
            }
        )
    return pd.DataFrame.from_records(rows).sort_values(
        ["message_count", "start_timestamp", "silver_thread_id"],
        ascending=[False, True, True],
        kind="stable",
    ).reset_index(drop=True)


def _silver_conversations(
    run: LoadedRun,
    messages: pd.DataFrame,
    window: pd.DataFrame,
    selected_thread: str = "all",
) -> pd.DataFrame:
    """Return each Silver message once, grouped by its complete component.

    ``all`` keeps the current chronological window manageable. Selecting a component
    deliberately expands beyond that window so the user can inspect the complete
    evaluable Silver conversation.
    """
    projection = run.silver_projection[
        ["message_id", "silver_thread_id"]
    ].drop_duplicates("message_id").copy()
    projection["message_id"] = projection["message_id"].astype(str)
    projection["silver_thread_id"] = projection["silver_thread_id"].astype(str)
    if selected_thread == "all":
        ids = set(window["message_id"].astype(str))
        projection = projection[projection["message_id"].isin(ids)]
    else:
        projection = projection[
            projection["silver_thread_id"].eq(str(selected_thread))
        ]

    parents = (
        run.gold_outcomes[
            ["source_message_id", "silver_parent_message_id"]
        ]
        .drop_duplicates("source_message_id")
        .rename(
            columns={
                "source_message_id": "message_id",
                "silver_parent_message_id": "parent_message_id",
            }
        )
    )
    parents["message_id"] = parents["message_id"].astype(str)
    parents["parent_message_id"] = parents["parent_message_id"].astype(str)
    frame = projection.merge(parents, on="message_id", how="left")
    frame["score"] = pd.NA
    return _attach_conversation_messages(frame, messages, "silver_thread_id")


def _predicted_conversations(
    run: LoadedRun,
    messages: pd.DataFrame,
    window: pd.DataFrame,
    selected_thread: str = "all",
) -> pd.DataFrame:
    """Return each predicted message once, grouped by predicted thread.

    A selected thread is expanded to all of its messages, including ancestors outside
    the current window or split. This avoids presenting a complete artifact as a set
    of disconnected parent-child cards.
    """
    assignments = run.assignments[
        [
            "message_id",
            "predicted_thread_id",
            "predicted_parent_message_id",
            "predicted_parent_score",
        ]
    ].drop_duplicates("message_id").copy()
    assignments["message_id"] = assignments["message_id"].astype(str)
    assignments["predicted_thread_id"] = assignments[
        "predicted_thread_id"
    ].astype(str)
    if selected_thread == "all":
        ids = set(window["message_id"].astype(str))
        assignments = assignments[assignments["message_id"].isin(ids)]
    else:
        assignments = assignments[
            assignments["predicted_thread_id"].eq(str(selected_thread))
        ]
    assignments.rename(
        columns={
            "predicted_parent_message_id": "parent_message_id",
            "predicted_parent_score": "score",
        },
        inplace=True,
    )
    return _attach_conversation_messages(
        assignments, messages, "predicted_thread_id"
    )


def _predicted_thread_ids_for_silver(
    run: LoadedRun, silver_thread_id: str
) -> list[str]:
    component_ids = set(
        run.silver_projection.loc[
            run.silver_projection["silver_thread_id"].astype(str).eq(
                str(silver_thread_id)
            ),
            "message_id",
        ].astype(str)
    )
    related = run.assignments.loc[
        run.assignments["message_id"].astype(str).isin(component_ids),
        "predicted_thread_id",
    ].dropna().astype(str)
    counts = related.value_counts()
    return sorted(counts.index.tolist(), key=lambda item: (-int(counts[item]), item))


def _predicted_conversations_for_silver(
    run: LoadedRun,
    messages: pd.DataFrame,
    silver_thread_id: str,
) -> pd.DataFrame:
    related_threads = _predicted_thread_ids_for_silver(run, silver_thread_id)
    assignments = run.assignments.loc[
        run.assignments["predicted_thread_id"].astype(str).isin(related_threads),
        [
            "message_id",
            "predicted_thread_id",
            "predicted_parent_message_id",
            "predicted_parent_score",
        ],
    ].drop_duplicates("message_id").copy()
    assignments["message_id"] = assignments["message_id"].astype(str)
    assignments["predicted_thread_id"] = assignments[
        "predicted_thread_id"
    ].astype(str)
    assignments.rename(
        columns={
            "predicted_parent_message_id": "parent_message_id",
            "predicted_parent_score": "score",
        },
        inplace=True,
    )
    return _attach_conversation_messages(
        assignments, messages, "predicted_thread_id"
    )


def _silver_alignment_summary(
    run: LoadedRun, silver_thread_id: str
) -> dict[str, Any]:
    component_ids = set(
        run.silver_projection.loc[
            run.silver_projection["silver_thread_id"].astype(str).eq(
                str(silver_thread_id)
            ),
            "message_id",
        ].astype(str)
    )
    assignments = run.assignments.copy()
    assignments["message_id"] = assignments["message_id"].astype(str)
    component_assignments = assignments[
        assignments["message_id"].isin(component_ids)
    ].copy()
    predicted_counts = (
        component_assignments["predicted_thread_id"].dropna().astype(str).value_counts()
    )
    if predicted_counts.empty:
        dominant_thread = None
        preserved = 0
        fragment_count = 0
        dominant_thread_size = 0
        extra_messages = 0
    else:
        dominant_thread = sorted(
            predicted_counts.index,
            key=lambda item: (-int(predicted_counts[item]), str(item)),
        )[0]
        preserved = int(predicted_counts[dominant_thread])
        fragment_count = int(len(predicted_counts))
        dominant_ids = set(
            assignments.loc[
                assignments["predicted_thread_id"].astype(str).eq(dominant_thread),
                "message_id",
            ].astype(str)
        )
        dominant_thread_size = len(dominant_ids)
        extra_messages = len(dominant_ids - component_ids)

    silver_edges = (
        run.gold_outcomes.loc[
            run.gold_outcomes["source_message_id"].astype(str).isin(component_ids),
            ["source_message_id", "silver_parent_message_id"],
        ]
        .drop_duplicates("source_message_id")
        .rename(columns={"silver_parent_message_id": "target_message_id"})
        .copy()
    )
    predicted_parent = {
        str(row.message_id): (
            None
            if pd.isna(row.predicted_parent_message_id)
            else str(row.predicted_parent_message_id)
        )
        for row in component_assignments.itertuples(index=False)
    }
    exact_links = sum(
        predicted_parent.get(str(edge.source_message_id))
        == str(edge.target_message_id)
        for edge in silver_edges.itertuples(index=False)
    )
    silver_message_count = len(component_ids)
    silver_link_count = len(silver_edges)
    preservation_rate = (
        preserved / silver_message_count if silver_message_count else None
    )
    overlap_precision = (
        preserved / dominant_thread_size if dominant_thread_size else None
    )
    overlap_f1 = (
        2 * preservation_rate * overlap_precision
        / (preservation_rate + overlap_precision)
        if preservation_rate is not None
        and overlap_precision is not None
        and preservation_rate + overlap_precision
        else None
    )
    return {
        "approach_id": run.approach_id,
        "silver_messages": silver_message_count,
        "predicted_fragments": fragment_count,
        "dominant_thread": dominant_thread,
        "dominant_thread_size": dominant_thread_size,
        "messages_preserved": preserved,
        "preservation_rate": preservation_rate,
        "overlap_precision": overlap_precision,
        "overlap_f1": overlap_f1,
        "extra_messages": extra_messages,
        "exact_links": exact_links,
        "silver_links": silver_link_count,
        "exact_link_recall": exact_links / silver_link_count if silver_link_count else None,
    }


def _render_silver_alignment(summaries: list[dict[str, Any]]) -> None:
    rows = []
    for item in summaries:
        preservation = item["preservation_rate"]
        link_recall = item["exact_link_recall"]
        overlap_f1 = item["overlap_f1"]
        rows.append(
            {
                "Abordagem": item["approach_id"],
                "Threads usadas": item["predicted_fragments"],
                "Silver preservado": (
                    f"{item['messages_preserved']}/{item['silver_messages']} "
                    f"({preservation:.1%})"
                    if preservation is not None
                    else "N/A"
                ),
                "Direct replies exatos": (
                    f"{item['exact_links']}/{item['silver_links']} "
                    f"({link_recall:.1%})"
                    if link_recall is not None
                    else "N/A"
                ),
                "Mensagens sugeridas": item["extra_messages"],
                "F1 de sobreposição": (
                    f"{overlap_f1:.1%}" if overlap_f1 is not None else "N/A"
                ),
                "Thread principal": item["dominant_thread"] or "N/A",
            }
        )
    st.dataframe(pd.DataFrame.from_records(rows), hide_index=True, width="stretch")
    st.caption(
        "O ideal inicial é: uma única thread, 100% das mensagens Silver preservadas "
        "e todos os pais explícitos recuperados. O F1 de sobreposição compara o "
        "conjunto Silver com a thread principal; mensagens sugeridas continuam sem "
        "rótulo e não são tratadas automaticamente como erros."
    )


def _render_direct_reply_matrix(
    runs: list[LoadedRun],
    messages: pd.DataFrame,
    silver_thread_id: str,
) -> None:
    component_ids = set(
        runs[0].silver_projection.loc[
            runs[0].silver_projection["silver_thread_id"].astype(str).eq(
                str(silver_thread_id)
            ),
            "message_id",
        ].astype(str)
    )
    edges = (
        runs[0].gold_outcomes.loc[
            runs[0].gold_outcomes["source_message_id"].astype(str).isin(
                component_ids
            ),
            ["source_message_id", "silver_parent_message_id"],
        ]
        .drop_duplicates("source_message_id")
        .rename(columns={"silver_parent_message_id": "target_message_id"})
        .copy()
    )
    if edges.empty:
        return
    lookup = messages.set_index(messages["message_id"].astype(str))
    predicted_by_run: dict[str, dict[str, str | None]] = {}
    for run in runs:
        predicted_by_run[run.approach_id] = {
            str(row.message_id): (
                None
                if pd.isna(row.predicted_parent_message_id)
                else str(row.predicted_parent_message_id)
            )
            for row in run.assignments.itertuples(index=False)
        }
    rows = []
    for edge in edges.itertuples(index=False):
        source_id = str(edge.source_message_id)
        silver_parent = str(edge.target_message_id)
        source = lookup.loc[source_id]
        preview = " ".join(str(source["content_normalized"]).split())
        if len(preview) > 80:
            preview = f"{preview[:77]}..."
        row: dict[str, Any] = {
            "Mensagem": source_id,
            "Trecho": preview,
            "Pai Silver": silver_parent,
        }
        for run in runs:
            predicted_parent = predicted_by_run[run.approach_id].get(source_id)
            row[run.approach_id] = (
                "✅ exato"
                if predicted_parent == silver_parent
                else f"⚠ {predicted_parent or 'nova thread'}"
            )
        rows.append(row)
    with st.expander("Comparação vínculo a vínculo dos direct replies"):
        st.dataframe(pd.DataFrame.from_records(rows), hide_index=True, width="stretch")


def _render_approach_reconstruction(
    run: LoadedRun,
    messages: pd.DataFrame,
    silver_thread_id: str,
    summary: dict[str, Any],
    silver: pd.DataFrame,
    *,
    expanded: bool,
) -> None:
    preservation = summary["preservation_rate"]
    link_recall = summary["exact_link_recall"]
    overlap_f1 = summary["overlap_f1"]
    label = (
        f"{run.approach_id} · "
        f"Silver {summary['messages_preserved']}/{summary['silver_messages']} · "
        f"replies {summary['exact_links']}/{summary['silver_links']} · "
        f"{summary['predicted_fragments']} thread(s) · "
        f"{summary['extra_messages']} sugerida(s)"
    )
    with st.expander(label, expanded=expanded):
        metrics = st.columns(4)
        metrics[0].metric(
            "Silver preservado",
            f"{preservation:.1%}" if preservation is not None else "N/A",
        )
        metrics[1].metric(
            "Direct replies exatos",
            f"{link_recall:.1%}" if link_recall is not None else "N/A",
        )
        metrics[2].metric("Threads usadas", summary["predicted_fragments"])
        metrics[3].metric(
            "F1 de sobreposição",
            f"{overlap_f1:.1%}" if overlap_f1 is not None else "N/A",
        )
        reference_column, prediction_column = st.columns(2)
        with reference_column:
            st.markdown("#### Objetivo Silver")
            _render_conversation_messages(silver)
        with prediction_column:
            st.markdown(f"#### Reconstrução — {run.approach_id}")
            predicted = _predicted_conversations_for_silver(
                run, messages, silver_thread_id
            )
            _render_annotated_reconstruction(
                run,
                predicted,
                silver_thread_id,
                summary["dominant_thread"],
            )


def _render_annotated_reconstruction(
    run: LoadedRun,
    predicted: pd.DataFrame,
    silver_thread_id: str,
    dominant_thread: str | None,
) -> None:
    component_ids = set(
        run.silver_projection.loc[
            run.silver_projection["silver_thread_id"].astype(str).eq(
                str(silver_thread_id)
            ),
            "message_id",
        ].astype(str)
    )
    silver_parents = {
        str(row.source_message_id): str(row.silver_parent_message_id)
        for row in run.gold_outcomes.loc[
            run.gold_outcomes["source_message_id"].astype(str).isin(
                component_ids
            ),
            ["source_message_id", "silver_parent_message_id"],
        ].drop_duplicates("source_message_id").itertuples(index=False)
    }
    if predicted.empty:
        st.warning("A abordagem não atribuiu as mensagens Silver a uma thread.")
        return
    groups = list(predicted.groupby("thread_id", sort=False))
    groups.sort(key=lambda item: (str(item[0]) != str(dominant_thread), str(item[0])))
    for thread_id, conversation in groups:
        conversation = conversation.sort_values(
            ["timestamp", "message_id"], kind="stable"
        )
        thread_ids = set(conversation["message_id"].astype(str))
        silver_count = len(thread_ids & component_ids)
        extra_count = len(thread_ids - component_ids)
        role = "thread principal" if str(thread_id) == str(dominant_thread) else "fragmento"
        st.markdown(
            f"##### {role}: `{thread_id}`  \n"
            f"{silver_count} Silver · {extra_count} sugeridas · "
            f"{len(conversation)} mensagens no total"
        )
        for position, row in enumerate(conversation.itertuples(index=False), start=1):
            message_id = str(row.message_id)
            predicted_parent = (
                None if pd.isna(row.parent_message_id) else str(row.parent_message_id)
            )
            is_silver = message_id in component_ids
            badge = "🟩 SILVER" if is_silver else "🟨 SUGERIDA"
            st.markdown(
                f"**{badge} · {position:02d} · {row.timestamp:%Y-%m-%d %H:%M:%S} "
                f"· {row.author_anon}** `{message_id}`  \n"
                f"{row.content_normalized}"
            )
            silver_parent = silver_parents.get(message_id)
            score = getattr(row, "score", None)
            score_text = f" · score {float(score):.4f}" if pd.notna(score) else ""
            if silver_parent:
                relation = (
                    f"✅ direct_reply preservado: `{silver_parent}`"
                    if predicted_parent == silver_parent
                    else f"⚠ pai Silver `{silver_parent}` · pai previsto "
                    f"`{predicted_parent or 'nova thread'}`"
                )
            elif is_silver:
                relation = (
                    "raiz do componente Silver"
                    if not predicted_parent
                    else f"raiz Silver ligada pelo modelo a `{predicted_parent}`"
                )
            else:
                relation = f"sugerida como continuação de `{predicted_parent or 'nova thread'}`"
            st.caption(f"{relation}{score_text}")


def _attach_conversation_messages(
    membership: pd.DataFrame,
    messages: pd.DataFrame,
    thread_column: str,
) -> pd.DataFrame:
    message_columns = [
        "message_id",
        "timestamp",
        "author_anon",
        "content_normalized",
        "split",
    ]
    available = [column for column in message_columns if column in messages.columns]
    message_context = messages[available].drop_duplicates("message_id").copy()
    message_context["message_id"] = message_context["message_id"].astype(str)
    frame = membership.merge(message_context, on="message_id", how="inner")
    frame.rename(columns={thread_column: "thread_id"}, inplace=True)
    if "parent_message_id" not in frame:
        frame["parent_message_id"] = pd.NA
    if "score" not in frame:
        frame["score"] = pd.NA
    return frame.sort_values(
        ["timestamp", "message_id"], kind="stable"
    ).reset_index(drop=True)


def _render_messages(messages: pd.DataFrame) -> None:
    for row in messages.itertuples(index=False):
        st.markdown(
            f"**{row.timestamp:%Y-%m-%d %H:%M:%S} · {row.author_anon}**  \n"
            f"{row.content_normalized}"
        )


def _render_conversations(
    conversations: pd.DataFrame,
    title: str,
    selected_thread: str = "all",
) -> None:
    st.markdown(f"**{title}**")
    if conversations.empty:
        st.caption("Nenhuma conversa observada nesse recorte.")
        return
    grouped = list(conversations.groupby("thread_id", sort=False))
    if selected_thread == "all":
        st.caption(
            "Cada cartão é uma conversa. Selecione uma thread acima para expandi-la "
            "completa, inclusive fora da janela atual."
        )
    for group_index, (thread_id, conversation) in enumerate(grouped):
        conversation = conversation.sort_values(
            ["timestamp", "message_id"], kind="stable"
        )
        participant_count = conversation["author_anon"].nunique()
        label = (
            f"{thread_id} · {len(conversation)} mensagens · "
            f"{participant_count} participantes"
        )
        expand = selected_thread != "all" or len(grouped) == 1 or group_index == 0
        with st.expander(label, expanded=expand):
            _render_conversation_messages(conversation)


def _render_conversation_messages(conversation: pd.DataFrame) -> None:
    ids = set(conversation["message_id"].astype(str))
    parent_by_message = {
        str(row.message_id): (
            None if pd.isna(row.parent_message_id) else str(row.parent_message_id)
        )
        for row in conversation.itertuples(index=False)
    }
    depth_cache: dict[str, int] = {}

    def depth(message_id: str, visiting: set[str] | None = None) -> int:
        if message_id in depth_cache:
            return depth_cache[message_id]
        active = set() if visiting is None else set(visiting)
        if message_id in active:
            return 0
        active.add(message_id)
        parent_id = parent_by_message.get(message_id)
        value = 0 if not parent_id or parent_id not in ids else 1 + depth(parent_id, active)
        depth_cache[message_id] = value
        return value

    for position, row in enumerate(conversation.itertuples(index=False), start=1):
        message_id = str(row.message_id)
        parent_id = parent_by_message.get(message_id)
        relation = "início da conversa"
        if parent_id:
            relation = (
                f"continua `{parent_id}`"
                if parent_id in ids
                else f"pai `{parent_id}` fora do recorte exibido"
            )
        score = getattr(row, "score", None)
        if pd.notna(score):
            relation += f" · score {float(score):.4f}"
        split = f" · {row.split}" if hasattr(row, "split") else ""
        branch = "↳ " * min(depth(message_id), 8)
        st.markdown(
            f"{branch}**{position:02d} · {row.timestamp:%Y-%m-%d %H:%M:%S} "
            f"· {row.author_anon}** `{message_id}`{split}  \n"
            f"{row.content_normalized}"
        )
        st.caption(relation)


def _format_metric(value: Any) -> str:
    return "N/A" if value is None or pd.isna(value) else f"{float(value):.4f}"


def _comparison_errors(
    repository: ExperimentRepository, interval_name: str, value_column: str
) -> list[list[float]]:
    lower_errors: list[float] = []
    upper_errors: list[float] = []
    values = repository.comparison.set_index("approach_id")[value_column]
    for approach_id in repository.approach_ids:
        interval = repository.load_run(approach_id).metrics["statistics"]["intervals"][
            interval_name
        ]
        estimate = float(values.loc[approach_id])
        lower = interval.get("lower")
        upper = interval.get("upper")
        lower_errors.append(max(0.0, estimate - float(lower)) if lower is not None else 0.0)
        upper_errors.append(max(0.0, float(upper) - estimate) if upper is not None else 0.0)
    return [lower_errors, upper_errors]


if __name__ == "__main__":
    main()
