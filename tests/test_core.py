# Copyright (c) 2026 Routekernel. All rights reserved.
# Licensed under the project LICENSE; third-party notices remain applicable.
import importlib.util
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("core", os.path.join(ROOT, "src", "E2PVR", "core.py"))
core = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core)


class CoreTests(unittest.TestCase):
    def test_seek_and_pause_timeline(self):
        track = core.SubtitleTrack([(1000, 2000, "first"), (3000, 4500, "second")])
        for position, expected in [(0, ""), (1000, "first"), (2000, ""),
                                   (4000, "second"), (1000, "first"),
                                   (1000, "first"), (5000, "")]:
            self.assertEqual(track.text_at(position), expected)

    def test_unicode_srt(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "sample.srt")
            with open(path, "w", encoding="utf-8-sig", newline="") as stream:
                stream.write("1\r\n00:00:01,250 --> 00:00:02,500\r\nسلام\r\nدنیا\r\n")
            self.assertEqual(core.SubtitleTrack.load(path).text_at(1250), "سلام\nدنیا")

    def test_overlay_stays_on_screen(self):
        for width, height in [(720, 576), (1280, 720), (1920, 1080)]:
            for size in ("small", "medium", "large"):
                for percent in (-10, 0, 80, 100, 150):
                    x, y, w, h, font = core.overlay_geometry(width, height, percent, size)
                    self.assertGreaterEqual(y, 0)
                    self.assertLessEqual(y + h, height)
                    self.assertLessEqual(x + w, width)


if __name__ == "__main__":
    unittest.main()
