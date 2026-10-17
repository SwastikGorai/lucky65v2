"""Windows preferences, startup integration, and reconnecting stream lifecycle."""
import ctypes
from ctypes import wintypes
import json
import logging
import math
import os
from pathlib import Path
import subprocess
import sys
import threading

from musicviz import run_stream
from musicviz_session import Panel

APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Lucky65Music"
DEFAULTS = {"version": 1, "gain": 1.0, "agc": True, "device": "", "startup": False}
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def load_preferences(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if (not isinstance(data, dict) or data.get("version") != 1
                or type(data.get("gain")) not in (int, float)
                or not math.isfinite(data["gain"]) or not 0.1 <= data["gain"] <= 4
                or type(data.get("agc")) is not bool
                or type(data.get("startup")) is not bool
                or not isinstance(data.get("device"), str)):
            raise ValueError("Invalid preferences")
        return {key: data[key] for key in DEFAULTS}, None
    except FileNotFoundError:
        return DEFAULTS.copy(), None
    except (OSError, ValueError) as exc:
        return DEFAULTS.copy(), f"Preferences could not be loaded: {exc}. Save explicitly to replace them."


def save_preferences(path, values):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(values, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def set_startup(enabled):
    import winreg
    if enabled and not getattr(sys, "frozen", False):
        raise RuntimeError("Start with Windows is available in the packaged EXE.")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
        if enabled:
            command = subprocess.list2cmdline([str(Path(sys.executable).resolve()), "--tray"])
            winreg.SetValueEx(key, "Lucky65Music", 0, winreg.REG_SZ, command)
        else:
            try:
                winreg.DeleteValue(key, "Lucky65Music")
            except FileNotFoundError:
                pass


def startup_enabled():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, "Lucky65Music")
        return True
    except FileNotFoundError:
        return False


class Instance:
    def __init__(self):
        self.kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        self.kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self.kernel.CreateMutexW.restype = wintypes.HANDLE
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handle = self.kernel.CreateMutexW(None, False, "Local\\Lucky65Music-" + os.environ.get("USERNAME", "user"))
        self.exists = ctypes.get_last_error() == 183
        if not self.handle:
            raise ctypes.WinError(ctypes.get_last_error())

    def close(self):
        self.kernel.CloseHandle(self.handle)


class DesktopSession:
    def __init__(self, args, runner=run_stream):
        self.args = args
        self.panel = Panel(args)
        self.runner = runner
        self.shutdown = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True, name="desktop-stream")

    def start(self):
        self.thread.start()

    def _run(self):
        while not self.shutdown.is_set():
            self.panel.stop.clear()
            if self.shutdown.is_set():
                break
            try:
                self.runner(self.args, self.panel)
            except Exception as exc:
                self.panel.log(f"Stream unavailable: {exc}")
                logging.exception("Streaming failed")
            self.panel.settings = None
            self.panel.levels[:] = 0
            while not self.panel.commands.empty():
                self.panel.commands.get_nowait()
            if self.shutdown.wait(2):
                break

    def change_device(self, name):
        self.args.device = name or None
        self.panel.stop.set()

    def close(self):
        self.shutdown.set()
        self.panel.stop.set()
