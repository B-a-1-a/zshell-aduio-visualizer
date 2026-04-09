from __future__ import annotations

import platform
import signal
import sys
import threading
import time
from dataclasses import dataclass

import click
import numpy as np
from blessed import Terminal

from termviz.capture import BackendDiagnostic, CaptureError, SwiftHelperBackend
from termviz.config import AppConfig
from termviz.dsp import SpectrumProcessor
from termviz.renderer import TerminalRenderer


class UnsupportedPlatformError(RuntimeError):
    """Raised when termviz is started on an unsupported platform."""


@dataclass(slots=True)
class LatestBands:
    values: np.ndarray
    lock: threading.Lock

    @classmethod
    def empty(cls) -> "LatestBands":
        return cls(values=np.zeros(0, dtype=np.float32), lock=threading.Lock())

    def get(self) -> np.ndarray:
        with self.lock:
            return self.values.copy()

    def set(self, values: np.ndarray) -> None:
        with self.lock:
            self.values = values.copy()


class VisualizerApp:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.term = Terminal()
        self.renderer = TerminalRenderer(self.term, config.color, no_color=config.no_color)
        self.capture = SwiftHelperBackend(
            frame_samples=config.frame_samples,
            sample_rate=config.sample_rate,
            queue_size=config.queue_size,
            startup_timeout=config.startup_timeout,
        )
        self.latest = LatestBands.empty()
        self.stop_event = threading.Event()
        self.dsp_thread: threading.Thread | None = None
        self.processor = SpectrumProcessor(
            sample_rate=config.sample_rate,
            frame_samples=config.frame_samples,
            smoothing=config.smoothing,
            peak_decay=config.peak_decay,
        )

    def ensure_supported_platform(self) -> None:
        if sys.platform != "darwin":
            raise UnsupportedPlatformError("termviz currently supports macOS only.")
        mac_ver = platform.mac_ver()[0]
        if not mac_ver:
            raise UnsupportedPlatformError("termviz could not determine your macOS version.")
        pieces = mac_ver.split(".")
        major = int(pieces[0])
        minor = int(pieces[1]) if len(pieces) > 1 else 0
        if (major, minor) < (14, 2):
            raise UnsupportedPlatformError("termviz requires macOS 14.2 or newer for Core Audio taps.")

    def check(self) -> BackendDiagnostic:
        self.ensure_supported_platform()
        diagnostic = self.capture.check()
        colors = self.term.number_of_colors if self.term.does_styling else 0
        return BackendDiagnostic(
            backend=diagnostic.backend,
            supported=diagnostic.supported,
            permission=diagnostic.permission,
            color_depth=colors,
            sample_rate=diagnostic.sample_rate,
            message=diagnostic.message,
        )

    def run(self) -> None:
        self.ensure_supported_platform()
        self.capture.start()
        self.processor.set_sample_rate(self.capture.sample_rate)
        self._install_signal_handlers()
        self.dsp_thread = threading.Thread(target=self._dsp_loop, name="termviz-dsp", daemon=True)
        self.dsp_thread.start()

        frame_delay = 1.0 / self.config.fps
        with self.term.fullscreen(), self.term.hidden_cursor(), self.term.cbreak():
            sys.stdout.write(self.term.home + self.term.clear)
            sys.stdout.flush()
            while not self.stop_event.is_set():
                magnitudes = self.latest.get()
                sys.stdout.write(self.renderer.render_frame(magnitudes, self.config.bars))
                sys.stdout.flush()
                time.sleep(frame_delay)
        self.shutdown()

    def shutdown(self) -> None:
        self.stop_event.set()
        self.capture.stop()
        if self.dsp_thread is not None:
            self.dsp_thread.join(timeout=1.0)

    def _install_signal_handlers(self) -> None:
        signal.signal(signal.SIGINT, self._handle_stop_signal)
        signal.signal(signal.SIGTERM, self._handle_stop_signal)
        if hasattr(signal, "SIGWINCH"):
            signal.signal(signal.SIGWINCH, self._handle_resize)

    def _handle_stop_signal(self, _signum: int, _frame: object) -> None:
        self.stop_event.set()

    def _handle_resize(self, _signum: int, _frame: object) -> None:
        # Terminal dimensions are read live by blessed; the handler exists so SIGWINCH interrupts sleep.
        return

    def _dsp_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                frame = self.capture.read_frame(timeout=0.1)
            except CaptureError as exc:
                self.stop_event.set()
                click.echo(
                    f"termviz audio capture stopped: {exc}\n"
                    "If macOS denied access, enable your terminal in System Settings > Privacy & Security > Screen & System Audio Recording.",
                    err=True,
                )
                return
            if frame is None:
                continue
            bar_count = self.renderer.metrics(self.config.bars).bars
            magnitudes = self.processor.process(frame, bar_count, sensitivity=self.config.sensitivity)
            self.latest.set(magnitudes)
