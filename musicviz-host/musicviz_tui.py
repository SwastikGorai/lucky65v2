"""Local terminal controls; the streaming thread owns all HID access."""
import queue
import threading
import time

import numpy as np
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, Footer, Header, Static

from musicviz import preview_line, run_stream

COLORS = ("Red", "Yellow", "Green", "Cyan", "Blue", "Pink", "White", "Color drift", "Custom")
MODES = ("Other RGB effect", "Breathing", "Bottom-up bar")


class Panel:
    def __init__(self, args):
        self.gain = max(0.1, min(4.0, args.gain))
        self.agc = not args.no_agc
        self.paused = False
        self.stop = threading.Event()
        self.commands = queue.Queue()
        self.settings = (1, 0, 200, 1) if args.dry_run else None
        self.levels = np.zeros(30, dtype=np.uint8)
        self.status = "Connecting…"
        self.last_poll = 0
        self.last_reply = time.monotonic()

    def log(self, message):
        self.status = message

    def exchange(self, transport, now):
        while not self.commands.empty():
            command, value = self.commands.get_nowait()
            if transport.dry_run:
                state = list(self.settings)
                state[command - 1] = value
                if command == 1:
                    state[3] = 1
                self.settings = tuple(state)
            else:
                transport.control(command, value)
        if now - self.last_poll >= 0.25:
            self.last_poll = now
            if not transport.dry_run:
                transport.control()
                state = None
                for _ in range(8):
                    reply = transport.read_settings()
                    if reply is None:
                        break
                    state = reply
                if state is not None:
                    self.settings = state
                    self.last_reply = now
                    self.status = "Connected · settings apply live"
                elif now - self.last_reply > 2:
                    self.settings = None
                    self.status = "No control reply: use USB mode and flash the updated firmware."


class MusicApp(App):
    TITLE = "Lucky65 · Music controls"
    CSS = """
    Screen { padding: 1 2; }
    #meter { height: 3; color: $accent; }
    #audio, #keyboard { height: 3; }
    Horizontal { height: 3; margin-bottom: 1; }
    Button { margin-right: 1; min-width: 12; }
    #status { margin-top: 1; color: $text-muted; }
    """
    BINDINGS = [("q", "quit", "Quit"), ("space", "pause", "Pause"),
                ("minus", "gain_down", "Less sensitive"), ("plus", "gain_up", "More sensitive")]

    def __init__(self, args):
        super().__init__()
        self.args = args
        self.panel = Panel(args)
        self.thread = None
        self.started = time.monotonic()

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(id="meter")
        yield Static(id="audio")
        with Horizontal():
            yield Button("Sensitivity −", id="gain-down")
            yield Button("Sensitivity +", id="gain-up")
            yield Button("Auto gain", id="agc")
            yield Button("Pause", id="pause")
        yield Static(id="keyboard")
        with Horizontal():
            yield Button("Breathing", id="breathing")
            yield Button("Bottom-up bar", id="bar")
            yield Button("Next color", id="color")
        with Horizontal():
            yield Button("Dimmer", id="dimmer")
            yield Button("Brighter", id="brighter")
        yield Static("Settings apply live. Keyboard controls require updated firmware.")
        yield Static(id="status")
        yield Footer()

    def on_mount(self):
        self.thread = threading.Thread(target=self.stream, name="music-stream", daemon=True)
        self.thread.start()
        self.set_interval(0.1, self.refresh_panel)

    def stream(self):
        try:
            run_stream(self.args, self.panel)
        except Exception as exc:
            self.panel.log(f"Stream stopped: {exc}")

    def refresh_panel(self):
        p = self.panel
        self.query_one("#meter", Static).update(preview_line(p.levels))
        self.query_one("#audio", Static).update(
            f"Sensitivity {p.gain:.1f}×  ·  Auto gain {'on' if p.agc else 'off'}  ·  {'Paused' if p.paused else 'Playing'}")
        state = p.settings
        self.query_one("#keyboard", Static).update(
            f"{MODES[state[0]]}  ·  {COLORS[state[1]]}  ·  Brightness {state[2]}/200  ·  RGB {'on' if state[3] else 'off'}"
            if state else "Waiting for keyboard settings…")
        for name in ("breathing", "bar", "color", "dimmer", "brighter"):
            self.query_one(f"#{name}", Button).disabled = state is None or not self.thread.is_alive()
        self.query_one("#status", Static).update(("DEMO · " if self.args.dry_run else "") + p.status)
        if self.args.duration and time.monotonic() - self.started >= self.args.duration:
            self.exit()

    def action_gain_down(self):
        self.panel.gain = max(0.1, round(self.panel.gain - 0.1, 1))

    def action_gain_up(self):
        self.panel.gain = min(4.0, round(self.panel.gain + 0.1, 1))

    def action_pause(self):
        self.panel.paused = not self.panel.paused

    def on_button_pressed(self, event: Button.Pressed):
        name = event.button.id
        if name in ("gain-down", "gain-up", "pause"):
            getattr(self, "action_" + name.replace("-", "_"))()
        elif name == "agc":
            self.panel.agc = not self.panel.agc
        elif self.panel.settings is not None:
            _, color, brightness, _ = self.panel.settings
            command, value = {"breathing": (1, 1), "bar": (1, 2),
                              "color": (2, (color + 1) % 8),
                              "dimmer": (3, max(0, brightness - 10)),
                              "brighter": (3, min(200, brightness + 10))}[name]
            self.panel.commands.put((command, value))

    def on_unmount(self):
        self.panel.stop.set()
        if self.thread:
            self.thread.join(timeout=3)
