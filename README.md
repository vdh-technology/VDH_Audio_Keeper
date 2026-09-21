# VDH_Audio_Keeper

**VDH_Audio_Keeper** is a lightweight Windows background utility designed to eliminate audio latency, delay, and initial sound cut-offs commonly experienced with Bluetooth audio devices, USB DACs, and external sound cards.

Inspired by the `angelAudioKeeper` NVDA add-on created by **Angels Clan**, VDH_Audio_Keeper continuously feeds an imperceptible, low-volume keep-alive audio signal through Windows Core Audio (WASAPI), keeping your audio hardware continuously active without sleep mode delays or distortion.

---

## 📖 Table of Contents

- [The Problem & Solution](#-the-problem--solution)
- [Key Features](#-key-features)
- [System Requirements](#-system-requirements)
- [Installation & Running](#-installation--running)
- [Detailed User Guide](#-detailed-user-guide)
  - [1. System Tray Interface](#1-system-tray-interface)
  - [2. Settings Dialog Configuration](#2-settings-dialog-configuration)
- [Configuration & Logging](#-configuration--logging)
- [How It Works (Technical Highlights)](#-how-it-works-technical-highlights)
- [License & Acknowledgments](#-license--acknowledgments)

---

## ⚡ The Problem & Solution

### The Problem
Many Bluetooth headphones, wireless speakers, USB DACs, and HDMI audio receivers enter an aggressive power-saving or standby mode after a few seconds of silence. When Windows suddenly starts outputting audio (e.g., screen reader speech, notification chimes, system sound effects, or video playback), the audio device takes 1 to 2 seconds to wake up. As a result, the beginning of the sound is clipped, muted, or delayed.

### The Solution
VDH_Audio_Keeper solves this issue by running quietly in the background and streaming a continuous, mathematically optimized sub-audible audio signal directly to your output device via WASAPI shared mode. This keeps the audio driver and hardware interface active and ready at all times without affecting your master volume, audio quality, or media playback.

---

## ✨ Key Features

- **Zero-Latency Audio Response**: Prevents Bluetooth/USB audio devices from entering sleep mode, ensuring immediate sound playback.
- **Native WASAPI Engine**: Low-overhead C-types COM binding directly to Windows WASAPI shared render streams. Supports all sample rates (44.1kHz - 384kHz), floating point formats, and channel configurations (Stereo, 5.1, 7.1 surround).
- **System Tray Native**: Runs silently in the notification area without taskbar clutter.
- **Dynamic Device Tracking**: Follows the active Windows Default Output Device automatically, or allows locking to a specific audio hardware device.
- **Adjustable Volume Level**: Fine-tune background noise level slider (0% to 100%, default 5%) for complete transparency.
- **Auto-Start with Windows**: Integrated Windows Registry setting to automatically launch on boot up.
- **Single-Instance Protection**: Prevents duplicate instances from launching simultaneously.
- **Smooth Stream Recovery**: Automatically reconnects and recovers if audio devices are plugged in/unplugged or system sleeps.

---

## 💻 System Requirements

- **Operating System**: Windows 10 or Windows 11 (64-bit recommended)
- **Python**: Python 3.10 or higher (if running from source)
- **Dependencies**: `wxPython`

---

## 🚀 Installation & Running

### Option A: Run from Source

1. **Clone or Download the Repository**:
   ```bash
   git clone https://github.com/vdh-technology/VDH_Audio_Keeper.git
   cd VDH_Audio_Keeper
   ```

2. **Install Dependencies**:
   Using `uv` (recommended):
   ```bash
   uv sync
   ```
   Or using standard `pip`:
   ```bash
   pip install wxpython
   ```

3. **Launch the Application**:
   - Standard mode:
     ```bash
     python VDH_Audio_Keeper.py
     ```
   - Silent background mode (without console window):
     ```bash
     pythonw VDH_Audio_Keeper.py
     ```

---

## 🕹️ Detailed User Guide

### 1. System Tray Interface

Upon launching, VDH_Audio_Keeper stays hidden and creates a speaker icon in the **Windows System Tray** (notification area near the clock).

- **Left-Click** or **Double-Click** the tray icon: Opens the **Settings** dialog.
- **Right-Click** the tray icon: Opens the context menu with options:
  - **Settings...**: Open configuration window.
  - **Exit**: Stop the audio keeper engine and close the application.

---

### 2. Settings Dialog Configuration

Double-clicking the tray icon opens the **Settings** window:

| Setting Option | Description | Recommended Usage |
| :--- | :--- | :--- |
| **Enable continuous audio** | Master toggle to turn the audio keeper engine ON or OFF. | **Checked (Enabled)** |
| **Audio output device** | Select target device: **Default output device** (automatically tracks active default audio device) or a specific listed audio output device. | **Default output device** for general use, or select your specific Bluetooth headset/DAC. |
| **Noise volume** | Slider ranging from **0% to 100%** (default is **5%**). Controls signal strength. | **5%** (Or lower down to 1-2% if audible on high-gain headphones). |
| **Start with Windows** | Enables automatic startup when Windows boots by writing to Windows Registry `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`. | **Checked** for hands-off background operation. |

After adjusting settings:
- Click **OK** to save configuration and apply changes immediately to the running engine.
- Click **Cancel** to discard changes.

---

## 📂 Configuration & Logging

### Configuration File
Settings are automatically saved in JSON format at:
```text
%APPDATA%\VDH_Audio_Keeper\config.json
```
Example configuration:
```json
{
  "enabled": true,
  "device": "",
  "volume": 5,
  "start_with_windows": true
}
```

### Log Files
VDH_Audio_Keeper includes a built-in rotating logger (max 512KB per file, up to 3 backups) to track stream status, device changes, and diagnostic information:
```text
%APPDATA%\VDH_Audio_Keeper\logs\vdh-audio-keeper.log
```

---

## 🔬 How It Works (Technical Highlights)

1. **Thread-Owned WASAPI Loop**: The core `Engine` manages a dedicated background thread running an event-driven loop that interacts with Windows Core Audio endpoints through COM interfaces (`IAudioClient`, `IAudioRenderClient`, `IAudioStreamVolume`).
2. **Channel-Aware Noise Pool**: Generates per-channel decorrelated pseudo-random noise scaled dynamically to device channel counts and sample encoding (PCM 16/24/32-bit or IEEE Float).
3. **Smooth Crossfading**: When disabling continuous audio or changing devices, the engine applies ramped fade-outs to eliminate audio clicks or pops.

---

## 📄 License & Acknowledgments

- **Inspiration**: Inspired by the `angelAudioKeeper` NVDA add-on by developer **Angels Clan**.
- **License**: Distributed under the terms of the GNU General Public License v3.0 ([GPL-3.0](LICENSE)).

