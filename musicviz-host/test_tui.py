import asyncio
import unittest
from types import SimpleNamespace

from musicviz import HidStreamer
from musicviz_tui import MusicApp, Panel


def args():
    return SimpleNamespace(gain=1.0, no_agc=False, dry_run=True, bands=30,
                           fps=60, probe=None, selftest=True, duration=0,
                           preview=False, device=None, rate=None, tilt=6)


class ControlTests(unittest.TestCase):
    def test_protocol(self):
        class Device:
            def write(self, payload):
                self.payload = payload
                return len(payload)

            def read(self, size, timeout):
                assert (size, timeout) == (32, 1)
                return self.response

        transport = HidStreamer()
        transport.dev = Device()
        transport.control(2, 7)
        self.assertEqual(transport.dev.payload, bytes([0, 0x4E, 1, 2, 7]) + bytes(28))
        transport.dev.response = bytes([0x4E, 1, 0x80, 2, 7, 200, 1]) + bytes(25)
        self.assertEqual(transport.read_settings(), (2, 7, 200, 1))
        transport.dev.response = bytes(32)
        self.assertIsNone(transport.read_settings())
        panel = Panel(args())
        panel.exchange(transport, panel.last_reply + 3)
        self.assertIsNone(panel.settings)


class TuiTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_controls(self):
        app = MusicApp(args())
        async with app.run_test(size=(100, 32)) as pilot:
            await pilot.pause(0.2)
            await pilot.click("#gain-up")
            self.assertAlmostEqual(app.panel.gain, 1.1)
            await pilot.click("#agc")
            self.assertFalse(app.panel.agc)
            await pilot.click("#bar")
            for _ in range(7):
                await pilot.click("#color")
                await pilot.pause(0.05)
            await pilot.click("#dimmer")
            await pilot.pause(0.1)
            self.assertEqual(app.panel.settings, (2, 7, 190, 1))
            await pilot.press("space")
            await pilot.pause(0.1)
            self.assertTrue(app.panel.paused)
            self.assertEqual(int(app.panel.levels.max()), 0)
            await pilot.press("q")
        self.assertFalse(app.thread.is_alive())


if __name__ == "__main__":
    unittest.main()
