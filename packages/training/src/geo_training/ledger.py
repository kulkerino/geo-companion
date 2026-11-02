"""Dataset rights ledger: training reads a dataset only when its record is ``cleared``."""

from __future__ import annotations

import json
from pathlib import Path

from geo_companion.contracts import Attribution, RightsStatus
from pydantic import Field


class DatasetRecord(Attribution):
    """Provenance and rights for one training dataset, reusing the content attribution fields."""

    dataset_id: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")


class DatasetNotClearedError(PermissionError):
    """Raised when training would read a dataset that kulo has not cleared."""


def load_record(path: Path) -> DatasetRecord:
    return DatasetRecord.model_validate(json.loads(path.read_text(encoding="utf-8")))


def require_cleared(record: DatasetRecord) -> DatasetRecord:
    if record.rights_status is not RightsStatus.CLEARED:
        msg = (
            f"Dataset {record.dataset_id!r} is {record.rights_status.value}; only cleared "
            "datasets may be used for training."
        )
        raise DatasetNotClearedError(msg)
    return record
