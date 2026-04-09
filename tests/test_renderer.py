from __future__ import annotations

import numpy as np
from termviz.renderer import FULL_BLOCK, LOWER_HALF_BLOCK, TerminalRenderer, compute_bar_count, compute_bar_units


class FakeTerminal:
    def __init__(self, width: int = 90, height: int = 20, colors: int = 256, styling: bool = True) -> None:
        self._width = width
        self._height = height
        self._colors = colors
        self._styling = styling
        self.home = ""
        self.clear_eol = "<clear_eol>"
        self.clear_eos = ""

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def number_of_colors(self) -> int:
        return self._colors

    @property
    def does_styling(self) -> bool:
        return self._styling

    def color_rgb(self, red: int, green: int, blue: int):
        def style(text: str) -> str:
            return f"<{red},{green},{blue}>{text}</>"

        return style


def test_bar_count_auto_scales_to_terminal_width() -> None:
    assert compute_bar_count(90, None) == 30
    assert compute_bar_count(90, 80) == 30
    assert compute_bar_count(90, 10) == 10


def test_bar_units_double_vertical_resolution() -> None:
    assert compute_bar_units([0.0, 0.5, 1.0], rows=10) == [0, 10, 20]


def test_renderer_outputs_blocks() -> None:
    renderer = TerminalRenderer(FakeTerminal(), "spectrum")
    frame = renderer.render_frame(np.array([0.1, 0.6, 1.0], dtype=np.float32), configured_bars=3)
    assert FULL_BLOCK in frame or LOWER_HALF_BLOCK in frame


def test_renderer_respects_no_color() -> None:
    renderer = TerminalRenderer(FakeTerminal(styling=False), "mono", no_color=True)
    frame = renderer.render_frame(np.array([1.0], dtype=np.float32), configured_bars=1)
    assert "\x1b[" not in frame


def test_renderer_recomputes_bars_for_resize() -> None:
    term = FakeTerminal(width=30, height=10)
    renderer = TerminalRenderer(term, "ice")
    assert renderer.metrics(None).bars == 10
    term._width = 60
    assert renderer.metrics(None).bars == 20


def test_renderer_clears_each_line_to_avoid_stale_bars() -> None:
    term = FakeTerminal(width=12, height=4)
    renderer = TerminalRenderer(term, "mono", no_color=True)
    frame = renderer.render_frame(np.zeros(2, dtype=np.float32), configured_bars=2)
    assert frame.count(term.clear_eol) == term.height
