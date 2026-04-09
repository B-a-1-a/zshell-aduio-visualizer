from __future__ import annotations

from dataclasses import dataclass


RGB = tuple[int, int, int]


@dataclass(frozen=True, slots=True)
class GradientStop:
    position: float
    color: RGB


SCHEMES: dict[str, tuple[GradientStop, ...]] = {
    "spectrum": (
        GradientStop(0.0, (33, 56, 150)),
        GradientStop(0.35, (0, 182, 210)),
        GradientStop(0.7, (152, 227, 81)),
        GradientStop(1.0, (255, 104, 31)),
    ),
    "mono": (
        GradientStop(0.0, (120, 120, 135)),
        GradientStop(1.0, (245, 245, 255)),
    ),
    "fire": (
        GradientStop(0.0, (82, 15, 15)),
        GradientStop(0.4, (191, 58, 44)),
        GradientStop(0.8, (255, 180, 0)),
        GradientStop(1.0, (255, 242, 189)),
    ),
    "ice": (
        GradientStop(0.0, (15, 50, 90)),
        GradientStop(0.4, (42, 130, 181)),
        GradientStop(0.8, (164, 235, 255)),
        GradientStop(1.0, (242, 250, 255)),
    ),
}


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def gradient_color(scheme: str, position: float) -> RGB:
    stops = SCHEMES[scheme]
    position = clamp01(position)
    if position <= stops[0].position:
        return stops[0].color
    if position >= stops[-1].position:
        return stops[-1].color

    for left, right in zip(stops, stops[1:]):
        if left.position <= position <= right.position:
            span = right.position - left.position or 1.0
            ratio = (position - left.position) / span
            return tuple(
                int(round(start + (end - start) * ratio))
                for start, end in zip(left.color, right.color)
            )
    return stops[-1].color
