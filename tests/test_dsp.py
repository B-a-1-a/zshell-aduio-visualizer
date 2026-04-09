from __future__ import annotations

import numpy as np

from termviz.dsp import SpectrumProcessor


def sine_wave(frequency: float, sample_rate: int, frame_samples: int) -> np.ndarray:
    timeline = np.arange(frame_samples, dtype=np.float32) / sample_rate
    return np.sin(2 * np.pi * frequency * timeline).astype(np.float32)


def test_silence_stays_silent() -> None:
    processor = SpectrumProcessor(sample_rate=48_000, frame_samples=1024)
    result = processor.process(np.zeros(1024, dtype=np.float32), bands=24)
    assert result.shape == (24,)
    assert np.allclose(result, 0.0)


def test_low_frequency_lights_lower_band() -> None:
    processor = SpectrumProcessor(sample_rate=48_000, frame_samples=1024, smoothing=1.0)
    frame = sine_wave(110.0, 48_000, 1024)
    result = processor.process(frame, bands=24)
    assert int(np.argmax(result)) < 8


def test_high_frequency_lights_higher_band() -> None:
    processor = SpectrumProcessor(sample_rate=48_000, frame_samples=1024, smoothing=1.0)
    frame = sine_wave(6_000.0, 48_000, 1024)
    result = processor.process(frame, bands=24)
    assert int(np.argmax(result)) > 10


def test_sensitivity_scales_output() -> None:
    processor = SpectrumProcessor(sample_rate=48_000, frame_samples=1024, smoothing=1.0)
    frame = sine_wave(440.0, 48_000, 1024) * 0.25
    low = processor.process(frame, bands=16, sensitivity=0.5)
    processor.reset()
    high = processor.process(frame, bands=16, sensitivity=2.0)
    assert float(np.max(high)) >= float(np.max(low))


def test_peak_decay_allows_recovery() -> None:
    processor = SpectrumProcessor(sample_rate=48_000, frame_samples=1024, smoothing=1.0, peak_decay=0.9)
    loud = processor.process(sine_wave(440.0, 48_000, 1024), bands=12)
    quiet = processor.process(sine_wave(440.0, 48_000, 1024) * 0.1, bands=12)
    assert float(np.max(loud)) == 1.0
    assert 0.0 < float(np.max(quiet)) < 1.0
