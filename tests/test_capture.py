from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from termviz.capture import PCMFrameAssembler, parse_helper_event, resolve_helper_executable


def test_pcm_frame_assembler_handles_partial_chunks() -> None:
    assembler = PCMFrameAssembler(frame_samples=4)
    partial = np.array([1.0, 2.0], dtype="<f4").tobytes()
    complete = np.array([3.0, 4.0, 5.0, 6.0], dtype="<f4").tobytes()
    assert assembler.push(partial) == []
    frames = assembler.push(complete)
    assert len(frames) == 1
    assert np.allclose(frames[0], np.array([1.0, 2.0, 3.0, 4.0], dtype=np.float32))


def test_parse_helper_event_accepts_json() -> None:
    event = parse_helper_event(json.dumps({"event": "ready", "message": "ok", "sample_rate": 48_000}))
    assert event.event == "ready"
    assert event.payload["sample_rate"] == 48_000


def test_parse_helper_event_falls_back_to_log() -> None:
    event = parse_helper_event("plain text")
    assert event.event == "log"
    assert event.message == "plain text"


def test_resolve_helper_prefers_env(monkeypatch: object, tmp_path: Path) -> None:
    helper = tmp_path / "termviz-helper"
    helper.write_text("", encoding="utf-8")
    monkeypatch.setenv("TERMVIZ_HELPER_PATH", str(helper))
    assert resolve_helper_executable() == helper
