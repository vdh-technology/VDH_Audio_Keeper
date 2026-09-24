"""Small, format-aware noise generator for VDH_Audio_Keeper."""
from dataclasses import dataclass
from array import array
import math
import random
import struct


@dataclass(frozen=True)
class AudioFormat:
    rate: int
    channels: int
    bits: int
    floating: bool
    channel_mask: int = 0
    valid_bits: int = 0

    def __post_init__(self):
        if not 8000 <= self.rate <= 384000 or not 1 <= self.channels <= 32:
            raise ValueError("Unsupported device rate or channel count")
        if self.bits not in ((32, 64) if self.floating else (16, 24, 32)):
            raise ValueError("Unsupported device sample format")
        if self.valid_bits and not 1 <= self.valid_bits <= self.bits:
            raise ValueError("Invalid valid-bits value")

    @property
    def frame_bytes(self):
        return self.channels * (self.bits // 8)

    @property
    def channel_names(self):
        speakers = ("Front left", "Front right", "Front center", "Low-frequency effects",
                    "Back left", "Back right", "Front left of center", "Front right of center",
                    "Back center", "Side left", "Side right", "Top center", "Top front left",
                    "Top front center", "Top front right", "Top back left", "Top back center", "Top back right")
        bits = [bit for bit in range(32) if self.channel_mask & (1 << bit)]
        if len(bits) != self.channels:
            return tuple(f"Channel {index + 1} (layout unspecified)" for index in range(self.channels))
        return tuple(speakers[bit] if bit < len(speakers) else f"Speaker bit {bit}" for bit in bits)


class Noise:
    """Bounded circular pool with separately generated signal for every channel."""
    def __init__(self, fmt, volume, signal_type="white_noise", seed=None):
        self.fmt = fmt
        self.volume = max(0, min(100, int(volume)))
        valid_types = ("white_noise", "sub_bass", "pink_noise", "brown_noise", "high_frequency")
        self.signal_type = signal_type if signal_type in valid_types else "white_noise"
        gain = self.volume / 10000.0
        self._integer_peak = int(gain * ((1 << ((fmt.valid_bits or fmt.bits) - 1)) - 1))
        rng = random.Random(seed)
        self.rng = rng
        self.pool_frames = min(fmt.rate, 48000, 192000 // fmt.channels)
        self.samples = []

        if self.signal_type == "sub_bass":
            # Generate 12Hz inaudible sub-bass sine wave tone
            freq = 12.0
            for channel in range(fmt.channels):
                samples = array("d", (
                    math.sin(2.0 * math.pi * freq * index / fmt.rate) * gain
                    for index in range(self.pool_frames)
                ))
                self.samples.append(samples)
        elif self.signal_type == "high_frequency":
            # Generate 19.5kHz inaudible ultra-high frequency sine wave tone
            # Capped safely at 0.43 * sample_rate to avoid Nyquist aliasing
            freq = min(19500.0, fmt.rate * 0.43)
            for channel in range(fmt.channels):
                samples = array("d", (
                    math.sin(2.0 * math.pi * freq * index / fmt.rate) * gain
                    for index in range(self.pool_frames)
                ))
                self.samples.append(samples)
        elif self.signal_type == "pink_noise":
            # Generate Pink Noise using Paul Kellet's filter (1/f equal energy per octave)
            for channel in range(fmt.channels):
                b0 = b1 = b2 = b3 = b4 = b5 = b6 = 0.0
                raw_samples = []
                for _ in range(self.pool_frames):
                    white = rng.uniform(-1.0, 1.0)
                    b0 = 0.99886 * b0 + white * 0.0555179
                    b1 = 0.99332 * b1 + white * 0.0750759
                    b2 = 0.96900 * b2 + white * 0.1538520
                    b3 = 0.86650 * b3 + white * 0.3104856
                    b4 = 0.55000 * b4 + white * 0.5329522
                    b5 = -0.7616 * b5 - white * 0.0168980
                    pink = b0 + b1 + b2 + b3 + b4 + b5 + b6 + white * 0.5362
                    b6 = white * 0.115926
                    raw_samples.append(pink * 0.11)
                mean = sum(raw_samples) / self.pool_frames
                max_amp = max(abs(s - mean) for s in raw_samples) or 1.0
                samples = array("d", (((s - mean) / max_amp) * gain for s in raw_samples))
                self.samples.append(samples)
        elif self.signal_type == "brown_noise":
            # Generate Brown/Red Noise using leaky integration (1/f^2 deep frequency response)
            for channel in range(fmt.channels):
                last_val = 0.0
                raw_samples = []
                for _ in range(self.pool_frames):
                    white = rng.uniform(-1.0, 1.0)
                    last_val = (last_val + (0.02 * white)) / 1.02
                    raw_samples.append(last_val * 3.5)
                mean = sum(raw_samples) / self.pool_frames
                max_amp = max(abs(s - mean) for s in raw_samples) or 1.0
                samples = array("d", (((s - mean) / max_amp) * gain for s in raw_samples))
                self.samples.append(samples)
        else:
            # Generate uniform random white noise
            for channel in range(fmt.channels):
                raw_samples = [rng.uniform(-1.0, 1.0) for _ in range(self.pool_frames)]
                mean = sum(raw_samples) / self.pool_frames
                max_amp = max(abs(s - mean) for s in raw_samples) or 1.0
                samples = array("d", (((s - mean) / max_amp) * gain for s in raw_samples))
                self.samples.append(samples)
        self.position = 0
        self.ramp_frames = max(1, int(fmt.rate * 0.05))
        self.frames_sent = 0
        self._float_packer = struct.Struct("<" + ("f" if fmt.bits == 32 else "d") * fmt.channels)
        self.pool = b"".join(self._frame(index) for index in range(self.pool_frames))

    def _frame(self, index, scale=1.0):
        f = self.fmt
        values = [samples[index] * scale for samples in self.samples]
        if f.floating:
            return self._float_packer.pack(*(value if value != 0 else 0.0 for value in values))
        valid = f.valid_bits or f.bits
        frame = bytearray()
        for value in values:
            integer = round(value * ((1 << (valid - 1)) - 1))
            integer = max(-self._integer_peak, min(self._integer_peak, integer)) << (f.bits - valid)
            frame.extend(integer.to_bytes(f.bits // 8, "little", signed=True))
        return bytes(frame)

    def take(self, frames, fade_out=False):
        if not 0 <= frames <= self.fmt.rate * 2:
            raise ValueError("Requested audio block is out of bounds")
        start = self.position
        position = start
        count = self.pool_frames
        if fade_out or self.frames_sent < self.ramp_frames:
            data = bytearray()
            for i in range(frames):
                ramp = min(1.0, (self.frames_sent + i + 1) / self.ramp_frames)
                if fade_out:
                    ramp *= max(0.0, 1.0 - (i + 1) / max(1, frames))
                data.extend(self._frame(position, ramp))
                position += 1
                if position == count:
                    position = self._next_cycle_start()
            result = bytes(data)
        else:
            size = self.fmt.frame_bytes
            chunks = []
            remaining = frames
            while remaining:
                chunk = min(remaining, count - position)
                chunks.append(self.pool[position * size:(position + chunk) * size])
                remaining -= chunk
                position += chunk
                if position == count:
                    position = self._next_cycle_start()
            result = b"".join(chunks)
        self.position = position
        self.frames_sent += frames
        return result

    def _next_cycle_start(self):
        return self.rng.randrange(max(1, self.pool_frames // 2))
