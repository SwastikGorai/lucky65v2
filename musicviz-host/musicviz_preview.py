"""Host-side music lighting estimate; the protocol does not return LED frames."""
import colorsys
import time
import tkinter as tk

FULL = 255 << 16
PALETTE = ((0, 255), (43, 255), (85, 255), (128, 255),
           (170, 255), (234, 128), (0, 0))

# Physical ANSI layout: 67 lit keys, with the three space switches shown as one key.
ROWS = (
    [(key, 1) for key in ("Esc", "1", "2", "3", "4", "5", "6", "7", "8", "9", "0", "−", "=")]
    + [("Back", 2), ("Ins", 1)],
    [("Tab", 1.5)] + [(key, 1) for key in ("Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P", "[", "]")]
    + [("\\", 1.5), ("Del", 1)],
    [("Caps", 1.75)] + [(key, 1) for key in ("A", "S", "D", "F", "G", "H", "J", "K", "L", ";", "'")]
    + [("Enter", 2.25), ("PgUp", 1)],
    [("Shift", 2.25)] + [(key, 1) for key in ("Z", "X", "C", "V", "B", "N", "M", ",", ".", "/")]
    + [("Shift", 1.75), ("↑", 1), ("PgDn", 1)],
    [("Ctrl", 1.25), ("Win", 1.25), ("Alt", 1.25), ("", 6.25), (None, 1)]
    + [(key, 1) for key in ("Fn", "Ctrl", "←", "↓", "→")],
)


class LightingModel:
    def __init__(self):
        self.level = 0
        self.last_ms = None

    def frame(self, levels, settings, now, last_audio_at):
        milliseconds = int(now * 1000)
        dt = 0 if self.last_ms is None else min(4000, max(0, milliseconds - self.last_ms))
        self.last_ms = milliseconds
        raw = max(levels, default=0) if now - last_audio_at <= 0.5 else 0
        target = min(FULL, int(raw) * FULL // 235)
        for _ in range(dt):
            if self.level < target:
                self.level += (target - self.level + 39) // 40
            elif self.level > target:
                self.level -= (self.level - target + 179) // 180
            else:
                break
        if settings is None:
            return [(0, 0, 0)] * 5, "Waiting for keyboard settings"
        mode, color, brightness, enabled = settings
        if not enabled:
            return [(0, 0, 0)] * 5, "RGB is off"
        if mode not in (1, 2):
            return [(0, 0, 0)] * 5, "Select a music effect to preview"
        if color == 8:
            return [(0, 0, 0)] * 5, "Custom VIA color: preview unavailable"
        hue, saturation = PALETTE[color] if color < 7 else (int(now * 1000) % 12000 * 256 // 12000, 255)
        rows = []
        for row in range(5):
            fill = self.level if mode == 1 else min(FULL, max(0, self.level * 5 - (4-row) * FULL))
            value = ((fill >> 8) * brightness + (FULL >> 9)) // (FULL >> 8)
            rows.append(tuple(round(c * 255) for c in colorsys.hsv_to_rgb(hue / 255, saturation / 255, value / 255)))
        return rows, "Live estimate · drift phase and indicator LEDs may differ"


class KeyboardPreview(tk.Canvas):
    def __init__(self, parent):
        super().__init__(parent, bg="#191919", height=166, highlightthickness=0)
        self.model = LightingModel()
        self.row_colors = [(0, 0, 0)] * 5
        self.caption = "Waiting for keyboard settings"
        self.keys = []
        self.bind("<Configure>", lambda event: self.draw_layout())

    def update_lighting(self, levels, settings, last_audio_at, now=None):
        self.row_colors, self.caption = self.model.frame(levels, settings, time.monotonic() if now is None else now, last_audio_at)
        self.paint()

    def draw_layout(self):
        self.delete("all")
        self.keys.clear()
        width = max(self.winfo_width(), 100)
        unit = (width - 24) / 16
        height = 25
        self.create_rectangle(2, 2, width-2, 142, fill="#252525", outline="#5C625E", width=2)
        for row, keys in enumerate(ROWS):
            x = 12
            for label, units in keys:
                if label is not None:
                    y = 9 + row * height
                    item = self.create_rectangle(x+1, y, x+unit*units-3, y+height-4,
                                                 width=1, tags="key")
                    legend = self.create_text(x+unit*units/2-1, y+(height-4)/2,
                                              text=label, font=("Segoe UI", 8), tags="legend")
                    self.keys.append((row, item, legend))
                x += unit * units
        self.create_text(10, 157, anchor="w", fill="#AEB6AE", font=("Segoe UI", 8), tags="caption")
        self.paint()

    def paint(self):
        for row, item, legend in self.keys:
            rgb = self.row_colors[row]
            # Keep unlit keycaps visible; colored edges represent the backlight.
            fill = tuple(round(38 + value * 0.62) for value in rgb)
            edge = tuple(max(65, value) for value in rgb)
            self.itemconfigure(item, fill="#%02x%02x%02x" % fill, outline="#%02x%02x%02x" % edge)
            luminance = fill[0] * .2126 + fill[1] * .7152 + fill[2] * .0722
            self.itemconfigure(legend, fill="#111111" if luminance > 125 else "#E5E8E5")
        self.itemconfigure("caption", text=self.caption)
