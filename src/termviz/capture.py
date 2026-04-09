from __future__ import annotations

import json
import os
import queue
import signal
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
import numpy.typing as npt


class CaptureError(RuntimeError):
    """Raised when audio capture cannot start or continue."""


@dataclass(frozen=True, slots=True)
class BackendDiagnostic:
    backend: str
    supported: bool
    permission: str
    color_depth: int | None = None
    sample_rate: int | None = None
    message: str = ""


class CaptureBackend(Protocol):
    def start(self) -> None: ...
    def read_frame(self, timeout: float | None = None) -> npt.NDArray[np.float32] | None: ...
    def stop(self) -> None: ...
    def check(self) -> BackendDiagnostic: ...


@dataclass(slots=True)
class HelperEvent:
    event: str
    level: str | None
    message: str
    payload: dict[str, object]


class PCMFrameAssembler:
    def __init__(self, frame_samples: int) -> None:
        self.frame_bytes = frame_samples * 4
        self._buffer = bytearray()

    def push(self, chunk: bytes) -> list[npt.NDArray[np.float32]]:
        self._buffer.extend(chunk)
        frames: list[npt.NDArray[np.float32]] = []
        while len(self._buffer) >= self.frame_bytes:
            frame_bytes = bytes(self._buffer[: self.frame_bytes])
            del self._buffer[: self.frame_bytes]
            frames.append(np.frombuffer(frame_bytes, dtype="<f4").astype(np.float32, copy=False))
        return frames


def parse_helper_event(line: str) -> HelperEvent:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        return HelperEvent(event="log", level="info", message=line.strip(), payload={})
    return HelperEvent(
        event=str(payload.get("event", "log")),
        level=payload.get("level") if isinstance(payload.get("level"), str) else None,
        message=str(payload.get("message", "")),
        payload=payload if isinstance(payload, dict) else {},
    )


class SwiftHelperBackend:
    def __init__(self, *, frame_samples: int, sample_rate: int, queue_size: int = 8, startup_timeout: float = 5.0) -> None:
        self.frame_samples = frame_samples
        self.sample_rate = sample_rate
        self.queue_size = queue_size
        self.startup_timeout = startup_timeout
        self._frames: queue.Queue[npt.NDArray[np.float32]] = queue.Queue(maxsize=queue_size)
        self._events: queue.Queue[HelperEvent] = queue.Queue()
        self._process: subprocess.Popen[bytes] | None = None
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()
        self._fatal_error: str | None = None

    def start(self) -> None:
        self.stop()
        helper = resolve_helper_executable()
        self._process = subprocess.Popen(
            [
                str(helper),
                "capture",
                "--frame-samples",
                str(self.frame_samples),
                "--sample-rate",
                str(self.sample_rate),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self._stop.clear()
        self._fatal_error = None
        self._threads = [
            threading.Thread(target=self._stdout_loop, name="termviz-helper-stdout", daemon=True),
            threading.Thread(target=self._stderr_loop, name="termviz-helper-stderr", daemon=True),
        ]
        for thread in self._threads:
            thread.start()

        deadline = threading.Event()
        timer = threading.Timer(self.startup_timeout, deadline.set)
        timer.start()
        try:
            while not deadline.is_set():
                try:
                    event = self._events.get(timeout=0.1)
                except queue.Empty:
                    if self._fatal_error is not None:
                        self.stop()
                        raise CaptureError(self._fatal_error)
                    continue
                if event.event == "ready":
                    if "sample_rate" in event.payload:
                        self.sample_rate = int(event.payload["sample_rate"])
                    return
                if event.event == "error":
                    self.stop()
                    raise CaptureError(event.message or "termviz helper failed to start audio capture.")
        finally:
            timer.cancel()
        self.stop()
        raise CaptureError("termviz helper did not report ready status before timeout.")

    def read_frame(self, timeout: float | None = None) -> npt.NDArray[np.float32] | None:
        if self._fatal_error is not None:
            raise CaptureError(self._fatal_error)
        try:
            return self._frames.get(timeout=timeout)
        except queue.Empty:
            if self._fatal_error is not None:
                raise CaptureError(self._fatal_error)
            return None

    def stop(self) -> None:
        self._stop.set()
        process = self._process
        self._process = None
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=1.0)
        for thread in self._threads:
            thread.join(timeout=0.2)
        self._threads.clear()

    def check(self) -> BackendDiagnostic:
        helper = resolve_helper_executable()
        result = subprocess.run(
            [
                str(helper),
                "check",
                "--frame-samples",
                str(self.frame_samples),
                "--sample-rate",
                str(self.sample_rate),
            ],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        payload: dict[str, object] = {}
        stdout = result.stdout.strip()
        if stdout:
            try:
                payload = json.loads(stdout)
            except json.JSONDecodeError:
                payload = {"message": stdout}
        message = str(payload.get("message", result.stderr.strip() or "helper diagnostic completed"))
        return BackendDiagnostic(
            backend=str(payload.get("backend", "swift-coreaudio")),
            supported=bool(payload.get("supported", result.returncode == 0)),
            permission=str(payload.get("permission", "unknown")),
            sample_rate=int(payload["sample_rate"]) if "sample_rate" in payload else None,
            message=message,
        )

    def _stdout_loop(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        assembler = PCMFrameAssembler(self.frame_samples)
        while not self._stop.is_set():
            chunk = self._process.stdout.read(self.frame_samples * 4)
            if not chunk:
                if self._process.poll() not in (None, 0) and self._fatal_error is None:
                    self._fatal_error = "termviz helper exited unexpectedly."
                return
            for frame in assembler.push(chunk):
                while True:
                    try:
                        self._frames.put_nowait(frame)
                        break
                    except queue.Full:
                        try:
                            self._frames.get_nowait()
                        except queue.Empty:
                            break

    def _stderr_loop(self) -> None:
        assert self._process is not None and self._process.stderr is not None
        for raw_line in self._process.stderr:
            if self._stop.is_set():
                return
            event = parse_helper_event(raw_line.decode("utf-8", errors="replace"))
            if event.event == "error":
                self._fatal_error = event.message or "termviz helper reported an error."
                self._events.put(event)
                return
            self._events.put(event)


def resolve_helper_executable() -> Path:
    env_path = os.environ.get("TERMVIZ_HELPER_PATH")
    candidates = [
        Path(env_path).expanduser() if env_path else None,
        Path(__file__).with_name("helper") / "termviz-helper.app" / "Contents" / "MacOS" / "termviz-helper",
        Path(__file__).resolve().parents[2] / "termviz_helper" / ".build" / "release" / "termviz-helper",
    ]
    for candidate in candidates:
        if candidate is not None and candidate.exists():
            return candidate
    raise CaptureError(
        "Bundled helper is missing. Reinstall termviz on macOS with Swift available, or build the helper and set TERMVIZ_HELPER_PATH."
    )
