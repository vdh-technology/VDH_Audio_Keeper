"""Config store and Windows registry startup manager for VDH_Audio_Keeper."""
import json
import os
from pathlib import Path
import sys
import tempfile
import winreg

APP_NAME = "VDH_Audio_Keeper"
VERSION = "1.0.0"
REG_RUN_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"

DEFAULTS = {
    "enabled": True,
    "device": "",
    "volume": 5,
    "start_with_windows": False
}


def get_config_path() -> Path:
    app_data = os.environ.get("APPDATA")
    if app_data:
        config_dir = Path(app_data) / APP_NAME
    else:
        config_dir = Path.home() / f".{APP_NAME.lower()}"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"


def get_log_dir() -> Path:
    app_data = os.environ.get("APPDATA")
    if app_data:
        log_dir = Path(app_data) / APP_NAME / "logs"
    else:
        log_dir = Path.home() / f".{APP_NAME.lower()}" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_executable_command() -> str:
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    else:
        pythonw = Path(sys.executable).parent / "pythonw.exe"
        if not pythonw.exists():
            pythonw = Path(sys.executable)
        main_script = Path(__file__).resolve().parent.parent / "VDH_Audio_Keeper.py"
        return f'"{pythonw}" "{main_script}"'


def get_autostart_status() -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_PATH, 0, winreg.KEY_READ)
        try:
            val, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(val)
        finally:
            winreg.CloseKey(key)
    except FileNotFoundError:
        return False
    except Exception:
        return False


def set_autostart_status(enable: bool) -> bool:
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_RUN_PATH, 0, winreg.KEY_ALL_ACCESS)
        try:
            if enable:
                cmd = get_executable_command()
                winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        finally:
            winreg.CloseKey(key)
        return True
    except Exception as exc:
        print(f"Failed to update registry autostart: {exc}")
        return False


class SettingsStore:
    def __init__(self, path: Path = None):
        self.path = path or get_config_path()
        self.data = dict(DEFAULTS)
        self.load()

    def load(self):
        if self.path.exists():
            try:
                content = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(content, dict):
                    for key in DEFAULTS:
                        if key in content:
                            self.data[key] = content[key]
            except Exception as exc:
                print(f"Error loading config: {exc}")
        # Always synchronize actual registry status into start_with_windows
        self.data["start_with_windows"] = get_autostart_status()

    def save(self, data: dict):
        validated = dict(DEFAULTS)
        for key in validated:
            if key in data:
                validated[key] = data[key]

        # Update Windows Registry for startup
        start_windows = bool(validated.get("start_with_windows", False))
        set_autostart_status(start_windows)

        # Write config file safely
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=self.path.parent,
                                             prefix="vdh_config-", suffix=".tmp", delete=False) as handle:
                temp_path = Path(handle.name)
                json.dump(validated, handle, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self.path)
            self.data = validated
        finally:
            if temp_path and temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
