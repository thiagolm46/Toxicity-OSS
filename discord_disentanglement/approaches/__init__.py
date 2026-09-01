from __future__ import annotations

from collections.abc import Callable

from .base import (
    ApproachContractError,
    ApproachFitData,
    ApproachReference,
    ApproachScore,
    DisentanglementApproach,
)
from .co_training import UnsupervisedCoTrainingApproach
from .chi_zero_shot import ChiZeroShotAdapter
from .irc_transfer import IrcTransferAdapter
from .weak_supervision import WeakSupervisionPairwiseRankerApproach
from .zero_shot import ZeroShotResponseSelectionApproach


APPROACH_FACTORIES: dict[str, Callable[[], DisentanglementApproach]] = {
    ZeroShotResponseSelectionApproach.approach_id: ZeroShotResponseSelectionApproach,
    UnsupervisedCoTrainingApproach.approach_id: UnsupervisedCoTrainingApproach,
    WeakSupervisionPairwiseRankerApproach.approach_id: WeakSupervisionPairwiseRankerApproach,
    ChiZeroShotAdapter.approach_id: ChiZeroShotAdapter,
    IrcTransferAdapter.approach_id: IrcTransferAdapter,
}
APPROACH_IDS: tuple[str, ...] = tuple(APPROACH_FACTORIES)


def create_approach(
    approach_id: str, settings: dict[str, object] | None = None
) -> DisentanglementApproach:
    try:
        factory = APPROACH_FACTORIES[approach_id]
    except KeyError as error:
        raise ValueError(
            f"Abordagem desconhecida: {approach_id}. Opcoes: {', '.join(APPROACH_IDS)}"
        ) from error
    return factory(**(settings or {}))


__all__ = [
    "APPROACH_IDS",
    "ApproachContractError",
    "ApproachFitData",
    "ApproachReference",
    "ApproachScore",
    "DisentanglementApproach",
    "ChiZeroShotAdapter",
    "IrcTransferAdapter",
    "UnsupervisedCoTrainingApproach",
    "WeakSupervisionPairwiseRankerApproach",
    "ZeroShotResponseSelectionApproach",
    "create_approach",
]
