"""Thread-owned WASAPI continuous audio state machine for VDH_Audio_Keeper."""
from dataclasses import dataclass
import logging
import os
from pathlib import Path
import sys
import threading
import time
from .noise import Noise
from .config import VERSION


class RotatingLogHandler(logging.Handler):
    def __init__(self, path, max_bytes=512 * 1024, backups=3):
        super().__init__()
        self.path = Path(path)
        self.max_bytes = max_bytes
        self.backups = backups
        self.last_error = ""

    def emit(self, record):
        try:
            payload = (self.format(record) + "\n").encode("utf-8", errors="replace")
            if len(payload) >= self.max_bytes:
                payload = payload[:self.max_bytes - 32] + b"\n[log entry truncated]\n"
            current = self.path.stat().st_size if self.path.exists() else 0
            if current + len(payload) >= self.max_bytes:
                for index in range(self.backups, 0, -1):
                    source = self.path if index == 1 else Path(str(self.path) + f".{index - 1}")
                    if source.exists():
                        os.replace(source, Path(str(self.path) + f".{index}"))
            with self.path.open("ab") as handle:
                handle.write(payload)
            self.last_error = ""
        except Exception as exc:
            self.last_error = str(exc)


@dataclass(frozen=True)
class Settings:
    enabled: bool = True
    device: str = ""
    volume: int = 5
    signal_type: str = "white_noise"
    debug: bool = False

    @classmethod
    def from_config(cls, data):
        return cls(
            enabled=bool(data.get("enabled", True)),
            device=str(data.get("device", "")),
            volume=max(0, min(100, int(data.get("volume", 5)))),
            signal_type=str(data.get("signal_type", "white_noise")),
            debug=bool(data.get("debug", False))
        )


def make_logger(directory):
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    logger = logging.Logger("VDH_Audio_Keeper", logging.INFO)
    handler = RotatingLogHandler(path / "vdh-audio-keeper.log")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger


class Engine:
    def __init__(self, logger, backend=None):
        if backend is None:
            from . import wasapi as backend
        self.backend = backend
        self.logger = logger
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.quit = threading.Event()
        self.scan_requested = threading.Event()
        self.settings = Settings()
        self.status = {
            "state": "Disabled",
            "device": "",
            "format": "",
            "frames": 0,
            "buffers": 0,
            "emptyBuffers": 0,
            "recoveries": 0,
            "lastError": "",
            "devices": [],
            "scanGeneration": 0,
            "scanError": "",
            "version": VERSION
        }
        self.thread = threading.Thread(target=self._run, name="VDH_Audio_Keeper_Engine", daemon=True)
        self.thread.start()

    def update(self, settings):
        with self.lock:
            self.settings = settings
        self.wake.set()

    def request_scan(self):
        self.scan_requested.set()
        self.wake.set()

    def snapshot(self):
        with self.lock:
            return dict(self.status)

    def _status(self, **values):
        with self.lock:
            self.status.update(values)

    def stop(self):
        self.quit.set()
        self.wake.set()
        self.thread.join(1.5)
        if self.thread.is_alive():
            self.logger.error("Engine worker did not stop cleanly within timeout")
            return False
        return True

    def _run(self):
        system = stream = noise = None
        applied = None
        volume_applied = None
        next_retry = next_devices = next_check = next_report = 0.0
        retry_delay = 1.0
        started_at = 0.0
        frames = buffers = empty = recoveries = 0
        self.logger.info("VDH_Audio_Keeper engine started (v%s)", VERSION)
        try:
            while not self.quit.is_set():
                self.wake.clear()
                with self.lock:
                    settings = self.settings
                scan = self.scan_requested.is_set()
                self.scan_requested.clear()
                now = time.monotonic()
                if settings != applied:
                    self.logger.setLevel(logging.DEBUG if settings.debug else logging.INFO)
                    if stream:
                        if not settings.enabled or settings.device != (applied.device if applied else ""):
                            self._close_stream(stream, noise, smooth=True)
                            stream = noise = None
                        elif applied and settings.signal_type != applied.signal_type:
                            noise = Noise(stream.format, 100, signal_type=settings.signal_type)
                    self.logger.info("Settings update: enabled=%s device=%s volume=%d signal_type=%s",
                                     settings.enabled, settings.device or "Windows Default", settings.volume, settings.signal_type)
                    applied = settings
                    next_retry = next_check = 0
                    retry_delay = 1
                    self._status(state=("Playing" if stream else "Starting") if settings.enabled else "Disabled")
                try:
                    if system is None and (settings.enabled or scan) and (scan or now >= next_retry):
                        system = self.backend.AudioSystem()
                        next_devices = 0
                    if system and (scan or (settings.enabled and now >= next_devices)):
                        try:
                            self._status(devices=system.devices())
                            self._status(scanError="")
                        except Exception:
                            self.logger.warning("Device list scan failed", exc_info=True)
                            self._status(scanError="Device scan failed")
                        self._status(scanGeneration=self.snapshot()["scanGeneration"] + 1)
                        next_devices = now + 5
                    if settings.enabled and not stream and system and now >= next_retry:
                        stream = self.backend.RenderStream(system, settings.device)
                        stream.set_volume(settings.volume)
                        volume_applied = settings.volume
                        noise = Noise(stream.format, 100, signal_type=settings.signal_type)
                        stream.write(noise.take(stream.capacity))
                        frames += stream.capacity
                        buffers += 1
                        stream.start()
                        started_at = now
                        recoveries += 1
                        self.logger.info("Audio stream started on output='%s' id='%s' format=%s",
                                         stream.name, stream.device_id, stream.format)
                        self._status(state="Playing", device=stream.name, format=str(stream.format),
                                     lastError="", recoveries=max(0, recoveries - 1))
                    if stream:
                        if volume_applied != settings.volume:
                            stream.set_volume(settings.volume)
                            volume_applied = settings.volume
                        available = stream.available()
                        if available:
                            if available == stream.capacity:
                                empty += 1
                            stream.write(noise.take(available))
                            frames += available
                            buffers += 1
                        self._status(frames=frames, buffers=buffers, emptyBuffers=empty)
                        if now >= next_check:
                            if not settings.device and system.default_id() != stream.device_id:
                                self.logger.info("Windows default output changed; reopening stream")
                                self._close_stream(stream, noise, smooth=True)
                                stream = noise = None
                            next_check = now + 2
                        if now - started_at >= 60:
                            retry_delay = 1
                        if now >= next_report:
                            self.logger.info("Status: frames=%d buffers=%d empty=%d recoveries=%d",
                                             frames, buffers, empty, max(0, recoveries - 1))
                            next_report = now + (30 if settings.debug else 120)
                    if system:
                        pump = getattr(self.backend, "pump_messages", None)
                        if pump:
                            pump()
                    if system and not settings.enabled:
                        system.close()
                        system = None
                except Exception as exc:
                    self.logger.exception("Audio operation error; retrying in %.0fs", retry_delay)
                    self._status(state="Recovering" if settings.enabled else "Disabled", lastError=str(exc))
                    if stream:
                        self._close_stream(stream, noise, smooth=False)
                        stream = noise = None
                    if system:
                        system.close()
                        system = None
                    next_retry = now + retry_delay
                    retry_delay = min(30, retry_delay * 2)
                self.wake.wait(0.02 if stream else 0.5)
        except Exception as exc:
            self._status(state="Error", lastError=str(exc))
            self.logger.exception("Engine thread error")
        finally:
            if stream:
                self._close_stream(stream, noise, smooth=False)
            if system:
                system.close()
            self._status(state="Stopped")
            self.logger.info("Engine thread stopped")

    def _close_stream(self, stream, noise, smooth):
        try:
            if smooth and noise and stream.started:
                available = stream.available()
                if available:
                    stream.write(noise.take(available, fade_out=True))
                    time.sleep(min(0.25, stream.capacity / stream.format.rate))
        except Exception:
            pass
        finally:
            try:
                stream.close()
            except Exception:
                pass
