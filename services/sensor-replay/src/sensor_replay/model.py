from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ImuSample:
    source_timestamp: str
    source_time: datetime
    sample_index: int
    acc_x_mg: int
    acc_y_mg: int
    acc_z_mg: int

    def as_payload(self) -> dict[str, int | str]:
        return {
            "source_timestamp": self.source_timestamp,
            "sample_index": self.sample_index,
            "acc_x_mg": self.acc_x_mg,
            "acc_y_mg": self.acc_y_mg,
            "acc_z_mg": self.acc_z_mg,
        }
