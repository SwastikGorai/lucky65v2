"""Portable Lucky65 desktop entry point."""
import argparse
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from types import SimpleNamespace

from PIL import Image, ImageDraw
import pystray

import musicviz
from musicviz_desktop import (APP_DIR, DesktopSession, Instance, load_preferences,
                              save_preferences, set_startup, startup_enabled)
from musicviz_session import COLORS, MODES
from musicviz_preview import KeyboardPreview

PAPER = "#F4F0E7"
INK = "#191919"
YELLOW = "#FFE34D"
MINT = "#B8F5CF"
PURPLE = "#D8C7FF"


def icon_image():
    image = Image.new("RGB", (64, 64), "#152331")
    draw = ImageDraw.Draw(image)
    for x, height in zip(range(10, 55, 9), (15, 30, 44, 30, 15)):
        draw.rounded_rectangle((x, 54-height, x+5, 54), radius=2, fill="#55dfb0")
    return image


class DesktopApp:
    def __init__(self, root, demo=False, tray=False, config_dir=APP_DIR):
        self.root = root
        self.path = config_dir / "settings.json"
        self.values, warning = load_preferences(self.path)
        self.preferences_valid = warning is None
        self.save_timer = None
        self.events = queue.Queue()
        self.tray = None
        self.closing = False
        self.closed = False
        self.device_names = ["Default output"]
        root.title("Lucky65 Music")
        root.geometry("760x875")
        root.minsize(700, 865)
        root.configure(bg=PAPER)
        root.option_add("*Font", ("Segoe UI", 10))
        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TCombobox", padding=7, fieldbackground="white", background=YELLOW,
                        foreground=INK, bordercolor=INK, lightcolor=INK, darkcolor=INK,
                        arrowcolor=INK, borderwidth=2)
        style.map("TCombobox", fieldbackground=[("readonly", "white"), ("disabled", PAPER)],
                  foreground=[("readonly", INK)])
        style.configure("Horizontal.TScale", background=MINT, troughcolor="white",
                        bordercolor=INK, lightcolor=INK, darkcolor=INK, sliderlength=24)
        root.protocol("WM_DELETE_WINDOW", self.hide)
        frame = tk.Frame(root, bg=PAPER, padx=24, pady=20)
        frame.pack(fill="both", expand=True)
        header = self.card(frame, YELLOW)
        self.label(header, "LUCKY65 / MUSIC", size=26, bold=True).pack(anchor="w")
        self.label(header, "SOUND IN. LIGHT OUT." + ("  /  DEMO" if demo else ""), bold=True).pack(anchor="w")
        self.status = tk.StringVar(value="Connecting…")
        meter_card = self.card(frame, INK)
        tk.Label(meter_card, text="LUCKY65 / LIVE LIGHTING", bg=INK, fg=MINT,
                 font=("Consolas", 10, "bold")).pack(anchor="w")
        self.meter = KeyboardPreview(meter_card)
        self.meter.pack(fill="x")
        tk.Label(meter_card, textvariable=self.status, bg=INK, fg="white", anchor="w",
                 wraplength=640, height=2, font=("Segoe UI", 9)).pack(fill="x")

        controls = tk.Frame(frame, bg=PAPER)
        controls.pack(fill="x")
        controls.columnconfigure((0, 1), weight=1, uniform="controls")
        audio = self.card(controls, MINT, column=0)
        lighting = self.card(controls, PURPLE, column=1)
        self.label(audio, "01 / AUDIO", size=14, bold=True).pack(anchor="w", pady=(0, 10))
        self.label(lighting, "02 / LIGHTING", size=14, bold=True).pack(anchor="w", pady=(0, 10))
        self.gain = tk.DoubleVar(value=self.values["gain"])
        self.gain_label = tk.StringVar()
        tk.Label(audio, textvariable=self.gain_label, bg=MINT, fg=INK, font=("Segoe UI", 11, "bold")).pack(anchor="w")
        ttk.Scale(audio, from_=0.1, to=4, variable=self.gain, command=self.gain_changed).pack(fill="x", pady=8)
        self.agc = tk.BooleanVar(value=self.values["agc"])
        self.check(audio, "Automatic gain", self.agc, self.agc_changed).pack(anchor="w", pady=(0, 8))
        self.effect = self.combo(lighting, "Music effect", MODES, lambda e: self.send(1, MODES.index(self.effect.get())))
        self.color = self.combo(lighting, "Color", COLORS, lambda e: self.send(2, COLORS.index(self.color.get())))
        self.brightness = tk.DoubleVar(value=200)
        self.label(lighting, "Brightness / 0–200", bold=True).pack(anchor="w", pady=(12, 4))
        style.configure("Lighting.Horizontal.TScale", background=PURPLE)
        self.brightness_scale = ttk.Scale(lighting, from_=0, to=200, variable=self.brightness,
                                          style="Lighting.Horizontal.TScale",
                                          command=lambda value: self.send(3, round(float(value))))
        self.brightness_scale.pack(fill="x")
        self.device = self.combo(audio, "Audio output", self.device_names, self.device_changed)
        self.device.set(self.values["device"] or "Default output")
        self.button(audio, "REFRESH OUTPUTS", self.refresh_devices).pack(fill="x", pady=(12, 0))
        footer = self.card(frame, PAPER)
        self.startup = tk.BooleanVar(value=startup_enabled())
        self.check(footer, "Start with Windows (in tray)", self.startup, self.startup_changed).pack(anchor="w", pady=(0, 10))
        buttons = tk.Frame(footer, bg=PAPER)
        buttons.pack(fill="x")
        self.pause_button = self.button(buttons, "PAUSE", self.pause, YELLOW)
        self.pause_button.pack(side="left", padx=(0, 8))
        self.button(buttons, "SAVE PREFERENCES", self.save).pack(side="left")
        self.button(buttons, "QUIT", self.quit, "#FF9A8B").pack(side="right")
        args = SimpleNamespace(gain=self.values["gain"], no_agc=not self.values["agc"],
                               dry_run=demo, selftest=demo, bands=30, fps=60, probe=None,
                               duration=0, preview=False, device=self.values["device"] or None,
                               rate=None, tilt=6)
        self.session = DesktopSession(args)
        self.gain_changed(str(self.gain.get()))
        self.session.start()
        self.refresh_devices()
        self.start_tray()
        if tray and self.tray:
            root.withdraw()
        root.after(100, self.tick)
        if warning:
            root.after(200, lambda: messagebox.showwarning("Preferences", warning, parent=root))

    def combo(self, frame, label, values, callback):
        self.label(frame, label, bold=True).pack(anchor="w", pady=(8, 4))
        widget = ttk.Combobox(frame, values=values, state="readonly")
        widget.pack(fill="x")
        widget.bind("<<ComboboxSelected>>", callback)
        return widget

    def card(self, parent, color, column=None):
        shadow = tk.Frame(parent, bg=INK)
        if column is None:
            shadow.pack(fill="x", pady=(0, 14))
        else:
            shadow.grid(row=0, column=column, sticky="nsew", padx=(0, 7) if column == 0 else (7, 0), pady=(0, 14))
        card = tk.Frame(shadow, bg=color, highlightbackground=INK, highlightthickness=3, padx=14, pady=12)
        card.pack(fill="both", expand=True, padx=(0, 5), pady=(0, 5))
        return card

    def label(self, parent, text, size=10, bold=False):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=INK,
                        font=("Segoe UI", size, "bold" if bold else "normal"), anchor="w")

    def button(self, parent, text, command, color="white"):
        return tk.Button(parent, text=text, command=command, bg=color, fg=INK,
                         activebackground=YELLOW, activeforeground=INK, relief="solid",
                         bd=2, padx=10, pady=7, font=("Segoe UI", 10, "bold"), cursor="hand2")

    def check(self, parent, text, variable, command):
        return tk.Checkbutton(parent, text=text, variable=variable, command=command,
                              bg=parent.cget("bg"), fg=INK, activebackground=parent.cget("bg"),
                              selectcolor="white", font=("Segoe UI", 10), anchor="w")

    def control_has_focus(self, widget):
        # Tcl owns combobox popdowns; Python's focus_get cannot resolve them.
        focus = str(self.root.tk.call("focus"))
        return focus == str(widget) or focus.startswith(str(widget) + ".")

    def gain_changed(self, value):
        gain = round(float(value), 1)
        self.gain_label.set(f"Sensitivity · {gain:.1f}×")
        if hasattr(self, "session"):
            self.session.panel.gain = gain
            self.schedule_save()

    def agc_changed(self):
        self.session.panel.agc = self.agc.get()
        self.schedule_save()

    def schedule_save(self):
        if not self.preferences_valid:
            return
        if self.save_timer:
            self.root.after_cancel(self.save_timer)
        self.save_timer = self.root.after(500, self.save)

    def send(self, command, value):
        if not hasattr(self, "session") or self.session.panel.settings is None:
            return
        if command == 1 and value == 0 or command == 2 and value > 7:
            return
        self.session.panel.commands.put((command, value))

    def pause(self):
        self.session.panel.paused = not self.session.panel.paused

    def device_changed(self, event=None):
        self.session.change_device("" if self.device.get() == "Default output" else self.device.get())
        self.schedule_save()

    def refresh_devices(self):
        def discover():
            try:
                names = [s.name for s in musicviz.sc.all_speakers()] if musicviz.sc else []
                self.events.put(("devices", names))
            except Exception as exc:
                logging.exception("Audio device enumeration failed")
                self.events.put(("error", str(exc)))
        threading.Thread(target=discover, daemon=True).start()

    def startup_changed(self):
        try:
            set_startup(self.startup.get())
            self.schedule_save()
        except Exception as exc:
            self.startup.set(startup_enabled())
            messagebox.showerror("Windows startup", str(exc), parent=self.root)

    def save(self):
        self.save_timer = None
        values = dict(version=1, gain=self.session.panel.gain, agc=self.agc.get(),
                      device="" if self.device.get() == "Default output" else self.device.get(),
                      startup=self.startup.get())
        try:
            save_preferences(self.path, values)
            self.preferences_valid = True
        except OSError as exc:
            messagebox.showerror("Save preferences", str(exc), parent=self.root)

    def start_tray(self):
        def action(name):
            return lambda icon, item: self.events.put((name, None))
        try:
            self.tray = pystray.Icon("Lucky65Music", icon_image(), "Lucky65 Music",
                menu=pystray.Menu(pystray.MenuItem("Open", action("open"), default=True),
                                  pystray.MenuItem("Pause / Resume", action("pause")),
                                  pystray.MenuItem("Quit", action("quit"))))
            self.tray.run_detached()
        except Exception:
            logging.exception("Tray unavailable")
            self.tray = None

    def hide(self):
        if self.tray and self.tray.visible:
            self.root.withdraw()
        else:
            self.quit()

    def tick(self):
        try:
            self.refresh_panel()
        except Exception:
            logging.exception("GUI refresh failed; retrying")
        finally:
            if not self.closed:
                self.root.after(33, self.tick)

    def refresh_panel(self):
        if self.closing:
            if not self.session.thread.is_alive():
                if self.tray:
                    self.tray.stop()
                self.closed = True
                self.root.destroy()
            return
        while not self.events.empty():
            action, value = self.events.get_nowait()
            if action == "open":
                self.root.deiconify()
                self.root.lift()
            elif action == "pause":
                self.pause()
            elif action == "quit":
                self.quit()
            elif action == "devices":
                self.device.configure(values=["Default output"] + value)
            elif action == "error":
                self.status.set(value)
        panel = self.session.panel
        self.status.set(panel.status)
        self.meter.update_lighting(panel.levels, panel.settings, panel.last_audio_at)
        self.pause_button["text"] = "RESUME" if panel.paused else "PAUSE"
        state = panel.settings
        for widget in (self.effect, self.color):
            widget.configure(state="readonly" if state else "disabled")
        self.brightness_scale.configure(state="normal" if state else "disabled")
        if state:
            if not self.control_has_focus(self.effect):
                self.effect.set(MODES[state[0]])
            if not self.control_has_focus(self.color):
                self.color.set(COLORS[state[1]])
            if not self.control_has_focus(self.brightness_scale):
                self.brightness.set(state[2])

    def quit(self):
        if self.closing:
            return
        if self.preferences_valid:
            self.save()
        self.closing = True
        self.status.set("Closing audio and keyboard connection…")
        self.session.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--tray", action="store_true")
    parser.add_argument("--smoke-test", action="store_true", help="run a short hidden demo and exit")
    args = parser.parse_args()
    APP_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, handlers=[RotatingFileHandler(
        APP_DIR / "app.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")])
    # A synthetic smoke test must not contend with a user's live lighting session.
    instance = None if args.smoke_test else Instance()
    root = tk.Tk()
    root.withdraw()
    try:
        if instance and instance.exists:
            messagebox.showinfo("Lucky65 Music", "Already running—open Lucky65 Music from the system tray.", parent=root)
            return
        root.report_callback_exception = lambda *error: logging.error("GUI callback failed", exc_info=error)
        if args.smoke_test and (musicviz.hid is None or musicviz.sc is None):
            raise RuntimeError("Packaged HID/audio dependencies failed to load")
        app = DesktopApp(root, demo=args.demo or args.smoke_test, tray=args.tray,
                         config_dir=APP_DIR / "smoke-test" if args.smoke_test else APP_DIR)
        if args.smoke_test:
            root.withdraw()
            root.after(2000, app.quit)
        elif not args.tray or not app.tray:
            root.deiconify()
        root.mainloop()
        logging.info("Application exited cleanly")
    finally:
        if instance:
            instance.close()


if __name__ == "__main__":
    main()
