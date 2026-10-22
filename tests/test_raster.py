# Copyright (c) 2026 Routekernel. All rights reserved.
# Licensed under the project LICENSE.
import os
import sys
import unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))
from E2PVR.raster import font_family


class RasterTests(unittest.TestCase):
    def test_bundled_font_uses_its_real_family_for_shaping(self):
        font = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src", "E2PVR", "Vazirmatn-SemiBold.ttf")
        self.assertEqual(font_family(font), "Vazirmatn SemiBold")


if __name__ == "__main__":
    unittest.main()
