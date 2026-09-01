"""Avaliação comum: candidatos, ranking, reconstrução silver e estatística."""

from .clustering import projected_conversation_metrics, silver_projection
from .leakage import LeakageAuditError, audit_prediction_inputs
from .ranking import candidate_generation_metrics, ranking_metrics, stratified_metrics
from .statistics import bootstrap_confidence_interval, paired_bootstrap_difference

__all__ = [
    "LeakageAuditError",
    "audit_prediction_inputs",
    "bootstrap_confidence_interval",
    "paired_bootstrap_difference",
    "candidate_generation_metrics",
    "projected_conversation_metrics",
    "ranking_metrics",
    "silver_projection",
    "stratified_metrics",
]
