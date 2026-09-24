"""Content-addressed IEC stage receipts with explicit zero-DO authority."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .model import digest


class IECStage(str, Enum):
    CORPUS_FREEZE = "CORPUS_FREEZE"
    OBSERVE = "OBSERVE"
    CORRESPONDENCE = "CORRESPONDENCE"
    GENERALIZE = "GENERALIZE"
    VALIDATE = "VALIDATE"
    RETIRE_REASONING = "RETIRE_REASONING"
    PROMOTE_INTENT = "PROMOTE_INTENT"


@dataclass(frozen=True, slots=True)
class IECReceipt:
    stage: IECStage
    subject_ids: tuple[str, ...]
    input_ids: tuple[str, ...]
    output_ids: tuple[str, ...]
    result: str
    verifier_ids: tuple[str, ...] = ()
    previous_receipt: str | None = None
    authority: str = "NONE"
    external_consequence: bool = False

    def __post_init__(self) -> None:
        if self.authority != "NONE":
            raise ValueError("IEC receipts cannot carry external authority")
        if self.external_consequence:
            raise ValueError("IEC receipt cannot certify an external consequence")
        if not self.result.strip():
            raise ValueError("result must be non-empty")

    @property
    def receipt_id(self) -> str:
        return digest(self)


class ReceiptChain:
    """Small append-only chain for replay identity."""

    def __init__(self) -> None:
        self._receipts: list[IECReceipt] = []

    def append(
        self,
        *,
        stage: IECStage,
        subject_ids: tuple[str, ...],
        input_ids: tuple[str, ...],
        output_ids: tuple[str, ...],
        result: str,
        verifier_ids: tuple[str, ...] = (),
    ) -> IECReceipt:
        previous = self._receipts[-1].receipt_id if self._receipts else None
        receipt = IECReceipt(
            stage=stage,
            subject_ids=tuple(sorted(set(subject_ids))),
            input_ids=tuple(sorted(set(input_ids))),
            output_ids=tuple(sorted(set(output_ids))),
            result=result,
            verifier_ids=tuple(sorted(set(verifier_ids))),
            previous_receipt=previous,
        )
        self._receipts.append(receipt)
        return receipt

    def verify(self) -> bool:
        previous = None
        for receipt in self._receipts:
            if receipt.previous_receipt != previous:
                return False
            previous = receipt.receipt_id
        return True

    def receipts(self) -> tuple[IECReceipt, ...]:
        return tuple(self._receipts)
