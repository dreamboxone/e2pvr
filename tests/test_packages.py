# Copyright (c) 2026 Routekernel. All rights reserved.
# Licensed under the project LICENSE; third-party notices remain applicable.
import importlib.util
import io
from pathlib import Path
import tarfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("packages", ROOT / "tools/build_packages.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def members(data):
    result, offset = {}, 8
    while offset < len(data):
        header = data[offset:offset+60]
        size = int(header[48:58])
        name = header[:16].decode("ascii").strip().rstrip("/")
        result[name] = data[offset+60:offset+60+size]
        offset += 60 + size + size % 2
    return result


class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        builder.main()

    def test_both_formats_include_parent_directories_and_correct_profile(self):
        for extension, profile, key_path in [("deb", "dreamos", "/root/apikey.txt"),
                                              ("ipk", "oealliance-universal", "/home/root/apikey.txt")]:
            path = ROOT / "dist" / (builder.NAME + "_" + builder.VERSION + "_all." + extension)
            ar = members(path.read_bytes())
            self.assertEqual(ar["debian-binary"], b"2.0\n")
            prefix = "./usr/lib/enigma2/python/Plugins/Extensions/E2PVR/"
            with tarfile.open(fileobj=io.BytesIO(ar["data.tar.gz"])) as data:
                names = data.getnames()
                self.assertIn(prefix.rstrip("/"), names)
                self.assertIn(profile, data.extractfile(prefix+"platform_profile.py").read().decode())
                self.assertFalse(any(name.endswith((".pyc", ".pyo", "key.txt", "apikey.txt")) for name in names))
                self.assertIn(prefix+"OFL-Vazirmatn.txt", names)
                self.assertIn(prefix+"LICENSE-E2Dub.txt", names)
            with tarfile.open(fileobj=io.BytesIO(ar["control.tar.gz"])) as control:
                postinst = control.extractfile("./postinst").read().decode()
                self.assertIn("KEY_FILE=" + key_path, postinst)
                self.assertEqual(control.getmember("./postinst").mode, 0o755)

    def test_archives_are_reproducible(self):
        paths = sorted((ROOT/"dist").glob("*_" + builder.VERSION + "_all.*"))
        before = {path: path.read_bytes() for path in paths}
        builder.main()
        for path, contents in before.items():
            self.assertEqual(path.read_bytes(), contents)


if __name__ == "__main__":
    unittest.main()
