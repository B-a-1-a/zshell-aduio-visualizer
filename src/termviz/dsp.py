from __future__ import annotations

from functools import lru_cache

import numpy as np
import numpy.typing as npt


class SpectrumProcessor:
    def __init__(
        self,
        sample_rate: int,
        frame_samples: int = 1024,
        smoothing: float = 0.3,
        peak_decay: float = 0.985,
    ) -> None:
        self.sample_rate = sample_rate
        self.frame_samples = frame_samples
        self.smoothing = smoothing
        self.peak_decay = peak_decay
        self.window = np.hanning(frame_samples).astype(np.float32)
        self._smoothed = np.zeros(1, dtype=np.float32)
        self._peak = 1e-6
        self._refresh_frequency_bins()

    def reset(self) -> None:
        self._smoothed = np.zeros(1, dtype=np.float32)
        self._peak = 1e-6

    def set_sample_rate(self, sample_rate: int) -> None:
        if sample_rate != self.sample_rate:
            self.sample_rate = sample_rate
            self._refresh_frequency_bins()
            self._band_edges.cache_clear()

    def band_centers(self, bands: int) -> npt.NDArray[np.float32]:
        edges = self._band_edges(bands)
        return ((edges[:-1] + edges[1:]) / 2.0).astype(np.float32)

    def process(
        self,
        frame: npt.NDArray[np.float32],
        bands: int,
        *,
        sensitivity: float = 1.0,
    ) -> npt.NDArray[np.float32]:
        if bands <= 0:
            return np.zeros(0, dtype=np.float32)

        if frame.shape[0] != self.frame_samples:
            frame = self._normalize_frame(frame)

        windowed = frame.astype(np.float32, copy=False) * self.window
        spectrum = np.abs(np.fft.rfft(windowed))
        magnitudes = self._map_bins_to_bands(spectrum, bands)
        magnitudes = np.sqrt(np.maximum(magnitudes, 0.0))

        if self._smoothed.shape[0] != bands:
            self._smoothed = np.zeros(bands, dtype=np.float32)

        alpha = self.smoothing
        self._smoothed = alpha * magnitudes + (1.0 - alpha) * self._smoothed
        peak_candidate = float(np.max(self._smoothed, initial=0.0))
        self._peak = max(peak_candidate, self._peak * self.peak_decay, 1e-6)
        normalized = np.clip((self._smoothed / self._peak) * sensitivity, 0.0, 1.0)
        return normalized.astype(np.float32, copy=False)

    def _normalize_frame(self, frame: npt.NDArray[np.float32]) -> npt.NDArray[np.float32]:
        fixed = np.zeros(self.frame_samples, dtype=np.float32)
        length = min(frame.shape[0], self.frame_samples)
        fixed[:length] = frame[:length]
        return fixed

    def _map_bins_to_bands(
        self,
        spectrum: npt.NDArray[np.float32] | npt.NDArray[np.float64],
        bands: int,
    ) -> npt.NDArray[np.float32]:
        edges = self._band_edges(bands)
        values = np.zeros(bands, dtype=np.float32)
        for index in range(bands):
            low, high = edges[index], edges[index + 1]
            mask = (self._frequencies >= low) & (self._frequencies < high)
            if not np.any(mask):
                nearest = int(np.argmin(np.abs(self._frequencies - (low + high) / 2.0)))
                values[index] = float(spectrum[nearest])
                continue
            values[index] = float(np.mean(spectrum[mask]))
        return values

    @lru_cache(maxsize=128)
    def _band_edges(self, bands: int) -> tuple[float, ...]:
        minimum = 20.0
        maximum = max(min(self.sample_rate / 2.0, 20_000.0), minimum + 1.0)
        edges = np.geomspace(minimum, maximum, num=bands + 1, dtype=np.float64)
        edges[0] = 0.0
        edges[-1] = maximum + 1.0
        return tuple(float(value) for value in edges)

    def _refresh_frequency_bins(self) -> None:
        self._frequencies = np.fft.rfftfreq(self.frame_samples, d=1.0 / self.sample_rate)
