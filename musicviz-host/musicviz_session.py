import queue
import threading
import time
import numpy as np

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
        self.last_audio_at = 0.0
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
