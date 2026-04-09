from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


ColorSchemeName = Literal["spectrum", "mono", "fire", "ice"]


@dataclass(slots=True)
class AppConfig:
    fps: int = 30
    bars: int | None = None
    color: ColorSchemeName = "spectrum"
    sensitivity: float = 1.0
    no_color: bool = False
    frame_samples: int = 1024
    sample_rate: int = 48_000
    smoothing: float = 0.3
    peak_decay: float = 0.985
    startup_timeout: float = 5.0
    queue_size: int = 8
