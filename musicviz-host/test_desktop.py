import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from musicviz_desktop import DEFAULTS, DesktopSession, Instance, load_preferences, save_preferences, set_startup
from test_tui import args


class DesktopTests(unittest.TestCase):
    def test_keyboard_lighting(self):
        from musicviz_preview import LightingModel, FULL, ROWS
        self.assertEqual(sum(label is not None for row in ROWS for label, width in row), 67)
        self.assertTrue(all(sum(width for label, width in row) == 16 for row in ROWS))
        model = LightingModel()
        settings = (1, 0, 200, 1)
        model.frame([235], settings, 0, 0)
        colors, _ = model.frame([235], settings, 0.04, 0.04)
        self.assertTrue(FULL * .62 < model.level < FULL * .65)
        self.assertTrue(all(color == colors[0] for color in colors))
        self.assertGreater(colors[0][0], 0)
        self.assertEqual(colors[0][1:], (0, 0))
        model.level = FULL // 10
        colors, _ = model.frame([235], (2, 6, 200, 1), .04, .04)
        self.assertEqual(colors[:4], [(0, 0, 0)] * 4)
        self.assertEqual(colors[4], (100, 100, 100))
        for state in ((1, 0, 0, 1), (1, 0, 200, 0), None, (0, 0, 200, 1), (1, 8, 200, 1)):
            colors, _ = model.frame([235], state, .04, .04)
            self.assertEqual(colors, [(0, 0, 0)] * 5)
        model.level = FULL
        colors, _ = model.frame([235], settings, 5, .04)
        self.assertEqual(colors, [(0, 0, 0)] * 5)

    def test_dropdown_focus_and_refresh_recovery(self):
        import tkinter as tk
        from musicviz_gui import DesktopApp
        with tempfile.TemporaryDirectory() as directory, patch.object(DesktopApp, "start_tray"), patch.object(DesktopApp, "refresh_devices"):
            root = tk.Tk()
            app = DesktopApp(root, demo=True, config_dir=Path(directory))
            try:
                root.update()
                root.tk.call("ttk::combobox::Post", str(app.effect))
                popup = str(root.tk.call("ttk::combobox::PopdownWindow", str(app.effect)))
                root.tk.call("focus", "-force", popup + ".f.l")
                root.update()
                # Real Tk popdown focus reproduces the reported Python wrapper failure.
                with self.assertRaises(KeyError):
                    root.focus_get()
                self.assertTrue(app.control_has_focus(app.effect))
                app.refresh_panel()
                root.tk.call("ttk::combobox::Unpost", str(app.effect))
                with patch.object(app, "refresh_panel", side_effect=RuntimeError("transient")), patch.object(root, "after") as after, patch("musicviz_gui.logging.exception"):
                    app.tick()
                    after.assert_called_once_with(33, app.tick)
                app.refresh_panel()
                self.assertEqual(len(app.meter.find_withtag("key")), 67)
            finally:
                app.quit()
                app.session.thread.join(1)
                root.destroy()

    def test_single_instance(self):
        first = Instance()
        second = Instance()
        try:
            self.assertTrue(second.exists)
        finally:
            second.close()
            first.close()

    def test_startup_quotes_path_and_removes_only_app(self):
        import winreg
        with patch("musicviz_desktop.sys.frozen", True, create=True), patch("musicviz_desktop.sys.executable", r"C:\Apps With Spaces\Lucky65Music.exe"), patch.object(winreg, "CreateKey"), patch.object(winreg, "SetValueEx") as write, patch.object(winreg, "DeleteValue") as delete:
            set_startup(True)
            self.assertEqual(write.call_args.args[1], "Lucky65Music")
            self.assertEqual(write.call_args.args[4], '"C:\\Apps With Spaces\\Lucky65Music.exe" --tray')
            set_startup(False)
            self.assertEqual(delete.call_args.args[1], "Lucky65Music")

    def test_retry_recovers(self):
        calls = []
        def runner(options, panel):
            calls.append(1)
            if len(calls) == 1:
                raise OSError("Disconnected")
            panel.stop.wait(3)
        session = DesktopSession(args(), runner=runner)
        with patch("musicviz_desktop.logging.exception"):
            session.start()
            time.sleep(2.2)
            session.close()
            session.thread.join(1)
        self.assertEqual(len(calls), 2)
        self.assertFalse(session.thread.is_alive())

    def test_gui_controls(self):
        import tkinter as tk
        from musicviz_gui import DesktopApp
        with tempfile.TemporaryDirectory() as directory, patch.object(DesktopApp, "start_tray"), patch.object(DesktopApp, "refresh_devices"):
            root = tk.Tk()
            root.withdraw()
            app = DesktopApp(root, demo=True, config_dir=Path(directory))
            try:
                app.gain_changed("2.4")
                app.send(1, 2)
                app.send(2, 7)
                time.sleep(0.15)
                app.tick()
                self.assertEqual(app.session.panel.settings[:2], (2, 7))
                app.save()
                self.assertEqual(load_preferences(app.path)[0]["gain"], 2.4)
                app.pause()
                self.assertTrue(app.session.panel.paused)
            finally:
                app.quit()
                app.session.thread.join(1)
                root.destroy()

    def test_preferences(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "settings.json"
            self.assertEqual(load_preferences(path), (DEFAULTS, None))
            values = dict(DEFAULTS, gain=2.1, device="Speakers")
            save_preferences(path, values)
            self.assertEqual(load_preferences(path), (values, None))
            for text in ('broken', '{"version": 2}', '[]'):
                path.write_text(text)
                self.assertIsNotNone(load_preferences(path)[1])
                self.assertEqual(path.read_text(), text)

    def test_shutdown_interrupts_retry(self):
        calls = []
        def fail(options, panel):
            calls.append(1)
            raise OSError("Disconnected")
        session = DesktopSession(args(), runner=fail)
        with patch("musicviz_desktop.logging.exception"):
            session.start()
            time.sleep(0.1)
            session.close()
            session.thread.join(1)
        self.assertFalse(session.thread.is_alive())
        self.assertEqual(len(calls), 1)

    def test_demo_pause_and_shutdown(self):
        session = DesktopSession(args())
        session.start()
        try:
            time.sleep(0.15)
            session.panel.commands.put((2, 7))
            session.panel.paused = True
            time.sleep(0.15)
            self.assertEqual(session.panel.settings[1], 7)
            self.assertEqual(int(max(session.panel.levels)), 0)
        finally:
            session.close()
            session.thread.join(1)
        self.assertFalse(session.thread.is_alive())


if __name__ == "__main__":
    unittest.main()
