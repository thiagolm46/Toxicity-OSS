from types import SimpleNamespace

import pandas as pd

from discord_disentanglement.ui.app import (
    _channel_label_map,
    _predicted_conversations,
    _predicted_conversations_for_silver,
    _silver_alignment_summary,
    _silver_conversations,
    _silver_thread_catalog,
)


def _messages() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "message_id": ["a", "b", "c", "d"],
            "timestamp": pd.to_datetime(
                [
                    "2024-01-01T00:00:00Z",
                    "2024-01-01T00:01:00Z",
                    "2024-01-01T00:02:00Z",
                    "2024-01-01T00:03:00Z",
                ]
            ),
            "author_anon": ["USER_1", "USER_2", "USER_1", "USER_2"],
            "content_normalized": ["A", "B", "C", "D"],
            "split": ["train", "test", "test", "test"],
            "channel_key": ["id:1", "id:1", "id:1", "id:1"],
        }
    )


def _run() -> SimpleNamespace:
    return SimpleNamespace(
        approach_id="test_approach",
        assignments=pd.DataFrame(
            {
                "message_id": ["a", "b", "c", "d"],
                "predicted_thread_id": ["P1", "P1", "P1", "P1"],
                "predicted_parent_message_id": [None, "a", "b", "c"],
                "predicted_parent_score": [None, 0.8, 0.9, 0.7],
            }
        ),
        silver_projection=pd.DataFrame(
            {
                "message_id": ["a", "b", "c"],
                "silver_thread_id": ["S1", "S1", "S1"],
                "channel_key": ["id:1", "id:1", "id:1"],
            }
        ),
        gold_outcomes=pd.DataFrame(
            {
                "source_message_id": ["b", "c"],
                "silver_parent_message_id": ["a", "b"],
            }
        ),
        ranked_candidates=pd.DataFrame(
            {
                "source_message_id": ["c", "d"],
                "target_message_id": ["b", "a"],
                "is_silver_parent": [True, False],
            }
        ),
    )


def test_selected_predicted_thread_expands_beyond_current_window() -> None:
    messages = _messages()
    window = messages[messages["message_id"].isin(["b", "c"])]

    conversation = _predicted_conversations(_run(), messages, window, "P1")

    assert conversation["message_id"].tolist() == ["a", "b", "c", "d"]
    assert conversation["message_id"].is_unique
    assert conversation["thread_id"].unique().tolist() == ["P1"]
    assert conversation.set_index("message_id").loc["d", "parent_message_id"] == "c"


def test_all_predicted_threads_remain_bounded_to_window_without_pair_duplicates() -> None:
    messages = _messages()
    window = messages[messages["message_id"].isin(["b", "c"])]

    conversation = _predicted_conversations(_run(), messages, window, "all")

    assert conversation["message_id"].tolist() == ["b", "c"]
    assert conversation["message_id"].is_unique


def test_selected_silver_component_expands_to_complete_evaluable_conversation() -> None:
    messages = _messages()
    window = messages[messages["message_id"].eq("c")]

    conversation = _silver_conversations(_run(), messages, window, "S1")

    assert conversation["message_id"].tolist() == ["a", "b", "c"]
    assert conversation["message_id"].is_unique
    assert conversation["thread_id"].unique().tolist() == ["S1"]
    assert conversation.set_index("message_id").loc["b", "parent_message_id"] == "a"
    assert conversation.set_index("message_id").loc["c", "parent_message_id"] == "b"


def test_silver_alignment_compares_whole_component_and_exact_reply_links() -> None:
    messages = _messages()

    predicted = _predicted_conversations_for_silver(_run(), messages, "S1")
    summary = _silver_alignment_summary(_run(), "S1")

    assert predicted["message_id"].tolist() == ["a", "b", "c", "d"]
    assert predicted["message_id"].is_unique
    assert summary["silver_messages"] == 3
    assert summary["predicted_fragments"] == 1
    assert summary["messages_preserved"] == 3
    assert summary["preservation_rate"] == 1.0
    assert summary["extra_messages"] == 1
    assert summary["dominant_thread_size"] == 4
    assert summary["overlap_precision"] == 0.75
    assert summary["overlap_f1"] == 6 / 7
    assert summary["exact_links"] == 2
    assert summary["silver_links"] == 2
    assert summary["exact_link_recall"] == 1.0


def test_channel_labels_show_names_and_disambiguate_duplicates() -> None:
    messages = pd.DataFrame(
        {
            "channel_key": ["id:1", "id:2", "id:3"],
            "channel_name": ["graph-academy", "support", "support"],
        }
    )

    labels = _channel_label_map(messages)

    assert labels["id:1"] == "graph-academy"
    assert labels["id:2"] == "support (id:2)"
    assert labels["id:3"] == "support (id:3)"


def test_silver_catalog_prioritizes_complete_large_conversations() -> None:
    catalog = _silver_thread_catalog(_run(), _messages(), "id:1")

    assert catalog["silver_thread_id"].tolist() == ["S1"]
    assert catalog.iloc[0]["message_count"] == 3
    assert catalog.iloc[0]["participant_count"] == 2
    assert "3 mensagens" in catalog.iloc[0]["display_label"]
    assert "2024-01-01 00:00" in catalog.iloc[0]["display_label"]
