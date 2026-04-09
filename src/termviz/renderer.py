from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from blessed import Terminal

from termviz.colors import gradient_color


FULL_BLOCK = "█"
LOWER_HALF_BLOCK = "▄"


@dataclass(frozen=True, slots=True)
class RenderMetrics:
    columns: int
    rows: int
    bars: int
    bar_width: int = 2
    gap: int = 1


def compute_bar_count(columns: int, configured_bars: int | None, *, bar_width: int = 2, gap: int = 1) -> int:
    max_bars = max(1, columns // (bar_width + gap))
    if configured_bars is None:
        return max_bars
    return max(1, min(configured_bars, max_bars))


def compute_bar_units(magnitudes: Iterable[float], rows: int) -> list[int]:
    max_units = max(1, rows * 2)
    return [int(round(max(0.0, min(1.0, value)) * max_units)) for value in magnitudes]


class TerminalRenderer:
    def __init__(self, term: Terminal, color_scheme: str, *, no_color: bool = False) -> None:
        self.term = term
        self.color_scheme = color_scheme
        self.no_color = no_color or not term.does_styling

    def metrics(self, configured_bars: int | None) -> RenderMetrics:
        columns = max(1, self.term.width)
        rows = max(2, self.term.height)
        bars = compute_bar_count(columns, configured_bars)
        return RenderMetrics(columns=columns, rows=rows, bars=bars)

    def render_frame(self, magnitudes: np.ndarray, configured_bars: int | None) -> str:
        metrics = self.metrics(configured_bars)
        bars = np.zeros(metrics.bars, dtype=np.float32)
        copy_count = min(metrics.bars, magnitudes.shape[0])
        if copy_count:
            bars[:copy_count] = magnitudes[:copy_count]
        units = compute_bar_units(bars, metrics.rows)

        lines: list[str] = [self.term.home]
        for row in range(metrics.rows):
            parts: list[str] = []
            for units_for_bar in units:
                parts.append(self._cell(units_for_bar, row, metrics.rows) * metrics.bar_width)
                parts.append(" " * metrics.gap)
            lines.append("".join(parts).rstrip())
            lines.append(self.term.clear_eol)
            if row != metrics.rows - 1:
                lines.append("\n")
        lines.append(self.term.clear_eos)
        return "".join(lines)

    def _cell(self, units_for_bar: int, row: int, rows: int) -> str:
        threshold = units_for_bar - (rows - row - 1) * 2
        if threshold <= 0:
            return " "
        glyph = LOWER_HALF_BLOCK if threshold == 1 else FULL_BLOCK
        if self.no_color:
            return glyph
        color = gradient_color(self.color_scheme, 1.0 - (row / max(1, rows - 1)))
        return self.term.color_rgb(*color)(glyph)
