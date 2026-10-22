# Copyright (c) 2026 Routekernel. All rights reserved.
# Licensed under the project LICENSE; third-party notices remain applicable.
"""Build deterministic DEB and IPK archives without platform-specific tools."""
import gzip
import hashlib
import io
from pathlib import Path
import tarfile
import argparse

ROOT = Path(__file__).resolve().parents[1]
VERSION = "0.2.3"
NAME = "enigma2-plugin-extensions-e2pvr"


def archive(files):
    result = io.BytesIO()
    with tarfile.open(fileobj=result, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        directories = set()
        for name, content, mode in files:
            parent = Path(name).parent
            while str(parent) != ".":
                directories.add("./" + parent.as_posix().lstrip("./"))
                parent = parent.parent
        for name in sorted(directories, key=lambda value: (value.count("/"), value)):
            entry = tarfile.TarInfo(name + "/")
            entry.type = tarfile.DIRTYPE
            entry.mode = 0o755
            tar.addfile(entry)
        for name, content, mode in sorted(files):
            entry = tarfile.TarInfo(name)
            entry.mode = mode
            entry.size = len(content)
            entry.mtime = 0
            tar.addfile(entry, io.BytesIO(content))
    return gzip.compress(result.getvalue(), mtime=0)


def ar(members):
    result = bytearray(b"!<arch>\n")
    for name, content in members:
        header = "{:<16}{:<12}{:<6}{:<6}{:<8}{:<10}`\n".format(name + "/", 0, 0, 0, "100644", len(content))
        result.extend(header.encode("ascii"))
        result.extend(content)
        if len(content) % 2:
            result.extend(b"\n")
    return bytes(result)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--native-root", type=Path)
    parser.add_argument("--architecture", default="all")
    parser.add_argument("--format", choices=("deb", "ipk", "both"), default="both")
    parser.add_argument("--python-abi", choices=("2.7", "3"))
    arguments = parser.parse_args(argv)
    if arguments.native_root and arguments.architecture == "all":
        parser.error("Native packages require an explicit receiver architecture")
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    files = []
    source = arguments.native_root or ROOT / "src" / "E2PVR"
    for path in sorted(source.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix in (".py", ".json", ".txt", ".ttf", ".png", ".so"):
            files.append(("./usr/lib/enigma2/python/Plugins/Extensions/E2PVR/" + path.relative_to(source).as_posix(),
                          path.read_bytes() if path.suffix in (".ttf", ".png", ".so") else path.read_bytes().replace(b"\r\n", b"\n"), 0o644))
    for name in ("LICENSE", "README.md"):
        path = ROOT / name
        if path.is_file():
            files.append(("./usr/share/doc/" + NAME + "/" + name, path.read_bytes(), 0o644))
    for extension in (("deb", "ipk") if arguments.format == "both" else (arguments.format,)):
        plugin_root = "./usr/lib/enigma2/python/Plugins/Extensions/E2PVR/"
        platform = "dreamos" if extension == "deb" else "oealliance-universal"
        payload = [item for item in files if item[0] != plugin_root + "platform_profile.py"]
        payload.append((plugin_root + "platform_profile.py", ('PLATFORM_PROFILE = "%s"\n' % platform).encode("ascii"), 0o644))
        data = archive(payload)
        dependency = {"2.7": ", python-core (>= 2.7), python-core (<< 2.8)",
                      "3": ", python3-core"}.get(arguments.python_abi, "")
        architecture = arguments.architecture
        control = ("Package: %s\nVersion: %s\nArchitecture: %s\nSection: extra\nPriority: optional\n"
                   "Maintainer: Routekernel\nDepends: enigma2, ffmpeg, ca-certificates%s\n"
                   "Description: PVR subtitle translation\n"
                   " Online subtitle translation during recording playback.\n" %
                   (NAME, VERSION, architecture, dependency))
        postinst = '''#!/bin/sh
set -e
KEY_FILE=__KEY_FILE__
mkdir -p "$(dirname "$KEY_FILE")"
if [ "$KEY_FILE" = /home/root/apikey.txt ]; then
    chown root:root /home/root
    chmod 700 /home/root
fi
for previous in /root/key.txt /root/apikey.txt /apikey.txt; do
    if [ ! -e "$KEY_FILE" ] && [ -f "$previous" ] && [ ! -L "$previous" ]; then
        mv "$previous" "$KEY_FILE"
    fi
done
if [ ! -e "$KEY_FILE" ]; then
    (umask 077; set -C; : > "$KEY_FILE") || [ -e "$KEY_FILE" ]
fi
if [ ! -f "$KEY_FILE" ] || [ -L "$KEY_FILE" ]; then
    echo "e2pvr: key must be a regular file" >&2
    exit 1
fi
chown root:root "$KEY_FILE"
chmod 600 "$KEY_FILE"
if [ -f /root/key.txt ] && [ ! -L /root/key.txt ] && cmp -s /root/key.txt "$KEY_FILE"; then
    rm -f /root/key.txt
fi
plugin_dir=/usr/lib/enigma2/python/Plugins/Extensions/E2PVR
if [ -d "$plugin_dir" ]; then
    find "$plugin_dir" -type f \\( -name '*.pyc' -o -name '*.pyo' \\) -exec rm -f -- {} \\;
fi
for archive in /tmp/enigma2-plugin-extensions-e2pvr*.deb /tmp/enigma2-plugin-extensions-e2pvr*.ipk /tmp/e2pvr*.deb /tmp/e2pvr*.ipk; do
    if [ -f "$archive" ]; then
        rm -f -- "$archive"
    fi
done
if command -v pidof >/dev/null 2>&1 && pidof enigma2 >/dev/null 2>&1; then
    (
        trap '' HUP
        sleep 2
        if command -v systemctl >/dev/null 2>&1 && systemctl -q is-active enigma2.service; then
            systemctl --no-block restart enigma2.service
        elif [ -x /etc/init.d/enigma2 ]; then
            /etc/init.d/enigma2 restart
        else
            init 4
            sleep 2
            init 3
        fi
    ) </dev/null >/dev/null 2>&1 &
fi
exit 0
'''.replace("__KEY_FILE__", "/root/apikey.txt" if extension == "deb" else "/home/root/apikey.txt")
        metadata = archive([("./control", control.encode("utf-8"), 0o644),
                            ("./postinst", postinst.encode("utf-8"), 0o755)])
        package = ar([("debian-binary", b"2.0\n"), ("control.tar.gz", metadata), ("data.tar.gz", data)])
        path = output / (NAME + "_" + VERSION + "_" + architecture + "." + extension)
        path.write_bytes(package)
        path.with_suffix(path.suffix + ".sha256").write_text(hashlib.sha256(package).hexdigest() + "  " + path.name + "\n")
        print(path)


if __name__ == "__main__":
    main()
